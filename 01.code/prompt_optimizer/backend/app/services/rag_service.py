# ==========================================================
# RAG 检索评测服务
#   - 语料入库：分块 + 嵌入（优先调用配置的 embedding 模型；不可用时降级为本地词法指纹）
#   - 检索：对 query 取 top-k 块，注入为生成/评测的上下文
#   - 评测：source_support（确定性来源支撑度）+ faithfulness（LLM 忠实度评审，可选）
# ==========================================================
import json
import math
import re

import httpx
from sqlalchemy import update

from app.core.config import get_settings
from app.core.exceptions import not_found
from app.llm.client import get_llm_client
from app.models import KnowledgeBase, KnowledgeChunk

settings = get_settings()

# 分块参数
_CHUNK_SIZE = 512
_CHUNK_OVERLAP = 60

# 内容词：仅取中文+字母数字作为检索指纹特征，跳过纯标点/空白
_TOKEN_RE = re.compile(r"[0-9A-Za-z\u4e00-\u9fff]+")


def _iter_ngrams(text: str, n: int = 2):
    """产出字符级 1~n gram（去除空白后），作为词法检索/相似度指纹特征。"""
    s = "".join(_TOKEN_RE.findall(text))
    chars = list(s)
    for i, c in enumerate(chars):
        yield c
    for i in range(len(chars) - 1):
        yield chars[i] + chars[i + 1]


def ngram_fingerprint(text: str) -> dict[str, int]:
    """把文本压缩为一个无序的词法指纹 {特征: 频次}（对中文检索有效且零外部依赖）。"""
    freq: dict[str, int] = {}
    for token in _iter_ngrams(text):
        freq[token] = freq.get(token, 0) + 1
    return freq


