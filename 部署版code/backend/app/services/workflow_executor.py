# ==========================================================
# 多步工作流执行与评测服务
#   - 链式执行：Step N 输出存入命名变量，Step N+1 用 {{input}}/{{stepN.out}} 占位符插值
#   - 末步输出为最终结果；评测复用 compute_metrics + judge_output + 权重合成（口径同主流程）
#   - 可选：以任务最优/初始 prompt 跑「单 prompt」基线，产出的端到端对比
# ==========================================================
import asyncio
import json
import logging
import re
from datetime import datetime

from sqlalchemy import update

from app.core.config import get_settings
from app.db.base import SessionLocal
from app.models import Task, TestCase, Workflow, WorkflowResult, WorkflowRun
from app.services.executor import execute_single
from app.services.judge_service import judge_output
from app.services.metrics_service import compute_metrics
from app.services.optimizer_orchestrator import _compute_auto_score, extract_anchors

_settings = get_settings()

logger = logging.getLogger("workflow")

# 占位符：{input} / {stepN.out}；规范化到小写键名匹配
_VAR_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def _now() -> str:
    """记录完成的 ISO 时间戳。"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _json_loads_fallback(s: str | None, default: object):
    """安全解析 JSON 文本，失败返回默认值。"""
    try:
        return json.loads(s) if s else default
    except Exception:  # noqa: BLE001
        return default


def interpolate(template: str, variables: dict[str, str]) -> str:
    """把模板中的 {{var}} 占位符替换为已完成的变量值；缺失变量替换为空串。"""
    def _sub(m: re.Match) -> str:
        key = m.group(1).strip().lower()
        return variables.get(key, "")
    return _VAR_RE.sub(_sub, template or "")


def _step_system(task_type: str) -> str:
    """工作流步骤的系统提示：对特定任务类型给出输出格式约束（复用主链路约定）。"""
    system = "你是本工作流步骤的执行器，严格遵循下列指令完成处理并直接给出最终结果，不要额外解释过程。"
    if task_type == "extraction":
        system += " 若需要JSON输出，请直接返回合法的JSON对象。"
    elif task_type == "code":
        system += " 请只返回Python代码。"
    elif task_type == "summary":
        system += " 请只返回摘要正文。"
    return system


async def _run_step(client, prompt_text: str, model: str, task_type: str,
                    timeout: int = 60, context: str | None = None) -> tuple[str, str]:
    """执行单步（对已插值完成的指令文本），返回 (output, error_reason)。

    client.chat 内部已带瞬时错误重试；此处仅兜底捕获非瞬时错误。
    context 为 RAG 检索到的参考知识，非空时注入并提示优先依据其作答（与主链路一致）。
    """
    user = prompt_text
    if context:
        user += (
            "\n\n【检索到的知识库上下文】\n" + context +
            "\n（请优先依据上述知识库上下文作答，仅当其中能找到支撑时引用其内容；"
            "知识不足时如实说明，不得编造知识库之外的信息。）"
        )
    try:
        out = await client.chat(
            messages=[
                {"role": "system", "content": _step_system(task_type)},
                {"role": "user", "content": user},
            ],
            model=model,
            temperature=0.4,
            max_tokens=2000,
            timeout=timeout,
        )
        return out, ""
    except Exception as exc:  # noqa: BLE001
        return "", f"{type(exc).__name__}: {exc}"


def build_report(db, run: WorkflowRun) -> dict:
    """由已落库的评测明细生成工作流通用报告数据结构。"""
    results = db.query(WorkflowResult).filter(WorkflowResult.run_id == run.id)\
        .order_by(WorkflowResult.test_case_id).all()
    wf = db.get(Workflow, run.workflow_id)
    steps = [{
        "seq": s.seq, "name": s.name, "output_var": s.output_var or f"step{s.seq}",
        "model": s.model or "",
    } for s in (wf.steps if wf else [])]

    cases = []
    for r in results:
        cases.append({
            "case_id": r.test_case_id, "input_text": r.input_text,
            "final_output": r.final_output, "error_reason": r.error_reason,
            "step_trace": _json_loads_fallback(r.step_trace, []),
            "bleu": r.bleu, "rouge": r.rouge, "keyword_hit": r.keyword_hit,
            "format_ok": r.format_ok, "judge_score": r.judge_score,
            "judge_reason": r.judge_reason, "total_score": r.total_score,
            "baseline_output": r.baseline_output, "baseline_score": r.baseline_score,
        })

    return {
        "run": {
            "id": run.id, "workflow_id": run.workflow_id, "task_id": run.task_id,
            "name": run.name, "status": run.status, "run_baseline": run.run_baseline,
            "avg_score": run.avg_score, "baseline_avg_score": run.baseline_avg_score,
            "created_at": run.created_at, "finished_at": run.finished_at,
        },
        "workflow": {"id": wf.id, "name": wf.name} if wf else None,
        "steps": steps,
        "cases": cases,
    }


async def run_workflow(run_id: int) -> None:
    """后台执行一次工作流评测：逐用例链式执行各步，末步输出评测 + 可选基线对照。

    流程（评测口径与主迭代/benchmark 一致，保证可比）：
      1) 对每个用例按步骤顺序插值执行，记录步骤输出追踪；
      2) 末步输出计算自动指标 + LLM 评审，按任务权重合成综合分；
      3) 若 run_baseline，以任务最优/初始 prompt 执行单 prompt 并评审，得到基线对照；
      4) 汇总平均分与基线平均分，落库。

    ⚠ 并发与事务约定：本函数让多个用例协程并发执行，但它们共享同一个 db Session。
      SQLAlchemy Session 非线程安全，为保证正确性，所有共享 Session 的数据库写操作
      （db.add / db.commit / db.flush / db.query 等）必须包裹在“无 await 的同步临界区”
      内——即在两次 await（LLM 调用）之间一次连续完成，避免协程交错破坏事务状态。
      新增任何 db 操作时务必保持此不变量，或改为每用例独立会话。
    """
    db = SessionLocal()
    try:
        run = db.get(WorkflowRun, run_id)
        if run is None:
            return
        wf = db.get(Workflow, run.workflow_id)
        task = db.get(Task, run.task_id)
        if wf is None or task is None:
            run.status = "failed"
            run.finished_at = _now()
            db.commit()
            return
        steps = sorted(wf.steps, key=lambda s: s.seq)
        if not steps:
            run.status = "failed"
            run.finished_at = _now()
            db.commit()
            return

        run.status = "running"
        run.finished_at = None
        db.commit()

        cases = db.query(TestCase).filter(TestCase.task_id == task.id)\
            .order_by(TestCase.id).all()
        baseline_prompt = task.best_prompt or task.initial_prompt or ""
        if run.run_baseline and not baseline_prompt:
            # 无基线 prompt 时仅跑工作流，避免空跑
            db.query(WorkflowRun).filter(WorkflowRun.id == run.id)\
                .update({"run_baseline": 0})
            db.commit()
            run.run_baseline = 0

        if not cases:
            run.status = "failed"
            run.finished_at = _now()
            db.commit()
            return

        anchors = extract_anchors(task, cases)
        sem = asyncio.Semaphore(task.concurrency or 2)
        score_sums = []
        baseline_sums = []

        # RAG 检索注入：任务开启 RAG 并绑定知识库时，为每个用例按输入检索并注入上下文。
        # 检索器在进入并发前一次性载入知识库全量块到内存，避免逐用例查询数据库。
        rag_retrieve = None
        if getattr(task, "enable_rag", 0) and getattr(task, "kb_id", None):
            from app.services import rag_service

            rag_retrieve = rag_service.build_retriever(db, task.kb_id)

        async def _one(c: TestCase) -> None:
            async with sem:
                await _eval_case(task, wf, run, c, steps, baseline_prompt,
                                 anchors, db, score_sums, baseline_sums, rag_retrieve)

        await asyncio.gather(*[_one(c) for c in cases])

        run.avg_score = round(sum(score_sums) / len(score_sums), 2) if score_sums else 0.0
        run.baseline_avg_score = (round(sum(baseline_sums) / len(baseline_sums), 2)
                                  if baseline_sums else None)
        run.status = "completed"
        run.finished_at = _now()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("工作流评测 %s 失败", run_id)
        db.rollback()
        try:
            db.execute(
                update(WorkflowRun).where(WorkflowRun.id == run_id)
                .values(status="failed", finished_at=_now())
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()


async def chain_execute_and_score(task, wf_name, steps, c: TestCase, anchors,
                                  rag_retrieve=None, run_baseline=False,
                                  baseline_prompt: str = "") -> dict:
    """对单个用例按给定步骤链执行并把末步输出评测为综合分（可复用于优化器变体评测）。

    :param steps: 步骤定义列表 [{seq, name, prompt_template, model, output_var}]，
                  优化器可通过替换其中目标步骤的 prompt_template 来实现「变体替换」。
    :return: {final_output, error_reason, total_score, judge_score, judge_reason,
              baseline_output, baseline_score}
    评测口径与 _eval_case 完全一致（自动指标 + LLM 评审 + 权重合成），不落库，由调用方决定。
    """
    from app.llm.client import get_llm_client

    client = get_llm_client()
    variables: dict[str, str] = {"input": c.input_text}
    trace: list[dict] = []
    final_out = ""
    final_err = ""

    context = None
    if rag_retrieve is not None:
        hits = await rag_retrieve(c.input_text, top_k=_settings.RAG_EVAL_TOP_K)
        if hits:
            from app.services import rag_service

            context = rag_service.compose_context(hits)

    for st in steps:
        prompt_text = interpolate(st["prompt_template"], variables)
        model = st.get("model") or task.execution_model or ""
        out, err = await _run_step(client, prompt_text, model, task.task_type,
                                   context=context)
        if st.get("seq"):
            trace.append({
                "seq": st["seq"], "name": st.get("name", ""),
                "output_var": st.get("output_var") or f"step{st['seq']}",
                "output": (out or "")[:2000],
            })
        if err:
            final_out, final_err = "", err
            break
        if st.get("seq"):
            variables[f"step{st['seq']}.out"] = out
        final_out = out

    baseline_out, baseline_score = "", None
    if run_baseline and baseline_prompt:
        bl_out, bl_err = await execute_single(
            client, baseline_prompt, c.input_text,
            model=task.execution_model or "", task_type=task.task_type,
            timeout=60, retries=2, context=context,
        )
        if not bl_err and bl_out:
            baseline_out = bl_out
            sc, _ = await judge_output(
                task=task, prompt=baseline_prompt, input_text=c.input_text,
                output=bl_out, reference=c.reference_output, anchors=anchors,
            )
            baseline_score = sc

    if final_err:
        return {"final_output": "", "error_reason": final_err, "total_score": 0.0,
                "judge_score": None, "judge_reason": None, "step_trace": trace,
                "baseline_output": baseline_out or None, "baseline_score": baseline_score}

    metric = compute_metrics(
        task.task_type, final_out or "", c.reference_output,
        _json_loads_fallback(c.keywords, []),
        _json_loads_fallback(c.run_test, {}),
    )
    judge_score, judge_reason = await judge_output(
        task=task, prompt=f"[工作流] {wf_name}", input_text=c.input_text,
        output=final_out, reference=c.reference_output, anchors=anchors,
    )
    auto = _compute_auto_score(metric, task)
    use_auto = task.auto_weight if auto is not None else 0.0
    denom = use_auto + task.judge_weight
    total = (((use_auto * (auto or 0) + task.judge_weight * (judge_score * 10)) / denom)
             if denom > 0 else judge_score * 10)

    return {"final_output": final_out, "error_reason": None, "total_score": total,
            "judge_score": judge_score, "judge_reason": judge_reason, "step_trace": trace,
            "metric": metric,
            "baseline_output": baseline_out or None, "baseline_score": baseline_score}


async def _eval_case(task, wf, run, c: TestCase, steps, baseline_prompt,
                     anchors, db, score_sums, baseline_sums, rag_retrieve=None) -> None:
    """评测单个用例：链式执行 + 末步评测 + 可选基线对照，写 WorkflowResult。

    rag_retrieve：RAG 检索函数（async），任务开启 RAG 时为用例输入检索一次参考上下文，
    注入到本用例全部步骤的执行消息中（与主链路一致）。
    评测口径复用 chain_execute_and_score，保证与优化器变体评测完全一致。
    """
    step_defs = [{"seq": s.seq, "name": s.name, "prompt_template": s.prompt_template,
                  "model": s.model, "output_var": s.output_var} for s in steps]
    res = await chain_execute_and_score(
        task, wf.name, step_defs, c, anchors,
        rag_retrieve=rag_retrieve,
        run_baseline=bool(run.run_baseline), baseline_prompt=baseline_prompt,
    )
    baseline_out = res.get("baseline_output")
    baseline_score = res.get("baseline_score")
    step_trace = json.dumps(res.get("step_trace") or [], ensure_ascii=False)

    if res.get("error_reason"):
        db.add(WorkflowResult(
            run_id=run.id, test_case_id=c.id, input_text=c.input_text,
            final_output="", error_reason=res["error_reason"],
            step_trace=step_trace,
            baseline_output=baseline_out or None, baseline_score=baseline_score,
            total_score=0.0,
        ))
        db.commit()
        # 失败用例：工作流分记 0；基线若不失败则计入基线均分，保证两边分母一致
        score_sums.append(0.0)
        if baseline_score is not None:
            baseline_sums.append(baseline_score)
        return

    metric = res.get("metric")
    total = float(res["total_score"])
    db.add(WorkflowResult(
        run_id=run.id, test_case_id=c.id, input_text=c.input_text,
        final_output=res["final_output"], error_reason=None,
        step_trace=step_trace,
        bleu=metric.bleu, rouge=metric.rouge, keyword_hit=metric.keyword_hit,
        format_ok=metric.format_ok, judge_score=round(res["judge_score"], 2),
        judge_reason=res["judge_reason"], total_score=round(total, 2),
        baseline_output=baseline_out or None, baseline_score=baseline_score,
    ))
    score_sums.append(total)
    if baseline_score is not None:
        baseline_sums.append(baseline_score)
    db.commit()