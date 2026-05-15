"""
后台任务进度存储

简化实现：基于内存字典 + asyncio.Lock 的 JobStore。
每个长耗时任务（如多教材整合）启动时分配 job_id，业务代码通过
JobHandle.update(...) 上报进度，前端轮询 /progress/{job_id} 获取状态。
"""
from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class JobState:
    job_id: str
    status: str = "pending"  # pending | running | completed | failed
    phase: str = ""
    current: int = 0
    total: int = 0
    message: str = ""
    error: Optional[str] = None
    result: Any = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "phase": self.phase,
            "current": self.current,
            "total": self.total,
            "percent": round(self.current / self.total * 100, 1) if self.total else 0.0,
            "message": self.message,
            "error": self.error,
            "result": self.result,
            "elapsed": round(self.updated_at - self.created_at, 2),
        }


class JobHandle:
    """业务代码用来上报进度的句柄"""

    def __init__(self, store: "JobStore", job_id: str):
        self._store = store
        self.job_id = job_id

    def update(
        self,
        *,
        phase: Optional[str] = None,
        current: Optional[int] = None,
        total: Optional[int] = None,
        message: Optional[str] = None,
        increment: int = 0,
    ) -> None:
        state = self._store._states.get(self.job_id)
        if state is None:
            return
        if phase is not None:
            state.phase = phase
        if total is not None:
            state.total = total
        if current is not None:
            state.current = current
        if increment:
            state.current += increment
        if message is not None:
            state.message = message
        state.updated_at = time.time()


class JobStore:
    def __init__(self, *, max_jobs: int = 200, retention_seconds: int = 1800):
        self._states: Dict[str, JobState] = {}
        self._order = deque()
        self._max_jobs = max_jobs
        self._retention_seconds = retention_seconds

    def _gc(self) -> None:
        now = time.time()
        expired_ids = []
        for job_id, state in self._states.items():
            if state.status in {"completed", "failed"} and (now - state.updated_at) > self._retention_seconds:
                expired_ids.append(job_id)

        for job_id in expired_ids:
            self._states.pop(job_id, None)

        while self._order and self._order[0] not in self._states:
            self._order.popleft()

        while len(self._states) > self._max_jobs and self._order:
            non_running = next((jid for jid in self._order if self._states.get(jid) and self._states[jid].status != "running"), None)
            if non_running is None:
                break
            try:
                self._order.remove(non_running)
            except ValueError:
                pass
            self._states.pop(non_running, None)

    def create(self) -> JobHandle:
        self._gc()
        job_id = str(uuid.uuid4())
        self._states[job_id] = JobState(job_id=job_id, status="running")
        self._order.append(job_id)
        return JobHandle(self, job_id)

    def get(self, job_id: str) -> Optional[JobState]:
        self._gc()
        return self._states.get(job_id)

    def complete(self, job_id: str, result: Any) -> None:
        self._gc()
        state = self._states.get(job_id)
        if state:
            state.status = "completed"
            state.result = result
            state.current = state.total or state.current
            state.updated_at = time.time()

    def fail(self, job_id: str, error: str) -> None:
        self._gc()
        state = self._states.get(job_id)
        if state:
            state.status = "failed"
            state.error = error
            state.updated_at = time.time()


job_store = JobStore()
