# ==========================================================
# 迭代进度内存记录器：供前端轮询实时进度
# ==========================================================
import threading
import time
from typing import Optional


class _Progress:
    """单任务迭代进度快照。"""

    def __init__(self, task_id: int):
        self.task_id = task_id
        self.status = "pending"
        self.current_round = 0
        self.max_rounds = 10
        self.current_best_score: Optional[float] = None
        self.variants_done = 0
        self.variants_total = 0
        self.cases_done = 0
        self.cases_total = 0
        self.cases_success = 0
        self.cases_failed = 0
        self.message: Optional[str] = None
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_status": self.status,
            "current_round": self.current_round,
            "max_rounds": self.max_rounds,
            "current_best_score": self.current_best_score,
            "variants_done": self.variants_done,
            "variants_total": self.variants_total,
            "cases_done": self.cases_done,
            "cases_total": self.cases_total,
            "cases_success": self.cases_success,
            "cases_failed": self.cases_failed,
            "message": self.message,
        }


class ProgressTracker:
    """线程安全的进度管理器（内存态，服务重启即失效，可接受）。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._store: dict[int, _Progress] = {}

    def create(self, task_id: int, max_rounds: int) -> _Progress:
        with self._lock:
            p = _Progress(task_id)
            p.max_rounds = max_rounds
            self._store[task_id] = p
            return p

    def get(self, task_id: int) -> Optional[_Progress]:
        with self._lock:
            return self._store.get(task_id)

    def update(self, task_id: int, **kwargs) -> None:
        with self._lock:
            p = self._store.get(task_id)
            if p is None:
                return
            for k, v in kwargs.items():
                if hasattr(p, k):
                    setattr(p, k, v)
            p.updated_at = time.time()

    def remove(self, task_id: int) -> None:
        with self._lock:
            self._store.pop(task_id, None)


progress_tracker = ProgressTracker()