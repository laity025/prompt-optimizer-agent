# ==========================================================
# 知识库（RAG 检索评测）接口
#   建库/列表/详情/删除、上传语料、一键导入示例语料目录、检索预览、RAG 忠实度评测
# ==========================================================
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.exceptions import not_found, state_error
from app.db.base import get_db
from app.llm.client import get_llm_client
from app.models import KnowledgeBase, KnowledgeDoc, User
from app.services import rag_service

router = APIRouter(prefix="/knowledge-bases", tags=["知识库"])
settings = get_settings()


# ---------- 请求体 ----------
class KBCreateReq(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)


class DocCreateReq(BaseModel):
    title: str = Field(default="", max_length=255)
    content: str = Field(min_length=1, max_length=500000, description="语料正文")


class DocsBulkReq(BaseModel):
    docs: list[DocCreateReq]


class RetrieveReq(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=10)


class EvaluateReq(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=10)
    model: str | None = Field(default=None, description="生成答案所用模型；缺省用默认")


class CorpusImportReq(BaseModel):
    dir: str = Field(default="", description="要导入的语料目录，留空使用配置的 RAG_CORPUS_DIR")


# ---------- 知识库 CRUD ----------
@router.post("", summary="创建知识库")
def create_kb(body: KBCreateReq, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    kb = rag_service.create_kb(db, user.id, body.name, body.description)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return {"code": 0, "message": "success", "data": _kb_view(db, kb)}


@router.get("", summary="我的知识库列表")
def list_kbs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user.id)\
        .order_by(KnowledgeBase.id.desc()).all()
    return {"code": 0, "message": "success", "data": {
        "items": [_kb_view(db, kb) for kb in rows], "total": len(rows),
    }}


@router.get("/{kb_id}", summary="知识库详情")
def kb_detail(kb_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    kb = rag_service.get_kb_owned(db, kb_id, user.id)
    docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.kb_id == kb_id)\
        .order_by(KnowledgeDoc.id.desc()).all()
    return {"code": 0, "message": "success", "data": {
        **_kb_view(db, kb),
        "docs": [{
            "id": d.id, "title": d.title, "status": d.status, "error": d.error,
            "content": d.content[:200], "created_at": d.created_at,
        } for d in docs],
    }}


