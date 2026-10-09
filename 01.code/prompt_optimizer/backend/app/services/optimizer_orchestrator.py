# ==========================================================
# LangGraph 迭代编排器：生成变体 → 执行任务 → 质量评估 → 择优更新 → 终止判断
# ==========================================================
import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import StateGraph

from app.core.progress import progress_tracker
from app.db.base import SessionLocal
from app.models import EvalResult, Iteration, PromptVersion, Task, TestCase, Variant
from app.services.executor import execute_cases
from app.services.judge_service import judge_output
from app.services.metrics_service import compute_metrics
from app.services.variant_generator import generate_variants

logger = logging.getLogger("orchestrator")


class OptimizationState(TypedDict):
    """迭代循环状态对象。"""

    task_id: int
    round: int                      # 当前轮（1-based）
    base_prompt: str                # 本轮基准提示词
    best_score: float               # 当前最优综合得分
    fail_cases: list[dict]          # 上一轮低分案例 [{case_id, input, output, reason}]
    stop_flag: bool                 # 是否应停止
    t: int                          # 已连续滞涨轮数
    terminating: str | None         # 终止原因 description/text/condition


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _json_loads_fallback(s: str | None, default: Any = None) -> Any:
    try:
        return json.loads(s) if s else default
    except Exception:  # noqa: BLE001
        return default


def _load_cases(db, task_id: int) -> list[TestCase]:
    return db.query(TestCase).filter(TestCase.task_id == task_id).order_by(TestCase.id).all()


# ---------- 主体锚定：防止优化器把核心主体整体改写掉（如橘猫 → 山水画） ----------
# 切分：标点/虚词/常见动词作为分隔符，拆出有语义的名词性短语
_ANCHOR_SPLIT = re.compile(
    r"[，。；、,\.!?！？' \"“”‘’「」（）()《》<>:：/\s\-｜|~～]+"
    r"|[的地得着了过着在与及或而是却则都又很太最较更或将让要把被对从向为为了给以于之等的了吗呢吧啊罢了哦你你我我他她它这个那个这些那些]"
    r"|躺|站|坐|抱|卧|趴|望|看|听|说|写|画|涂|描|想|希望|需要|正在|想要|能够|可以|应该|属于|变成|成为"
    r"|上下里外中内左右前后旁边面处"
)
_ANCHOR_FUNC = {"一只", "一个", "一条", "一些", "等等", "例如", "因为", "所以", "但是", "如果", "并且", "而且", "如何", "以及"}
_ANCHOR_QUANT = ("一只", "一个", "一条", "一些", "这群", "那片", "这份")


def extract_case_keywords(cases: list[TestCase]) -> list[str]:
    """收集所有用例的关键词（用户显式给出的强制主体）。"""
    kws: set[str] = set()
    for c in cases:
        for kw in _json_loads_fallback(c.keywords, []):
            k = str(kw).strip()
            if 1 <= len(k) <= 8:
                kws.add(k)
    return sorted(kws)


def extract_anchors(task, cases: list[TestCase]) -> list[str]:
    """提取供 LLM 阅读的"需强制保留主体词"清单（用于变体生成/评审提示）：
    - 用例关键词（硬约束）
    - 初始提示词中的名词性短语（兜底，避免主体被优化丢弃）
    仅从初始提示词与关键词取，不把目标/标准这类指令性文本当作主体词。
    """
    anchors: set[str] = set(extract_case_keywords(cases))
    for seg in _ANCHOR_SPLIT.split(task.initial_prompt or ""):
        tok = seg.strip()
        for q in _ANCHOR_QUANT:
            if tok.startswith(q):
                tok = tok[len(q):]
        if 2 <= len(tok) <= 8 and tok not in _ANCHOR_FUNC:
            anchors.add(tok)
    # 去噪：若某词是另一更长词的子串，保留更短更具体的那个（避免“猫窝上/猫窝”并存）
    kept = []
    for a in sorted(anchors, key=len):
        if not any(a != b and a in b for b in anchors):
            kept.append(a)
    return sorted(kept)


def _bigram_sim(a: str, b: str) -> float:
    """字符二元组重叠度（0-1）：衡量两个文本的内容相似度，中文下比整串匹配更稳。"""
    def grams(s: str) -> set[str]:
        s = "".join(ch for ch in (s or "") if not ch.isspace())
        return {s[i:i + 2] for i in range(len(s) - 1)}
    ga, gb = grams(a), grams(b)
    inter = ga & gb
    denom = ga | gb
    return len(inter) / len(denom) if denom else 0.0


