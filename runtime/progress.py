"""Callback bridge for upstream's status context and ComfyUI interruption."""

from contextlib import contextmanager
from dataclasses import dataclass


def noop(*args):
    pass


@dataclass(frozen=True)
class ProgressEvent:
    phase: str
    completed: int
    total: int | None
    unit: str | None
    status: str


class Callbacks:
    def __init__(self, check_cancelled=noop, report=noop, release_cache=noop):
        self.check_cancelled = check_cancelled
        self.report = report
        self.release_cache = release_cache

    def cancelled(self):
        self.check_cancelled()
        return False

    @contextmanager
    def stage(self, label, total=None, unit=None):
        stage = Stage(self, label, total, unit)
        stage.emit()
        yield stage
        if stage.status == "running":
            stage.finish()


class Stage:
    def __init__(self, callbacks, label, total, unit):
        self.callbacks = callbacks
        self.label, self.total, self.unit = label, total, unit
        self.completed = 0
        self.status = "running"

    def emit(self):
        self.callbacks.check_cancelled()
        self.callbacks.report(ProgressEvent(self.label, self.completed, self.total, self.unit, self.status))

    def update(self, completed, total=None):
        self.completed = completed
        if total is not None:
            self.total = total
        self.emit()

    def advance(self, count=1):
        self.update(self.completed + count)

    def finish(self, status="completed"):
        self.status = status
        self.emit()