@router.delete("/{kb_id}", summary="删除知识库")
def delete_kb(kb_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    kb = rag_service.get_kb_owned(db, kb_id, user.id)
    # 若有任务绑定该库，解绑并关闭其 RAG 开关，避免遗留悬空外键引用
    from sqlalchemy import update
    from app.models import Task

    db.execute(
        update(Task).where(Task.kb_id == kb_id).values(kb_id=None, enable_rag=0)
        .execution_options(synchronize_session=False)
    )
    db.delete(kb)  # 级联删除文档与块
    db.commit()
    return {"code": 0, "message": "success", "data": {"id": kb_id}}


def _kb_view(db, kb) -> dict:
    """知识库视图（列表项与详情共用）。"""
    return {
        "id": kb.id, "name": kb.name, "description": kb.description,
        "embed_model": kb.embed_model, "doc_count": kb.doc_count,
        "chunk_count": kb.chunk_count, "created_at": kb.created_at,
    }


# ---------- 语料入库 ----------
@router.post("/{kb_id}/docs", summary="上传/粘贴单篇语料")
async def add_doc(kb_id: int, body: DocCreateReq, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    kb = rag_service.get_kb_owned(db, kb_id, user.id)
    if not body.content.strip():
        raise state_error("语料内容不能为空")
    info = await rag_service.add_document(
        db, kb, title=body.title or f"文档{kb.chunk_count + 1}",
        content=body.content, embed_model=kb.embed_model,
    )
    return {"code": 0, "message": "success", "data": info}


@router.post("/{kb_id}/docs/bulk", summary="批量导入多篇语料")
async def add_docs_bulk(kb_id: int, body: DocsBulkReq,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    kb = rag_service.get_kb_owned(db, kb_id, user.id)
    success = failed = 0
    errors: list[str] = []
    for d in body.docs:
        try:
            if not d.content.strip():
                raise state_error("空文档")
            await rag_service.add_document(
                db, kb, title=d.title or f"文档{kb.chunk_count + 1}",
                content=d.content, embed_model=kb.embed_model,
            )
            success += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append(f"{d.title or '文档'}: {exc}")
    return {"code": 0, "message": "success", "data": {
        "success": success, "failed": failed, "errors": errors[:20],
    }}


@router.post("/{kb_id}/import-corpus", summary="一键导入示例语料库目录")
async def import_corpus(kb_id: int, body: CorpusImportReq,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    kb = rag_service.get_kb_owned(db, kb_id, user.id)
    # 安全限制：仅允许导入配置的 RAG_CORPUS_DIR 语料目录，拒绝任意路径以避免任意文件读取
    cfg_dir = (settings.RAG_CORPUS_DIR or "").strip()
    if body.dir.strip():
        if not cfg_dir:
            raise state_error("未配置 RAG_CORPUS_DIR，不允许指定任意目录")
        if Path(body.dir.strip()).resolve() != Path(cfg_dir).resolve():
            raise state_error("仅允许从配置的 RAG_CORPUS_DIR 目录导入语料")
        corpus_dir = body.dir.strip()
    else:
        corpus_dir = cfg_dir
    if not corpus_dir:
        raise state_error("未配置语料目录：请设置 RAG_CORPUS_DIR")
    path = Path(corpus_dir)
    if not path.exists() or not path.is_dir():
        raise not_found("语料目录不存在")
    files = sorted([f for f in path.glob("*.md") if f.is_file()])
    if not files:
        raise state_error("目录下未找到 .md 语料文件")

    success = failed = 0
    errors: list[str] = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            if not text.strip():
                continue
            await rag_service.add_document(
                db, kb, title=f.stem, content=text, embed_model=kb.embed_model,
            )
            success += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append(f"{f.stem}: {exc}")
    return {"code": 0, "message": "success", "data": {
        "success": success, "failed": failed, "total": len(files), "errors": errors[:20],
    }}


# ---------- 检索与 RAG 评测 ----------
@router.post("/{kb_id}/retrieve", summary="检索预览")
async def retrieve_preview(kb_id: int, body: RetrieveReq,
                           user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    kb = rag_service.get_kb_owned(db, kb_id, user.id)
    retrieve = rag_service.build_retriever(db, kb_id)
    hits = await retrieve(body.query, body.top_k)
    return {"code": 0, "message": "success", "data": {
        "kb_id": kb_id, "query": body.query,
        "embed_model": kb.embed_model, "hits": hits,
    }}


@router.post("/{kb_id}/evaluate", summary="RAG 检索+生成评测")
async def rag_evaluate(kb_id: int, body: EvaluateReq,
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """检索 → 注入上下文生成答案 → 计算来源支撑度与忠实度。"""
    kb = rag_service.get_kb_owned(db, kb_id, user.id)
    retrieve = rag_service.build_retriever(db, kb_id)
    hits = await retrieve(body.query, body.top_k)
    if not hits:
        raise state_error("知识库为空，请先上传语料")

    context = rag_service.compose_context(hits)
    client = get_llm_client()
    answer = ""
    try:
        answer = await client.chat(
            messages=[
                {"role": "system", "content": (
                    "你是基于给定知识库作答的严谨问答助手。仅依据【检索到的知识】回答，"
                    "若知识不足以回答请明确说明，不得编造知识库外的信息。"
                )},
                {"role": "user", "content": f"【检索到的知识】\n{context}\n\n【问题】\n{body.query}"},
            ],
            model=body.model or "", temperature=0.3, max_tokens=1500, timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        answer = f"（生成失败：{exc}）"

    src_score = rag_service.source_support(answer, context)
    # 忠实度评测需要 task 对象取 judge 模型；此处用空壳对象提供 model 属性
    fh, reason = await rag_service.faithfulness_score(
        _JudgeTask(body.model), answer, context, client=client)

    return {"code": 0, "message": "success", "data": {
        "query": body.query, "embed_model": kb.embed_model,
        "answer": answer, "source_score": src_score,
        "faithfulness": {"score": fh, "reason": reason},
        "retrieved": [{
            "doc_title": h["doc_title"], "seq": h["seq"], "text": h["text"],
            "score": h["score"],
        } for h in hits],
    }}


class _JudgeTask:
    """供 faithfulness 评测占位使用的任务模型，仅提供 judge_model / execution_model。"""

    def __init__(self, model: str | None):
        self.judge_model = model or settings.LLM_DEFAULT_MODEL
        self.execution_model = self.judge_model