def anchor_factor(prompt_text: str, initial_prompt: str | None, case_keywords: list[str]) -> float:
    """主体保留系数（0.6 ~ 1.0）：
    - 存在用例关键词：作为显式硬约束，缺失则按保留比例打折；
    - 无关键词：以与初始提示词的内容重叠兜底，仅对“走题到几乎无重叠”的变体打重折，
      从而拦住把核心主体整体替换成无关内容（如橘猫 → 山水画）的候选。
    """
    prompt_text = prompt_text or ""
    kws = [k for k in case_keywords if k]
    if kws:
        keep = sum(1 for k in kws if k in prompt_text) / len(kws)
        return round(0.6 + 0.4 * keep, 3)
    if initial_prompt and _bigram_sim(prompt_text, initial_prompt) < 0.15:
        return 0.6
    return 1.0


def _compute_auto_score(res, task: Task) -> float | None:
    """计算自动指标合成分（0-100）。

    - 有参考输出：BLEU/ROUGE/关键词/单测取可用均值；
    - 无参考输出：仍以关键词命中等可用信号参与合成，
      保证 auto_weight 在无参考输出时依然生效（修复此前权重被清零的问题）；
    - 抽取/代码等格式敏感任务：格式不合规直接判 0，避免"非空即高分"；
    - 抽取任务进一步把"格式合规"计入平均值，强化 JSON 合法性对得分的影响。
    """
    # 格式敏感任务（抽取/代码）输出不合法 JSON 或空时，自动分直接置 0
    if task.task_type in ("extraction", "code") and res.format_ok == 0:
        return 0.0
    vals = [v for v in (res.bleu, res.rouge, res.keyword_hit, res.unit_pass_rate) if v is not None]
    # 抽取任务：格式合规（合法 JSON）是硬性要求，纳入平均强化其影响
    if task.task_type == "extraction" and res.format_ok is not None:
        vals.append(res.format_ok * 100)
    return sum(vals) / len(vals) if vals else None


# ---------- 节点 1：生成变体 ----------
async def _gen_variants(state: OptimizationState) -> dict:
    """基于当前最优先生成当前轮全部变体并落库。"""
    task_id = state["task_id"]
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        base_prompt = state["base_prompt"]
        count = task.variants_per_round

        # 轮次递增：start_round 传入时 round=start_round-1，进入生成时 +1 得到本轮实际轮次
        round_no = state["round"] + 1

        # 幂等化：单轮失败重试时可能再次进入本节点，若该轮已存在 iteration 则复用并清空其旧变体/评审，
        # 避免每次重试都新增一条同轮记录，造成 completed+running 成对、数据库被重复记录污染。
        iteration = db.query(Iteration).filter(
            Iteration.task_id == task_id, Iteration.round_no == round_no
        ).first()
        if iteration is None:
            iteration = Iteration(
                task_id=task_id,
                round_no=round_no,
                base_prompt=base_prompt,
                status="running",
            )
            db.add(iteration)
            db.commit()
            db.refresh(iteration)
        else:
            for old_v in db.query(Variant).filter(Variant.iteration_id == iteration.id).all():
                db.query(EvalResult).filter(EvalResult.variant_id == old_v.id).delete()
                db.delete(old_v)
            iteration.base_prompt = base_prompt
            iteration.status = "running"
            iteration.best_variant_id = None
            iteration.best_score = None
            iteration.finished_at = None
            db.commit()

        # 生成变体（含失败案例注入 + 强制主体锚定）
        cases = _load_cases(db, task_id)
        anchors = extract_anchors(task, cases)
        variants = await generate_variants(
            base_prompt=base_prompt,
            task=task,
            fail_cases=state["fail_cases"],
            count=count,
            anchors=anchors,
        )
        progress_tracker.update(task_id, status="running", current_round=round_no,
                                variants_total=len(variants), variants_done=0)
        for i, v in enumerate(variants, start=1):
            db.add(Variant(
                iteration_id=iteration.id,
                variant_no=i,
                prompt_text=v["prompt"],
                strategy_tag=v["strategy_tag"],
                status="pending",
            ))
        db.commit()
        return {"round": round_no, "iteration_id": iteration.id}
    finally:
        db.close()


