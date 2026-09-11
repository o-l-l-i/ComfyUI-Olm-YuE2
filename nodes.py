"""ComfyUI graph stages. Heavy dependencies are imported only during execution."""

from dataclasses import asdict
import logging

from .runtime.artifacts import ModelSelection
from ._vendor.yue2.protocol import SongRequest, Sampling, GenerationConfig


def model_paths():
    import folder_paths
    from .runtime.paths import ModelPaths
    return ModelPaths(folder_paths)


def execute(*args, **kwargs):
    from .runtime.stages import run_stage
    return run_stage(*args, **kwargs)


class ModelLoader:
    _missing_paths_warned = {}

    @classmethod
    def choices(cls, paths, kind):
        choices = paths.list(kind)
        if choices:
            cls._missing_paths_warned.pop(kind, None)
            return choices
        roots = tuple(paths.folders.get_folder_paths(kind))
        if cls._missing_paths_warned.get(kind) != roots:
            logging.warning("YuE2: no valid %s checkpoints found. Searched: %s. "
                            "Place the checkpoint folder under ComfyUI/models/%s, or add '%s' "
                            "to extra_model_paths.yaml and restart ComfyUI. Required: config.json, "
                            "safetensors weights%s.", kind, ", ".join(roots), kind, kind,
                            ", qwen.tiktoken" if kind == "yue2" else "")
            cls._missing_paths_warned[kind] = roots
        return choices

    @classmethod
    def INPUT_TYPES(cls):
        paths = model_paths()
        return {"required": {
            "model": (cls.choices(paths, "yue2") or ["No models found — configure yue2 paths"],
                      {"tooltip": "Uses models/yue2 or the yue2 key in extra_model_paths.yaml. Direct checkpoint mappings display their folder names."}),
            "vae": (cls.choices(paths, "yue2_vae") or ["No VAEs found — configure yue2_vae paths"],
                    {"tooltip": "Uses models/yue2_vae or the yue2_vae key in extra_model_paths.yaml. Image VAE paths are separate."})}}

    @classmethod
    def VALIDATE_INPUTS(cls, model, vae):
        paths = model_paths()
        errors = []
        for kind, name in (("yue2", model), ("yue2_vae", vae)):
            choices = paths.list(kind)
            if not choices:
                roots = ", ".join(paths.folders.get_folder_paths(kind))
                errors.append(f"No valid {kind} checkpoints found. Searched: {roots}. "
                        f"Add a '{kind}' mapping in extra_model_paths.yaml and restart ComfyUI. "
                        "Keep config.json and weights together; the generation model also needs qwen.tiktoken.")
                continue
            if name not in choices:
                if name == ".":
                    try:
                        paths.resolve(kind, name)
                        continue
                    except (OSError, ValueError, KeyError, TypeError):
                        pass
                errors.append(f"{kind} selection {name!r} is unavailable. Refresh the dropdown and select one of: {', '.join(choices)}.")
        return "Check YuE2 Model Loader selections: " + " ".join(errors) if errors else True

    RETURN_TYPES = ("YUE2_MODEL",)
    FUNCTION = "load"
    CATEGORY = "YuE2"

    @classmethod
    def IS_CHANGED(cls, model, vae):
        paths = model_paths()
        return tuple((str(file), file.stat().st_size, file.stat().st_mtime_ns, file.stat().st_ctime_ns)
                     for kind, name in (("yue2", model), ("yue2_vae", vae))
                     for file in sorted(paths.resolve(kind, name).iterdir()) if file.is_file())

    def load(self, model, vae):
        paths = model_paths()
        paths.resolve("yue2", model)
        paths.resolve("yue2_vae", vae)
        return (ModelSelection(model, vae),)


class Request:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "style": ("STRING", {"multiline": True, "default": "gentle acoustic piano"}),
            "lyrics": ("STRING", {"multiline": True, "default": "", "tooltip": "Leave empty for instrumental music."}),
            "cot": (["full", "melody", "off"], {"tooltip": "Plan a score with chords, melody only, or generate without a score."}),
            "seed": ("INT", {"default": 831001, "min": 0, "max": 2**63 - 1, "control_after_generate": True}),
        }, "optional": {"abc": ("STRING", {"multiline": True, "default": ""})}}

    RETURN_TYPES = ("YUE2_REQUEST",)
    FUNCTION = "create"
    CATEGORY = "YuE2"

    def create(self, style, lyrics, cot, seed, abc=""):
        return (SongRequest(style, lyrics, cot=cot, seed=seed, abc=abc if abc.strip() else None),)


