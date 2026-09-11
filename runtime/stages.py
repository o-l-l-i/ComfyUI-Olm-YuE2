"""Stage-scoped host execution; graph caches never own a live runtime."""

from copy import deepcopy
import logging
import time

import numpy as np
import torch

from .adapter import Yue2Runtime
from .artifacts import PlanArtifact, SemanticArtifact, LatentArtifact
from .comfy import comfy_callbacks, comfy_device
from .memory import cuda_memory
from .paths import ModelPaths
from .residency import ComfyResidency


def edit_score(selection, plan, abc):
    from dataclasses import replace
    from .._vendor.yue2.protocol import GenerationConfig
    from .archive import plan_identity

    request = replace(plan.value.request, abc=abc)
    config = GenerationConfig.from_dict(plan.info["stages"][0]["provenance"]["config"]["generation"])
    edited = run_stage(selection, "plan", request, config)
    edited.info["edited_from"] = plan_identity(plan)
    return edited


def run_stage(selection, stage, value, sampling, *, full=False, tile_frames=1024, offload_ar=False):
    import folder_paths

    paths = ModelPaths(folder_paths)
    model, vae = paths.resolve("yue2", selection.model), paths.resolve("yue2_vae", selection.vae)
    device = comfy_device()
    request = value if stage == "plan" else (
        value.value.request if stage == "semantic" else
        value.value.plan.request if stage == "synthesize" else value.semantic.value.plan.request)
    start = time.perf_counter()
    memory_before = cuda_memory(device)
    logging.info("[YuE2] %s stage: model=%s, vae=%s, device=%s.", stage, model.name, vae.name, device)
    with Yue2Runtime(model, vae, device=device, callbacks=comfy_callbacks(),
                     generation_config=sampling, vae_core_frames=tile_frames,
                     residency=ComfyResidency(device), offload_ar=offload_ar) as runtime:
        provenance = runtime.provenance(request)
        if stage != "plan":
            prior = value.info["stages"][0]["provenance"]
            if (prior["weights"]["mot"] != provenance["weights"]["mot"] or
                    prior["tokenizer_sha256"] != provenance["tokenizer_sha256"]):
                raise ValueError("YuE2 model/tokenizer differs from this artifact; regenerate its plan")
        if stage == "plan":
            result = runtime.plan(value)
        elif stage == "semantic":
            result = runtime.generate_semantic(value.value)
        elif stage == "synthesize":
            result = runtime.synthesize(value.value)
        elif stage == "decode":
            result = runtime.decode(value.value, full=full)
            provenance["config"]["vae_decode"] = "full" if full else "halo_crop"
        else:
            raise ValueError(f"Unknown YuE2 stage: {stage}")
    info = {"version": 1, "request": request.to_dict(), "stages": []} if stage == "plan" else deepcopy(value.info)
    memory_after = cuda_memory(device)
    info["stages"].append({"stage": stage, "seconds": time.perf_counter() - start,
                           "provenance": provenance,
                           "memory": {"before": memory_before, "after_cleanup": memory_after}})
    if memory_after is not None:
        logging.info("[YuE2] %s cleanup: allocated %.2f -> %.2f GiB, reserved %.2f -> %.2f GiB.",
                     stage, memory_before["allocated_bytes"] / 2**30, memory_after["allocated_bytes"] / 2**30,
                     memory_before["reserved_bytes"] / 2**30, memory_after["reserved_bytes"] / 2**30)
    if stage == "plan":
        info["truncated"] = {"abc": result.truncated}
        return PlanArtifact(result, info)
    if stage == "semantic":
        info["truncated"]["semantic"] = result.truncated
        return SemanticArtifact(result, info)
    if stage == "synthesize":
        return LatentArtifact(result, value, info)
    if result.ndim != 2 or result.shape[1] != 2 or not np.isfinite(result).all():
        raise ValueError("YuE2 decoder did not return finite stereo audio")
    audio = {"waveform": torch.from_numpy(np.ascontiguousarray(result.T)).unsqueeze(0),
             "sample_rate": 48000}
    logging.info("[YuE2] Audio ready: %.2fs, stereo, 48000 Hz.", result.shape[0] / 48000)
    return audio, info