# ---------- 横向归一化：消除评审员轮间尺度漂移 ----------
def _normalize_case_judge(scores: dict[int, float]) -> dict[int, float]:
    """对「同一用例、本轮 N 个变体」的评审分做横向归一化，消除轮间尺度漂移。

    背景：LLM 评审员给分存在『轮间尺度漂移』——同一 baseline 提示词在不同轮次
    被评出 20 与 90；且整轮协同偏高/偏低。单纯多次抽样求均值只能降噪声，无法
    消除轮间系统性的尺度偏移（均值仍随评审尺度整体平移）。

    做法：对同一用例内本轮全部变体的评审分做 z-score，再重映射回固定中心 5.5、
    范围 ±4.5、clamp [1,10] 的可读分。这样每轮分数以同一中心分布，保留变体间
    相对优劣，best 得分曲线由『变体相对改进』驱动，而非评审尺度漂移驱动。

    :param scores: {variant_id: judge_score(1-10)}
    :return: {variant_id: normalized(1-10)}
    """
    if len(scores) < 2:
        return dict(scores)  # 单一变体无可横向比较，保留原分避免误伤
    values = list(scores.values())
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    std = var ** 0.5
    if std < 1e-6:
        return {k: 5.5 for k in scores}  # 全变体同分，认为无差异，居中
    out = {}
    for k, v in scores.items():
        z = max(-1.5, min(1.5, (v - mean) / std))   # clamp 防单点离群暴走
        out[k] = round(5.5 + (z / 1.5) * 4.5, 2)    # [-1.5,1.5] -> [1.0,10.0]
    return out


