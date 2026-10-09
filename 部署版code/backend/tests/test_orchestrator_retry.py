# -*- coding: utf-8 -*-
# ==========================================================
# orchestrator「单轮失败自动重试」回归测试
# 场景：单轮 graph.ainvoke 前两次抛瞬时异常、第三次成功 → 这一轮重试后任务不应被标记 failed
# 注意：方案4 将图改为「单轮图」，轮次推进与重试由 run_iteration_task 外层循环驱动，
#       失败仅重试当轮，不再把整个任务从头重跑。
# ==========================================================
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.services import optimizer_orchestrator as orch


class _FakeGraph:
    """单轮图：ainvoke 前 fail_n 次抛瞬时异常，其后返回 terminating 表示本轮正常结束。

    terminating 返回 "completed" 会让外层循环立即退出（等价于本轮 decide 已判定终止），
    若场景需要持续迭代，可返回 "" （继续），并多次调用以模拟多轮。
    """

    def __init__(self, fail_n, terminating="completed"):
        self._calls = 0
        self._fail_n = fail_n
        self._terminating = terminating

    async def ainvoke(self, state):
        self._calls += 1
        if self._calls <= self._fail_n:
            raise RuntimeError("变体生成失败：瞬时故障")
        # 推进 round（模拟 gen 节点自增），并返回终止原因
        state["round"] = state["round"] + 1
        return {**state, "terminating": self._terminating}


class _TaskRecorder:
    """记录 status / last_error 赋值的任务替身，便于断言失败路径写入。"""

    def __init__(self):
        self.status = None
        self.last_error = None
        self.updated_at = None
        # run_iteration_task 开头会读 best_prompt 作为基准提示词；提供非空值避免触发初始提示词生成
        self.best_prompt = "seed-prompt"
        self.initial_prompt = None


def _make_db():
    """构造一个 db：get 返回任务替身，commit 可观测。"""
    db = MagicMock()
    db.get.return_value = _TaskRecorder()
    return db


@pytest.mark.anyio
async def test_round_retry_recovers_transient_failure():
    """瞬时失败 2 次后成功：只重试当轮，任务不应进入 failed。"""
    graph = _FakeGraph(fail_n=2)
    db = _make_db()
    with patch.object(orch, "get_compiled_graph", return_value=graph), \
         patch.object(orch, "SessionLocal", return_value=db):
        await orch.run_iteration_task(1, 1)
    assert graph._calls == 3  # 首次 + 2 次重试
    # 成功路径不应写 failed
    task = db.get.return_value
    assert task.status != "failed"


@pytest.mark.anyio
async def test_round_retry_exhausted_marks_failed():
    """连续失败超过重试上限：任务最终标记 failed，且不会无限重试。"""
    graph = _FakeGraph(fail_n=99)
    db = _make_db()
    with patch.object(orch, "get_compiled_graph", return_value=graph), \
         patch.object(orch, "SessionLocal", return_value=db):
        await orch.run_iteration_task(1, 1)
    assert graph._calls == 3  # 首次 + 2 次重试后即停止，不再无限重试
    task = db.get.return_value
    assert task.status == "failed"
    assert task.last_error and "变体生成失败" in task.last_error


@pytest.mark.anyio
async def test_multi_round_continues_until_terminating():
    """单轮图返回终止原因应为空时继续下一轮，直到返回终止原因才退出。"""
    graph = _FakeGraph(fail_n=0, terminating="")
    # 前2次返回 ""（继续），第3次返回 completed（终止）
    def _terminate_on_3():
        return ""
    graph._terminating = None
    orig = graph.ainvoke

    class _Seq:
        def __init__(self):
            self.n = 0
    seq = _Seq()

    async def seq_ainvoke(state):
        seq.n += 1
        state["round"] = state["round"] + 1
        if seq.n < 3:
            return {**state, "terminating": ""}
        return {**state, "terminating": "completed"}

    graph.ainvoke = seq_ainvoke
    db = _make_db()
    with patch.object(orch, "get_compiled_graph", return_value=graph), \
         patch.object(orch, "SessionLocal", return_value=db):
        await orch.run_iteration_task(1, 1)
    assert seq.n == 3  # 推进了 3 轮后才终止