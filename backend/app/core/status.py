from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.queued: {JobStatus.running, JobStatus.canceled},
    JobStatus.running: {JobStatus.completed, JobStatus.failed, JobStatus.canceled},
    JobStatus.completed: set(),
    JobStatus.failed: set(),
    JobStatus.canceled: set(),
}


def can_transition(current: JobStatus, target: JobStatus) -> bool:
    return target in TRANSITIONS.get(current, set())