# ---------- 节点 2：执行任务 + 质量评估 ----------
async def _execute_and_eval(state: OptimizationState) -> dict:
    """对每轮全部变体执行全部用例，计算自动指标 + 评审打分 + 横向归一化 + 合成综合得分。

    流程（三阶段）：
    1) 收集：执行全部变体，对每个 (variant, case) 计算自动指标并评审 1-10 分（含缓存去重）；
    2) 归一化：对『同一用例、本轮全部变体』的评审分做横向归一化，消除评审员轮间尺度漂移
       （同一 baseline 变体在不同轮次被评出 20 vs 90 且整轮协同偏移的症状）；
    3) 入库：用归一化后的评审分合成综合得分并写 EvalResult / 汇总变体分。
    """
    task_id = state["task_id"]
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        cases = _load_cases(db, task_id)
        if not cases:
            raise ValueError("任务无测试用例，无法迭代")
        anchors = extract_anchors(task, cases)
        case_keywords = extract_case_keywords(cases)

        iteration = db.query(Iteration).filter(
            Iteration.task_id == task_id, Iteration.round_no == state["round"]
        ).first()
        variants = db.query(Variant).filter(Variant.iteration_id == iteration.id).order_by(Variant.variant_no).all()

        inputs = [{"case_id": c.id, "input_text": c.input_text} for c in cases]
        progress_tracker.update(task_id, cases_total=len(cases))

        # 本轮评审缓存：相同的（提示词+输入+输出）复用同一评审结果
        judge_cache: dict[str, tuple[int, str]] = {}

        # ---- 阶段 1：执行 + 自动指标 + 原始评审（全部收集到内存，暂不写库）----
        # 结构索引：per_ev[vid][case_id] = {metric, output, err, judge_score, judge_reason}
        per_ev: dict[int, dict[int, dict]] = {}

        for vi, variant in enumerate(variants, start=1):
            variant.status = "running"
            db.commit()

            exec_results = await execute_cases(
                prompt=variant.prompt_text,
                inputs=inputs,
                task=task,
                concurrency=task.concurrency,
            )
            exec_map = {r["case_id"]: r for r in exec_results}

            per_ev[variant.id] = {}
            for case in cases:
                er = exec_map.get(case.id)
                output = er["output"] if er else ""
                err = er["error_reason"] if er else "执行失败"
                keywords = _json_loads_fallback(case.keywords, [])
                run_test = _json_loads_fallback(case.run_test, {})
                metric = compute_metrics(
                    task.task_type, output or "", case.reference_output, keywords, run_test
                )
                if err:
                    per_ev[variant.id][case.id] = {
                        "metric": metric, "output": output, "err": err,
                        "judge_score": None, "judge_reason": None,
                    }
                    continue
                judge_key = f"{variant.prompt_text}\u0001{case.input_text}\u0001{output}"
                if judge_key in judge_cache:
                    judge_score, judge_reason = judge_cache[judge_key]
                else:
                    judge_score, judge_reason = await judge_output(
                        task=task, prompt=variant.prompt_text,
                        input_text=case.input_text, output=output,
                        reference=case.reference_output,
                        anchors=anchors,
                    )
                    judge_cache[judge_key] = (judge_score, judge_reason)
                per_ev[variant.id][case.id] = {
                    "metric": metric, "output": output, "err": None,
                    "judge_score": judge_score, "judge_reason": judge_reason,
                }
                progress_tracker.update(task_id, cases_done=(vi - 1) * len(cases) + 1)  # 粗略进度

        # ---- 阶段 2：按 case 横向归一化评审分 ----
        # normalized[case_id][variant_id] = 1-10 归一分
        normalized: dict[int, dict[int, float]] = {}
        for case in cases:
            subj = {vid: ev[case.id]["judge_score"] for vid, ev in per_ev.items()
                    if case.id in ev and ev[case.id]["err"] is None}
            if subj:
                normalized[case.id] = _normalize_case_judge(subj)

        # ---- 阶段 3：写 EvalResult + 汇总变体分 ----
        for vi, variant in enumerate(variants, start=1):
            scores: list[float] = []
            for ci, case in enumerate(cases, start=1):
                ev = per_ev[variant.id].get(case.id)
                if ev is None:
                    continue
                metric = ev["metric"]
                if ev["err"]:
                    db.add(EvalResult(
                        variant_id=variant.id, test_case_id=case.id,
                        model_output=ev["output"], outcome="failed",
                        error_reason=ev["err"], total_score=0.0,
                    ))
                    db.commit()
                    continue

                raw_score = ev["judge_score"]
                norm_score = normalized.get(case.id, {}).get(variant.id, float(raw_score or 0))
                # 合成综合得分（横向归一化后的评审分参与）
                auto_score = _compute_auto_score(metric, task)
                judge_0to100 = norm_score * 10
                use_auto = task.auto_weight if auto_score is not None else 0.0
                denom = use_auto + task.judge_weight
                total = (
                    (use_auto * (auto_score or 0) + task.judge_weight * judge_0to100) / denom
                    if denom > 0 else judge_0to100
                )
                db.add(EvalResult(
                    variant_id=variant.id, test_case_id=case.id,
                    model_output=ev["output"], outcome="success",
                    bleu=metric.bleu, rouge=metric.rouge, keyword_hit=metric.keyword_hit,
                    format_ok=metric.format_ok,
                    judge_score=int(round(norm_score)) if norm_score is not None else None,
                    judge_reason=ev["judge_reason"],
                    total_score=round(total, 2),
                ))
                db.commit()
                scores.append(total)
                prog = progress_tracker.get(task_id)
                progress_tracker.update(
                    task_id, variants_done=vi,
                    cases_success=(prog.cases_success + 1) if prog else 0,
                )

            # 汇总变体综合得分（取全部用例得分均值），并按主体保留系数打折
            variant.score = round(sum(scores) / len(scores), 2) if scores else 0.0
            if variant.score:
                variant.score = round(
                    variant.score * anchor_factor(variant.prompt_text, task.initial_prompt, case_keywords), 2
                )
            variant.status = "completed" if scores else "failed"
            db.commit()

        progress_tracker.update(task_id, variants_done=len(variants))

        # 4) 确定本轮最优变体
        done = [v for v in variants if v.score is not None]
        if not done:
            iteration.status = "failed"
            db.commit()
            return {"best_score": state["best_score"], "fail_cases": []}
        best = max(done, key=lambda v: v.score)
        iteration.best_variant_id = best.id
        iteration.best_score = best.score
        iteration.status = "completed"
        iteration.finished_at = _now()
        db.commit()

        # 收集本轮薄弱用例用于下轮定向改进：
        # 自适应阈值 = max(60, 本轮最优变体得分×0.7)，适配任务难度；按 case 聚合取最失败的用例
        threshold = max(60.0, best.score * 0.7) if best.score else 60.0
        worst_by_case: dict[int, dict] = {}
        for v in done:
            if v.score is None or v.score >= best.score:
                continue
            for e in db.query(EvalResult).filter(EvalResult.variant_id == v.id).all():
                if e.total_score is None or e.total_score >= threshold:
                    continue
                prev = worst_by_case.get(e.test_case_id)
                if prev is not None and e.total_score >= prev["score"]:
                    continue
                c = db.get(TestCase, e.test_case_id)
                worst_by_case[e.test_case_id] = {
                    "case_id": e.test_case_id,
                    "score": e.total_score,
                    "input": c.input_text if c else "",
                    "output": e.model_output,
                    "reason": e.judge_reason,
                }
        fail_cases = sorted(worst_by_case.values(), key=lambda x: x["score"])[:5]
        # 供 LLM 的失败载荷内 score 无意义，仅用于排序，剔除后返回
        for f in fail_cases:
            f.pop("score", None)
        return {"best_score": best.score, "fail_cases": fail_cases, "best_variant_id": best.id}
    finally:
        db.close()


