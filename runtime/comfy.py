"""Explicit host bindings; importing the node package does not import this module."""

import logging
import time

from comfy import model_management
from comfy.utils import ProgressBar

from .progress import Callbacks


def comfy_callbacks():
    bar = None
    phase = None
    active = False
    started = last_report = 0.0

    def report(event):
        nonlocal bar, phase, active, started, last_report
        now = time.perf_counter()
        new_phase = event.phase != phase or not active
        if new_phase:
            phase = event.phase
            active = True
            started = last_report = now
            bar = ProgressBar(event.total) if event.total is not None else None
            logging.info("[YuE2] %s...", phase)
        if event.total is not None:
            if bar is None:
                bar = ProgressBar(event.total)
            bar.update_absolute(event.completed, event.total)
        if event.status != "running" or now - last_report >= 15:
            count = str(event.completed) if event.total is None else f"{event.completed}/{event.total}"
            detail = f"{count} {event.unit}, " if event.unit else ""
            if event.status == "truncated":
                logging.warning("[YuE2] %s: token limit reached (%s%.1fs).", phase, detail, now - started)
            else:
                logging.info("[YuE2] %s: %s (%s%.1fs).", phase, event.status, detail, now - started)
            last_report = now
            active = event.status == "running"

    return Callbacks(model_management.throw_exception_if_processing_interrupted,
                     report, model_management.soft_empty_cache)


def comfy_device():
    return model_management.get_torch_device()
