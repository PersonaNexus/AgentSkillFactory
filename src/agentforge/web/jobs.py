"""In-memory job store for long-running pipeline operations."""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Job:
    """A tracked async job (forge or batch)."""

    id: str
    status: str = "pending"  # pending | running | done | error
    events: queue.Queue = field(default_factory=queue.Queue)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)

    def emit(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Push an SSE event onto the queue."""
        self.events.put(json.dumps({"event": event, **(data or {})}))

    def emit_stage(self, stage: str, message: str) -> None:
        self.emit("stage", {"stage": stage, "message": message})

    def emit_done(self, result: dict[str, Any]) -> None:
        self.result = result
        self.status = "done"
        self.emit("done", result)

    def emit_error(self, message: str) -> None:
        self.error = message
        self.status = "error"
        self.emit("error", {"message": message})


class JobStore:
    """Thread-safe in-memory store for async jobs."""

    _TTL_SECONDS = 1800  # 30 minutes

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self) -> Job:
        job = Job(id=uuid.uuid4().hex[:12])
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cleanup(self) -> int:
        """Remove expired jobs. Returns count removed."""
        cutoff = time.time() - self._TTL_SECONDS
        removed = 0
        with self._lock:
            expired = [k for k, v in self._jobs.items() if v.created_at < cutoff]
            for k in expired:
                del self._jobs[k]
                removed += 1
        return removed