class SamplingConfig:
    @classmethod
    def INPUT_TYPES(cls):
        fields = {}
        config = GenerationConfig()
        limits = {"temperature": (0., 5.), "top_p": (.001, 1.), "top_k": (1, 184704),
                  "repetition_penalty": (.001, 10.), "penalty_window": (1, 100),
                  "min_tokens": (0, 24576), "max_tokens": (1, 24576)}
        for stage in ("abc", "semantic"):
            for name, default in asdict(getattr(config, stage)).items():
                low, high = limits[name]
                fields[f"{stage}_{name}"] = ("INT" if type(default) is int else "FLOAT",
                    {"default": default, "min": low, "max": high})
        fields["ode_steps"] = ("INT", {"default": 32, "min": 1, "max": 256})
        return {"required": fields}

    RETURN_TYPES = ("YUE2_SAMPLING",)
    FUNCTION = "create"
    CATEGORY = "YuE2"

    def create(self, **kwargs):
        stages = {stage: Sampling(**{k.removeprefix(stage + "_"): v for k, v in kwargs.items()
                                    if k.startswith(stage + "_")}) for stage in ("abc", "semantic")}
        return (GenerationConfig(**stages, ode_steps=kwargs.get("ode_steps", 32)),)


class Plan:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("YUE2_MODEL",), "request": ("YUE2_REQUEST",)},
                "optional": {"sampling": ("YUE2_SAMPLING",)}}

    RETURN_TYPES = ("YUE2_PLAN", "STRING", "YUE2_RUN_INFO")
    RETURN_NAMES = ("plan", "abc", "run_info")
    FUNCTION = "generate"
    CATEGORY = "YuE2"

    def generate(self, model, request, sampling=None):
        artifact = execute(model, "plan", request, sampling or GenerationConfig())
        return artifact, artifact.value.abc or "", artifact.info


class Semantic:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("YUE2_MODEL",), "plan": ("YUE2_PLAN",)},
                "optional": {"sampling": ("YUE2_SAMPLING",)}}

    RETURN_TYPES = ("YUE2_SEMANTIC", "YUE2_RUN_INFO")
    RETURN_NAMES = ("semantic", "run_info")
    FUNCTION = "generate"
    CATEGORY = "YuE2"

    def generate(self, model, plan, sampling=None):
        artifact = execute(model, "semantic", plan, sampling or GenerationConfig())
        return artifact, artifact.info


class Synthesize:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("YUE2_MODEL",), "semantic": ("YUE2_SEMANTIC",)},
                "optional": {"sampling": ("YUE2_SAMPLING",),
                             "offload_ar": ("BOOLEAN", {"default": False,
                                 "tooltip": "Experimental CUDA memory saving: offload token-generation layers through ComfyUI during synthesis. Cache preparation still loads the full model; transfers may add time."})}}

    RETURN_TYPES = ("YUE2_LATENTS", "YUE2_RUN_INFO")
    RETURN_NAMES = ("latents", "run_info")
    FUNCTION = "generate"
    CATEGORY = "YuE2"

    def generate(self, model, semantic, sampling=None, offload_ar=False):
        artifact = execute(model, "synthesize", semantic, sampling or GenerationConfig(), offload_ar=offload_ar)
        return artifact, artifact.info


class Decode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("YUE2_MODEL",), "latents": ("YUE2_LATENTS",),
                             "mode": (["tiled", "full"],),
                             "tile_frames": ("INT", {"default": 1024, "min": 1, "max": 4096})}}

    RETURN_TYPES = ("AUDIO", "YUE2_RUN_INFO")
    RETURN_NAMES = ("audio", "run_info")
    FUNCTION = "decode"
    CATEGORY = "YuE2"

    def decode(self, model, latents, mode, tile_frames):
        if mode not in {"tiled", "full"}:
            raise ValueError("Decode mode must be tiled or full")
        config = GenerationConfig.from_dict(latents.info["stages"][-1]["provenance"]["config"]["generation"])
        return execute(model, "decode", latents, config, full=mode == "full", tile_frames=tile_frames)


NODE_CLASS_MAPPINGS = {"OlmYuE2ModelLoader": ModelLoader, "OlmYuE2Request": Request,
    "OlmYuE2Sampling": SamplingConfig, "OlmYuE2Plan": Plan, "OlmYuE2Semantic": Semantic,
    "OlmYuE2Synthesize": Synthesize, "OlmYuE2Decode": Decode}
NODE_DISPLAY_NAME_MAPPINGS = {name: "YuE2 " + label for name, label in zip(NODE_CLASS_MAPPINGS,
    ("Model Loader", "Request", "Sampling", "Plan", "Semantic", "Synthesize", "Decode"))}