# ---------- 节点 3：择优更新 ----------
def _update_best(state: OptimizationState) -> dict:
    """将本轮最优写入任务/版本库，并据此判断滞涨。"""
    task_id = state["task_id"]
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        iteration = db.query(Iteration).filter(
            Iteration.task_id == task_id, Iteration.round_no == state["round"]
        ).first()
        if iteration is None or iteration.best_variant_id is None:
            return {"terminating": "failed"}
        best = db.get(Variant, iteration.best_variant_id)
        new_score = iteration.best_score or 0.0
        old_score = task.best_score if task.best_score is not None else 0.0

        improved = new_score > old_score
        if improved:
            task.best_prompt = best.prompt_text
            task.best_score = new_score

        # 回写当前轮次，保证断点续跑起点与前端展示准确
        task.current_round = state["round"]

        # 记录版本（每轮记录最优版）
        db.add(PromptVersion(
            task_id=task_id,
            version_no=state["round"],
            prompt_text=best.prompt_text,
            is_best=int(improved),
            score=new_score,
            parent_version_id=None,
        ))
        db.commit()

        # 滞涨判断：若未提升，滞涨计数+1
        stagnant = 0 if improved else 1
        return {
            "best_score": new_score,
            "t": stagnant,
            "terminating": None,
        }
    finally:
        db.close()


# ---------- 节点 4：终止判断 ----------
def _decide(state: OptimizationState) -> dict:
    """将终止判定结果写入状态 (terminating key)。"""
    return {"terminating": _evaluate_termination(state)}


def _evaluate_termination(state: OptimizationState) -> Literal["stop", "target", "max_round", "stagnant", "failed", ""]:
    """判定应继续还是终止，写入任务状态。返回空串表示继续。"""
    task_id = state["task_id"]
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if task is None:
            return ""
        # 用户停止请求：优先检查数据库状态（stop 接口已写入 stopped）
        # 与内存 stop_flag 双保险，保证运行中的 LangGraph 循环能被中断
        if state.get("stop_flag") or task.status == "stopped":
            task.status = "stopped"
            task.updated_at = _now()
            db.commit()
            return "stop"
        if state.get("terminating") == "failed":
            task.status = "failed"
            db.commit()
            return "failed"
        # 达到目标分
        if task.best_score is not None and task.target_score and task.best_score >= task.target_score:
            task.status = "completed"
            task.updated_at = _now()
            db.commit()
            return "target"
        # 达到最大轮次
        if state["round"] >= task.max_rounds:
            task.status = "completed"
            task.updated_at = _now()
            db.commit()
            return "max_round"
        # 连续滞涨达到阈值
        if state.get("t", 0) >= task.stagnant_rounds:
            task.status = "completed"
            task.updated_at = _now()
            db.commit()
            return "stagnant"
        return ""  # 继续
    finally:
        db.close()


# 说明：单轮图的轮次推进与终止判断由 run_iteration_task 外层循环 + decide 节点完成，
# 原自循环条件边使用的 _route 不再需要。


# ---------- 状态图构建 ----------
def build_optimization_graph():
    """构建「单轮」优化图：gen → eval → update → decide → end。

    历史实现是自循环图（decide 后回 gen 直到终止），一旦某轮抛异常，整个 ainvoke
    失败后从头重跑全部轮次，产生大量重复记录。现改为单轮图，轮次推进与单轮重试
    交给 run_iteration_task 外层循环驱动，某轮失败只重试当轮，避免污染数据库。
    """
    graph = StateGraph(OptimizationState)

    graph.add_node("gen", _gen_variants)
    graph.add_node("eval", _execute_and_eval)
    graph.add_node("update", _update_best)
    graph.add_node("decide", _decide)

    graph.set_entry_point("gen")
    graph.add_edge("gen", "eval")
    graph.add_edge("eval", "update")
    graph.add_edge("update", "decide")
    graph.add_edge("decide", "__end__")

    return graph.compile()


_compiled = None


def get_compiled_graph():
    """缓存编译后的单轮图实例。"""
    global _compiled
    if _compiled is None:
        _compiled = build_optimization_graph()
    return _compiled


