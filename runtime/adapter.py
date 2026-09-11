"""Local-only, serialized lifetime for the official YuE2 pipeline stages."""

import threading

import torch

from .._vendor.yue2.pipeline import YuE2Pipeline
from ..compat.state import upstream_state
from .paths import validate_checkpoint
from .progress import Callbacks


class _Pipeline(YuE2Pipeline):
    def __init__(self, *args, callbacks, residency=None, **kwargs):
        self.callbacks = callbacks
        self.residency = residency
        super().__init__(*args, progress=True, manage_cuda_memory=False, **kwargs)

    def _status(self, label, *, total=None, unit=None):
        return self.callbacks.stage(label, total, unit)

    def _move_model(self, model, device):
        if self.residency is None:
            return super()._move_model(model, device)
        if self.offload_ar and model is self._model:
            return self.residency.move_synthesis(model, device)
        return self.residency.move(model, device)

    def _offload_ar(self, model):
        if self.offload_ar and self.residency is not None:
            return self.residency.offload_ar(model)
        return super()._offload_ar(model)


class Yue2Runtime:
    def __init__(self, model_dir, vae_dir, *, device, callbacks=None,
                 memory_budget_gib=24, generation_config=None, vae_core_frames=None,
                 residency=None, offload_ar=False):
        self._lock = threading.RLock()
        self._pipeline = None
        self.device = torch.device(device)
        self.residency = residency
        self.callbacks = callbacks or Callbacks(release_cache=self._release_cache)
        if self.device.type not in {"cpu", "cuda", "mps"}:
            raise ValueError("YuE2 currently supports cpu, cuda or mps devices")
        if type(offload_ar) is not bool:
            raise ValueError("offload_ar must be a boolean")
        if offload_ar and self.device.type != "cuda":
            raise ValueError("Experimental synthesis offloading currently requires CUDA")
        if self.device.type == "cuda" and self.device.index is None:
            self.device = torch.device("cuda", torch.cuda.current_device())
        if vae_core_frames is not None and (isinstance(vae_core_frames, bool) or not isinstance(vae_core_frames, int) or vae_core_frames <= 0):
            raise ValueError("vae_core_frames must be a positive integer")
        model_dir = validate_checkpoint(model_dir, "yue2")
        vae_dir = validate_checkpoint(vae_dir, "yue2_vae")
        self.callbacks.check_cancelled()
        with upstream_state(self.device, preserve_cuda_limit=False):
            self._pipeline = _Pipeline(model_dir, vae_dir, device=self.device,
                                       backend="torch-eager", callbacks=self.callbacks, residency=residency,
                                       memory_budget_gib=memory_budget_gib,
                                       generation_config=generation_config,
                                       vae_core_frames=vae_core_frames, offload_ar=offload_ar)

    @property
    def closed(self):
        return self._pipeline is None

    def _call(self, stage, *args, **kwargs):
        with self._lock:
            if self.closed:
                raise RuntimeError("YuE2 runtime is unloaded; load it again")
            try:
                self.callbacks.check_cancelled()
                with upstream_state(self.device, preserve_cuda_limit=False):
                    result = getattr(self._pipeline, stage)(*args, **kwargs)
                    self.callbacks.check_cancelled()
                    return result
            except BaseException as error:
                try:
                    self.close()
                except Exception as cleanup_error:
                    raise error from cleanup_error
                raise

    def _release_cache(self):
        if self.device.type == "cuda":
            torch.cuda.empty_cache()

    def plan(self, request, *, abc_sampling=None):
        return self._call("plan", request=request, abc_sampling=abc_sampling,
                          cancelled=self.callbacks.cancelled)

    def generate_semantic(self, plan, *, sampling=None):
        return self._call("generate_semantic", plan, sampling=sampling,
                          cancelled=self.callbacks.cancelled)

    def synthesize(self, semantic):
        return self._call("synthesize", semantic, cancelled=self.callbacks.cancelled)

    def decode(self, latents, *, full=False):
        return self._call("decode", latents, full=full)

    def provenance(self, request):
        from copy import deepcopy
        from .._vendor.yue2.storage import sha256_file

        with self._lock:
            if self.closed:
                raise RuntimeError("YuE2 runtime is unloaded; load it again")
            return {"weights": deepcopy(self._pipeline.weights),
                    "tokenizer_sha256": sha256_file(self._pipeline.model_dir / "qwen.tiktoken"),
                    "config": self._pipeline.effective_config(request),
                    "attention": "upstream"}

    def close(self):
        with self._lock:
            pipeline, self._pipeline = self._pipeline, None
            if pipeline is None:
                return
            try:
                if self.residency is not None:
                    self.residency.close()
                else:
                    for name in ("_model", "_vae"):
                        model = getattr(pipeline, name)
                        try:
                            if model is not None:
                                model.to("cpu")
                        finally:
                            setattr(pipeline, name, None)
            finally:
                pipeline._model = pipeline._vae = None
                model = None
                pipeline = None
                self.callbacks.release_cache()

    def __enter__(self):
        if self.closed:
            raise RuntimeError("YuE2 runtime is unloaded")
        return self

    def __exit__(self, *exc):
        self.close()
