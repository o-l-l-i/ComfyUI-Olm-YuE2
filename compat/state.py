"""Scope the process settings changed by the audited upstream pipeline."""

from contextlib import contextmanager
import math
import threading

import torch


STATE_LOCK = threading.RLock()


@contextmanager
def upstream_state(device, *, preserve_cuda_limit=True):
    with STATE_LOCK:
        device = torch.device(device)
        cuda = device.type == "cuda" and preserve_cuda_limit
        if cuda and not callable(getattr(torch.cuda, "get_per_process_memory_fraction", None)):
            raise RuntimeError("This Torch build cannot read the CUDA memory limit; YuE2 was not initialized")
        fraction = torch.cuda.get_per_process_memory_fraction(device) if cuda else None
        if cuda and (not math.isfinite(fraction) or not 0 <= fraction <= 1):
            raise RuntimeError("CUDA memory limit cannot be restored with this allocator; YuE2 was not initialized")
        cudnn = torch.backends.cudnn
        matmul = torch.backends.cuda.matmul
        saved = (cudnn.benchmark, cudnn.deterministic, matmul.allow_tf32,
                 cudnn.allow_tf32, matmul.allow_fp16_reduced_precision_reduction,
                 torch.get_float32_matmul_precision())
        try:
            cudnn.benchmark = False
            cudnn.deterministic = True
            matmul.allow_tf32 = False
            cudnn.allow_tf32 = False
            matmul.allow_fp16_reduced_precision_reduction = False
            torch.set_float32_matmul_precision("highest")
            # Model constructors initialize CPU tensors; generation uses local RNGs.
            with torch.random.fork_rng(devices=[]):
                yield
        finally:
            torch.set_float32_matmul_precision(saved[5])
            cudnn.benchmark, cudnn.deterministic = saved[:2]
            matmul.allow_tf32, cudnn.allow_tf32 = saved[2:4]
            matmul.allow_fp16_reduced_precision_reduction = saved[4]
            if cuda:
                torch.cuda.set_per_process_memory_fraction(fraction, device)