async def run_iteration_task(task_id: int, start_round: int, resume: bool = False) -> None:
    """异步入口：外层逐轮推进 + 单轮失败重试，直至 decide 返回终止原因。

    每轮调用一次单轮图（gen→eval→update→decide）；若当轮抛出瞬时 LLM 异常则重试当轮，
    避免把前面已完成的轮次从头重跑而在数据库留下重复记录。
    """
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if task is None:
            return
        task.status = "running"
        task.updated_at = _now()
        db.commit()

        # 起始基准提示词：若 best_prompt 为空，先确保初始提示词
        base_prompt = task.best_prompt or task.initial_prompt or await _auto_seed_prompt(task, db)
        if task.best_prompt is None:
            task.best_prompt = base_prompt
            db.commit()
    finally:
        db.close()

    graph = get_compiled_graph()  # 单轮图
    state: OptimizationState = {
        "task_id": task_id,
        # round 表示「已完成轮次」，gen 节点会自增；首轮从 start_round-1 进入以得到 start_round
        "round": start_round - 1,
        "base_prompt": base_prompt,
        "best_score": 0.0,
        "fail_cases": [],
        "stop_flag": False,
        "t": 0,
        "terminating": None,
    }
    # 单轮失败自动重试：偶发的瞬时 LLM 故障（超时/断连/限流）只重试当轮，
    # 首次 + 重试合计至多 MAX_ROUND_RETRIES+1 次。
    MAX_ROUND_RETRIES = 2
    while True:
        last_exc: Exception | None = None
        for attempt in range(MAX_ROUND_RETRIES + 1):
            try:
                state = await graph.ainvoke(state)
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("任务 %s 第 %s 轮失败(%s/%s 次)：%s",
                               task_id, state["round"] + 1, attempt + 1, MAX_ROUND_RETRIES + 1, exc)
                if attempt < MAX_ROUND_RETRIES:
                    await asyncio.sleep(2.0 + attempt)

        if last_exc is not None:
            # 当轮重试耗尽，标记失败并写入错误原因，避免任务永远停留在 running
            logger.exception("任务 %s 第 %s 轮重试耗尽，最终失败", task_id, state["round"] + 1)
            db = SessionLocal()
            try:
                task = db.get(Task, task_id)
                if task is not None:
                    task.status = "failed"
                    task.last_error = f"{type(last_exc).__name__}: {last_exc}"[:500]
                    task.updated_at = _now()
                    db.commit()
                progress_tracker.update(task_id, status="failed", message=str(last_exc))
            finally:
                db.close()
            return

        # decide 已按终止原因写任务状态（completed/stopped/failed），退出外层循环
        if state.get("terminating"):
            return

        # 继续下一轮：仅更新迭代结果，round 保持上一轮 ainvoke 返回的「已完成轮次」不变，
        # 由 gen 节点内部再 +1 得到下一轮号；若在此 +1 会与 gen 内 +1 叠加，导致轮次跳号（如 1、3 缺 2）。
        state = {
            "task_id": task_id,
            "round": state["round"],
            "base_prompt": state["base_prompt"],
            "best_score": state.get("best_score", 0.0),
            "fail_cases": state.get("fail_cases", []),
            "stop_flag": state.get("stop_flag", False),
            "t": state.get("t", 0),
            "terminating": None,
        }


async def _auto_seed_prompt(task: Task, db) -> str:
    """当任务未填初始提示词时，按任务描述生成初始提示词并落库为第0版。"""
    from app.llm.client import get_llm_client

    client = get_llm_client()
    try:
        data = await client.chat_json(
            messages=[
                {"role": "system", "content": "你是提示词撰写专家，根据任务信息生成一份可直接用于执行的初始提示词。返回JSON {\"prompt\":\"内容\"}。"},
                {"role": "user", "content": f"任务类型：{task.task_type}\n描述：{task.description}\n目标：{task.objective}\n标准：{task.criteria}"},
            ],
            model=task.execution_model or "",
            temperature=0.7,
            max_tokens=1500,
            json_mode=True,
        )
        prompt = data.get("prompt", "")
    except Exception:  # noqa: BLE001
        # 降级：用结构化的通用模板
        prompt = (
            f"你是{task.name}的执行助手。\n任务说明：{task.description}\n"
            f"优化目标：{task.objective}\n请严格遵循：{task.criteria}。"
        )
    if not task.initial_prompt:
        task.initial_prompt = prompt
        db.commit()
    return prompt