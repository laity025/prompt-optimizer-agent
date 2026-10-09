# ==========================================================
# 多模型横向对比评测服务：对同一任务、同一提示词，切换多个模型执行全部用例，
# 复用现有执行/指标/评审/横向归一化逻辑，产出各模型的综合得分对比
# ==========================================================
import json
import logging
from datetime import datetime
from typing import Any

from app.db.base import SessionLocal
from app.models import BenchmarkResult, BenchmarkRun, Task, TestCase
from app.services.executor import execute_cases
from app.services.judge_service import judge_output
from app.services.metrics_service import compute_metrics
from app.services.optimizer_orchestrator import (
    _compute_auto_score,
    _normalize_case_judge,
    extract_anchors,
)

logger = logging.getLogger("benchmark")


def _now() -> str:
    """记录完成的 ISO 时间戳。"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _json_loads_fallback(s: str | None, default: Any = None) -> Any:
    """安全解析 JSON 文本，失败返回默认值。"""
    try:
        return json.loads(s) if s else default
    except Exception:  # noqa: BLE001
        return default


def build_report(db, run: BenchmarkRun) -> dict:
    """由已落库的评测明细生成对比报告数据结构，供接口/导出复用。

    :return:
      run(运行信息)、models(各模型汇总)、cases(用例清单)、
      matrix(用例×模型得分矩阵)、models_order(参与对比的模型顺序)
    """
    results = db.query(BenchmarkResult).filter(BenchmarkResult.run_id == run.id).all()
    models = sorted({r.model for r in results})
    case_ids = sorted({r.test_case_id for r in results})

    # 各模型汇总：平均综合分、成功/失败用例数、平均关键词命中
    model_agg: dict[str, dict] = {m: {
        "model": m, "avg_score": None,
        "success_cases": 0, "failed_cases": 0, "avg_keyword_hit": None,
    } for m in models}
    total_keywords = {m: [] for m in models}
    for r in results:
        agg = model_agg[r.model]
        if r.total_score is not None:
            agg["success_cases"] += 1
            if agg["avg_score"] is None:
                agg["avg_score"] = 0.0
            agg["avg_score"] += r.total_score
            if r.keyword_hit is not None:
                total_keywords[r.model].append(r.keyword_hit)
        else:
            agg["failed_cases"] += 1
    for m in models:
        agg = model_agg[m]
        if agg["avg_score"] is not None and agg["success_cases"]:
            agg["avg_score"] = round(agg["avg_score"] / agg["success_cases"], 2)
        if total_keywords[m]:
            agg["avg_keyword_hit"] = round(sum(total_keywords[m]) / len(total_keywords[m]), 2)

    # 以 (model, case_id) 建立索引，避免在矩阵装配时对全集做 O(n²) 线性查找
    res_index: dict[tuple[str, int], BenchmarkResult] = {}
    for r in results:
        res_index[(r.model, r.test_case_id)] = r

    cases_info = []
    test_cases = {c.id: c for c in db.query(TestCase).filter(TestCase.task_id == run.task_id).all()}
    for cid in case_ids:
        tc = test_cases.get(cid)
        ref = tc.reference_output if tc else None
        cases_info.append({"case_id": cid, "input_text": tc.input_text if tc else "",
                           "reference_output": ref})

    matrix = []
    for cid in case_ids:
        row = {"case_id": cid, "models": []}
        for m in models:
            r = res_index.get((m, cid))
            row["models"].append({
                "model": m,
                "score": r.total_score if r else None,
                "judge_score": r.judge_score if r else None,
                "judge_reason": r.judge_reason if r else None,
                "output": r.output if r else None,
                "error_reason": r.error_reason if r else None,
                "bleu": r.bleu if r else None,
                "rouge": r.rouge if r else None,
                "keyword_hit": r.keyword_hit if r else None,
            })
        matrix.append(row)

    return {
        "run": {
            "id": run.id, "task_id": run.task_id, "name": run.name,
            "prompt_mode": run.prompt_mode, "prompt_snapshot": run.prompt_snapshot,
            "status": run.status, "best_model": run.best_model, "best_score": run.best_score,
            "created_at": run.created_at, "finished_at": run.finished_at,
        },
        "models_order": models,
        "models": [model_agg[m] for m in models],
        "cases": cases_info,
        "matrix": matrix,
    }


async def run_benchmark(run_id: int) -> None:
    """后台执行一次多模型对比评测并落库。

    流程（与主迭代评估口径一致，保证可比）：
      1) 对每个模型复用 execute_cases 执行全部用例，计算自动指标 + LLM 评审；
      2) 按「同一用例、各模型」横向归一化评审分，消除评审员跨模型/跨用例的尺度差异；
      3) 合成综合得分（权重同主流程），写 BenchmarkResult 并汇总各模型平均分与最优模型。
    """
    db = SessionLocal()
    try:
        run = db.get(BenchmarkRun, run_id)
        if run is None:
            return
        task = db.get(Task, run.task_id)
        if task is None:
            run.status = "failed"
            run.finished_at = _now()
            db.commit()
            return
        run.status = "running"
        run.finished_at = None
        db.commit()

        cases = db.query(TestCase).filter(TestCase.task_id == task.id).order_by(TestCase.id).all()
        prompt = run.prompt_snapshot or task.best_prompt or task.initial_prompt or ""
        # 去除重复模型并保持顺序，避免同一模型被重复运行
        models = list(dict.fromkeys(m for m in _json_loads_fallback(run.models_json, []) if m))
        if not cases or not prompt or not models:
            run.status = "failed"
            run.finished_at = _now()
            run.progress = json.dumps({"error": "缺少用例/提示词/模型，无法评测"}, ensure_ascii=False)
            db.commit()
            return

        anchors = extract_anchors(task, cases)
        inputs = [{"case_id": c.id, "input_text": c.input_text} for c in cases]

        # 阶段1：逐模型执行 + 自动指标 + 原始评审
        # model_evals[model][case_id] = {metric, output, err, judge, reason}
        model_evals: dict[str, dict[int, dict]] = {}
        for m in models:
            per_case: dict[int, dict] = {}
            try:
                exec_results = await execute_cases(
                    prompt=prompt, inputs=inputs, task=task,
                    concurrency=task.concurrency, model=m,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("评测任务 %s 模型 %s 执行整体失败：%s", run_id, m, exc)
                for c in cases:
                    per_case[c.id] = {"metric": None, "output": "", "err": f"{type(exc).__name__}: {exc}",
                                      "judge": None, "reason": None}
                model_evals[m] = per_case
                continue
            exec_map = {r["case_id"]: r for r in exec_results}
            judge_cache: dict[str, tuple[int, str]] = {}
            for c in cases:
                er = exec_map.get(c.id)
                output = er["output"] if er else ""
                err = er["error_reason"] if er else "执行失败"
                metric = compute_metrics(
                    task.task_type, output or "", c.reference_output,
                    _json_loads_fallback(c.keywords, []),
                    _json_loads_fallback(c.run_test, {}),
                )
                ev: dict = {"metric": metric, "output": output, "err": err,
                            "judge": None, "reason": None}
                if not err:
                    key = f"{prompt}\u0001{c.input_text}\u0001{output}"
                    if key in judge_cache:
                        sc, rea = judge_cache[key]
                    else:
                        sc, rea = await judge_output(
                            task=task, prompt=prompt, input_text=c.input_text,
                            output=output, reference=c.reference_output, anchors=anchors,
                        )
                        judge_cache[key] = (sc, rea)
                    ev["judge"], ev["reason"] = sc, rea
                per_case[c.id] = ev
            model_evals[m] = per_case

        # 阶段2：按用例横向归一化评审分（跨模型比较）
        normalized: dict[int, dict[str, float]] = {}
        for c in cases:
            subj = {m: e[c.id]["judge"] for m, e in model_evals.items()
                    if c.id in e and not e[c.id]["err"] and e[c.id]["judge"] is not None}
            if subj:
                normalized[c.id] = _normalize_case_judge(subj)

        # 阶段3：写评测明细 + 汇总
        model_scores: dict[str, list[float]] = {}
        for m, per in model_evals.items():
            for c in cases:
                ev = per.get(c.id)
                if ev is None:
                    continue
                if ev["err"]:
                    db.add(BenchmarkResult(
                        run_id=run.id, model=m, test_case_id=c.id, input_text=c.input_text,
                        output=ev["output"], error_reason=ev["err"],
                        total_score=0.0,
                    ))
                    db.commit()
                    continue
                norm = normalized.get(c.id, {}).get(m, float(ev["judge"] or 0))
                auto = _compute_auto_score(ev["metric"], task)
                use_auto = task.auto_weight if auto is not None else 0.0
                denom = use_auto + task.judge_weight
                total = ((use_auto * (auto or 0) + task.judge_weight * (norm * 10)) / denom
                         if denom > 0 else norm * 10)
                db.add(BenchmarkResult(
                    run_id=run.id, model=m, test_case_id=c.id, input_text=c.input_text,
                    output=ev["output"], error_reason=None,
                    bleu=ev["metric"].bleu, rouge=ev["metric"].rouge,
                    keyword_hit=ev["metric"].keyword_hit, format_ok=ev["metric"].format_ok,
                    judge_score=round(norm, 2), judge_reason=ev["reason"],
                    total_score=round(total, 2),
                ))
                db.commit()
                model_scores.setdefault(m, []).append(total)

        # 汇总最优模型与平均分：分数并列时不武断指定最优模型（best_model 置 None）
        agg = {m: (round(sum(v) / len(v), 2) if v else None)
               for m, v in model_scores.items()}
        best_score = None
        for m, s in agg.items():
            if s is not None and (best_score is None or s > best_score):
                best_score = s
        best_candidates = [m for m, s in agg.items() if s == best_score] if best_score is not None else []
        best_model = best_candidates[0] if len(best_candidates) == 1 else None
        run.best_model = best_model
        run.best_score = best_score
        run.status = "completed"
        run.finished_at = _now()
        run.progress = json.dumps(agg, ensure_ascii=False)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("评测任务 %s 失败", run_id)
        db.rollback()
        try:
            run = db.query(BenchmarkRun).filter(BenchmarkRun.id == run_id).first()
            if run is not None:
                run.status = "failed"
                run.finished_at = _now()
                run.progress = json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()