def _cosine_dict(a: dict, b: dict) -> float:
    """两个稀疏频次字典的余弦相似度。"""
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _cosine_vec(a: list, b: list) -> float:
    """两个等长向量的余弦相似度。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ----------------------------------------------------------
# 分块
# ----------------------------------------------------------
def chunk_text(content: str, size: int = _CHUNK_SIZE,
               overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """把长文本切分为可检索的块。先按段落拆，段落过长再按句子拆，最终按窗口合并（带重叠）。"""
    if not content or not content.strip():
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]

    units: list[str] = []
    for p in paragraphs:
        if len(p) <= size:
            units.append(p)
            continue
        # 长段落按句界拆分，避免一句被硬切
        parts = re.split(r"(?<=[。！？!?；;\n])", p)
        buf = ""
        for part in parts:
            if not part:
                continue
            if buf and len(buf) + len(part) > size:
                units.append(buf.strip())
                buf = part
            else:
                buf += part
        if buf.strip():
            units.append(buf.strip())

    chunks: list[str] = []
    cur = ""
    for u in units:
        if not cur:
            cur = u
        elif len(cur) + len(u) <= size:
            cur += u
        else:
            chunks.append(cur)
            cur = (cur[-overlap:] if overlap else "") + u
    if cur.strip():
        chunks.append(cur)
    return [c for c in chunks if c.strip()]


# ----------------------------------------------------------
# 嵌入（向量）；失败时由外层降级为词法指纹
# ----------------------------------------------------------
async def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """批量嵌入。未配置嵌入模型或调用失败时返回 None，交由调用方降级。"""
    if not settings.EMBED_MODEL or not (settings.LLM_BASE_URL and settings.LLM_API_KEY):
        return None
    url = settings.LLM_BASE_URL.rstrip("/") + "/embeddings"
    payload = {"model": settings.EMBED_MODEL, "input": texts}
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            data = data.get("data") or []
            if len(data) != len(texts):
                return None
            out = [d["embedding"] for d in data]
            return out if all(isinstance(v, list) and v for v in out) else None
    except Exception:  # noqa: BLE001 嵌入失败不阻断入库，静默降级词法检索
        return None


# ----------------------------------------------------------
# 知识库 CRUD 与入库
# ----------------------------------------------------------
def get_kb_owned(db, kb_id: int, user_id: int) -> KnowledgeBase:
    """按属主取知识库，供任务/接口校验。"""
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.user_id != user_id:
        raise not_found("知识库不存在或无权访问")
    return kb


def create_kb(db, user_id: int, name: str, description: str = "",
              embed_model: str = "") -> KnowledgeBase:
    """创建知识库。embed_model 传空则入库时用本地词法检索。"""
    return KnowledgeBase(
        user_id=user_id, name=name, description=description,
        embed_model=embed_model or "", doc_count=0, chunk_count=0,
    )


def _set_doc_state(db, doc, status: str, error: str = ""):
    doc.status = status
    doc.error = error or None


async def add_document(db, kb: KnowledgeBase, title: str, content: str,
                       embed_model: str = "") -> dict:
    """把一份文档入库：分块 + 嵌入（或词法指纹），并刷新知识库计数。

    :param embed_model: 当前知识库采用的嵌入方式；空走词法指纹。实际是否走向量由
                        embed_texts 是否成功决定，成功后落库为向量、否则指纹。
    :return: {"doc_id", "chunk_count", "embed_mode": "vector"|"ngram"}
    """
    from app.models import KnowledgeDoc

    embed_mode = "ngram"
    doc = KnowledgeDoc(kb_id=kb.id, title=title, content=content, status="processing")
    db.add(doc)
    db.flush()

    try:
        chunks = chunk_text(content)
        vectors = await embed_texts(chunks) if (embed_model or settings.EMBED_MODEL) else None
        if vectors is not None:
            embed_mode = "vector"
            embeddings = [json.dumps(v) for v in vectors]
        else:
            embeddings = [json.dumps({"ngrams": ngram_fingerprint(c)}) for c in chunks]

        seq = 0
        for text, emb in zip(chunks, embeddings):
            db.add(KnowledgeChunk(
                kb_id=kb.id, doc_id=doc.id, seq=seq, text=text, embedding=emb,
            ))
            seq += 1
        _set_doc_state(db, doc, "done")
    except Exception as exc:  # noqa: BLE001
        db.rollback()  # 回滚到文档行
        raise exc

    # 计数用 SQL 原子自增而非 ORM 对象自增：并发上传同库时避免 lost update 丢计数。
    # 注意不要在 ORM 对象上自增 doc_count/chunk_count，否则 commit 时会用陈旧值覆盖原子结果。
    db.execute(
        update(KnowledgeBase)
        .where(KnowledgeBase.id == kb.id)
        .values(doc_count=KnowledgeBase.doc_count + 1,
                chunk_count=KnowledgeBase.chunk_count + len(chunks))
        .execution_options(synchronize_session=False)
    )
    kb.embed_model = embed_model  # 记录库的实际检索方式标签（信息性）
    db.commit()
    return {"doc_id": doc.id, "chunk_count": len(chunks), "embed_mode": embed_mode}


# ----------------------------------------------------------
# 检索
# ----------------------------------------------------------
def build_retriever(db, kb_id: int):
    """把知识库的块载入内存，返回一个 async 检索函数。

    :return: async retrieve(query, top_k) -> [{doc_title, seq, text, score, chunk_id}]
    """
    kb = db.get(KnowledgeBase, kb_id)
    rows = db.query(KnowledgeChunk).filter(KnowledgeChunk.kb_id == kb_id).all()
    from app.models import KnowledgeDoc

    titles = {d.id: d.title for d in db.query(KnowledgeDoc).filter(KnowledgeDoc.kb_id == kb_id)}
    store = []
    for ch in rows:
        store.append({
            "chunk_id": ch.id, "seq": ch.seq, "text": ch.text,
            "doc_title": titles.get(ch.doc_id, ""),
            "embedding": ch.embedding,
        })

    use_vector = bool(kb.embed_model)

    async def retrieve(query: str, top_k: int = 4) -> list[dict]:
        if not store:
            return []
        # query 指纹/向量
        if use_vector:
            qvec = None
            vectors = await embed_texts([query])
            if vectors:
                qvec = vectors[0]
            if qvec is None:
                # 块存的是向量，查询向量不可用则无法计算相似度；
                # 直接返回空以免注入随机命中的错误上下文（优雅降级为不检索）
                return []
            sims = []
            for it in store:
                try:
                    vec = json.loads(it["embedding"])
                except Exception:  # noqa: BLE001
                    continue
                score = _cosine_vec(qvec, vec) if isinstance(vec, list) else 0.0
                sims.append((score, it))
        else:
            qvec = ngram_fingerprint(query)
            sims = []
            for it in store:
                try:
                    fp = json.loads(it["embedding"]).get("ngrams", {})
                except Exception:  # noqa: BLE001
                    continue
                sims.append((_cosine_dict(qvec, fp), it))
        sims.sort(key=lambda t: t[0], reverse=True)
        return [{
            "chunk_id": it["chunk_id"], "doc_title": it["doc_title"],
            "seq": it["seq"], "text": it["text"], "score": round(s, 4),
        } for s, it in sims[:top_k]]

    return retrieve


def compose_context(chunks: list[dict]) -> str:
    """把检索结果拼装为可注入提示词的"参考知识"文本块。"""
    parts = []
    for i, c in enumerate(chunks, 1):
        title = c.get("doc_title") or "知识"
        parts.append(f"[来源{i}] {title}\n{c.get('text', '')}")
    return "\n\n".join(parts)


# ----------------------------------------------------------
# 评测指标
# ----------------------------------------------------------
def source_support(output: str, context: str) -> float:
    """确定性"来源支撑度"：输出中多少内容特征能在检索上下文中找到（0-100）。

    输出大量编造、与知识库无关时趋近 0；完全照应知识库时趋近 100。
    """
    if not output or not context:
        return 0.0
    out_fp = ngram_fingerprint(output)
    if not out_fp:
        return 0.0
    ctx_fp = ngram_fingerprint(context)
    if not ctx_fp:
        return 0.0
    hit = sum(1 for k in out_fp if k in ctx_fp)
    return round(hit / len(out_fp) * 100, 1)


def _build_faithfulness_messages(output: str, context: str) -> list[dict]:
    system = (
        "你是严格的 RAG 忠实度评审员。请判断模型输出是否完全被提供的知识库上下文所支撑，"
        "即输出中是否存在知识库中找不到的编造/臆断信息。"
        "输出必须为JSON对象：{\"score\": 0-100, \"reason\": \"<简述是否忠实及扣分点>\"}。"
    )
    user = (
        f"【知识库上下文】\n{context}\n\n"
        f"【模型输出】\n{output}\n\n"
        "请给出忠实度打分（0-100）：80+完全被支撑，60-79基本支撑但有小偏差，"
        "40-59部分支撑存在明显臆断，<40 大量编造。并说明依据。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def faithfulness_score(task, output: str, context: str,
                             client=None) -> tuple[float, str]:
    """RAG 忠实度评测：LLM 打分（失败时回退到 source_support）。"""
    if not output or not context:
        return 0.0, "缺少输出或上下文，无法评测"
    client = client or get_llm_client()
    try:
        data = await client.chat_json(
            messages=_build_faithfulness_messages(output, context),
            model=(task.judge_model or task.execution_model or ""),
            temperature=0.2, max_tokens=500, json_mode=True,
        )
        if isinstance(data, str):
            data = json.loads(data)
        score = float(data.get("score", 0))
        score = max(0, min(100, score))
        return round(score, 1), str(data.get("reason", ""))[:500]
    except Exception as exc:  # noqa: BLE001
        # LLM 评审不可用时用确定性来源支撑度作为软回退
        fallback = source_support(output, context)
        return fallback, f"LLM 忠实度评审失败，采用来源支撑度：{exc}"