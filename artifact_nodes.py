"""Score editing and local artifact nodes; serialization imports stay lazy."""


def archive_module():
    from .runtime import archive
    return archive


def folders():
    import folder_paths
    return folder_paths


class ApplyEditedScore:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("YUE2_MODEL",), "plan": ("YUE2_PLAN",),
            "abc": ("STRING", {"multiline": True, "default": "", "tooltip": "Edited ABC is tokenized into a new plan. Source plan must use full or melody mode."})}}

    RETURN_TYPES = ("YUE2_PLAN", "STRING", "YUE2_RUN_INFO")
    RETURN_NAMES = ("plan", "abc", "run_info")
    CATEGORY = "YuE2"
    FUNCTION = "apply"

    def apply(self, model, plan, abc):
        from .runtime.stages import edit_score
        edited = edit_score(model, plan, abc)
        return edited, edited.value.abc, edited.info


class SavePlan:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"plan": ("YUE2_PLAN",), "name": ("STRING", {"default": "plan"})},
                "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("artifact",)
    CATEGORY = "YuE2/artifacts"
    FUNCTION = "save"
    OUTPUT_NODE = True

    def save(self, plan, name, prompt=None, extra_pnginfo=None):
        reference = archive_module().save(folders(), name, plan, prompt=prompt,
                                          workflow=(extra_pnginfo or {}).get("workflow"))
        return {"ui": {"text": [reference]}, "result": (reference,)}


class LoadPlan:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"artifact": (archive_module().list_archives(folders(), "plan"),)}}

    RETURN_TYPES = ("YUE2_PLAN", "STRING", "YUE2_RUN_INFO")
    RETURN_NAMES = ("plan", "abc", "run_info")
    CATEGORY = "YuE2/artifacts"
    FUNCTION = "load"

    @classmethod
    def IS_CHANGED(cls, artifact):
        return archive_module().fingerprint(folders(), artifact)

    def load(self, artifact):
        plan = archive_module().load_plan(folders(), artifact)
        return plan, plan.value.abc or "", plan.info


class SaveRun:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"latents": ("YUE2_LATENTS",), "audio": ("AUDIO",),
            "run_info": ("YUE2_RUN_INFO",), "name": ("STRING", {"default": "run"})},
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("artifact",)
    CATEGORY = "YuE2/artifacts"
    FUNCTION = "save"
    OUTPUT_NODE = True

    def save(self, latents, audio, run_info, name, prompt=None, extra_pnginfo=None):
        reference = archive_module().save(folders(), name, latents=latents, audio=audio, run_info=run_info,
                                          prompt=prompt, workflow=(extra_pnginfo or {}).get("workflow"))
        return {"ui": {"text": [reference]}, "result": (reference,)}


class LoadRun:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"artifact": (archive_module().list_archives(folders(), "run"),)}}

    RETURN_TYPES = ("YUE2_PLAN", "YUE2_SEMANTIC", "YUE2_LATENTS", "AUDIO", "YUE2_RUN_INFO")
    RETURN_NAMES = ("plan", "semantic", "latents", "audio", "run_info")
    CATEGORY = "YuE2/artifacts"
    FUNCTION = "load"

    @classmethod
    def IS_CHANGED(cls, artifact):
        return archive_module().fingerprint(folders(), artifact)

    def load(self, artifact):
        return archive_module().load_run(folders(), artifact)


NODE_CLASS_MAPPINGS = {"OlmYuE2ApplyEditedScore": ApplyEditedScore, "OlmYuE2SavePlan": SavePlan,
    "OlmYuE2LoadPlan": LoadPlan, "OlmYuE2SaveRun": SaveRun, "OlmYuE2LoadRun": LoadRun}
NODE_DISPLAY_NAME_MAPPINGS = {"OlmYuE2ApplyEditedScore": "YuE2 Apply Edited Score",
    "OlmYuE2SavePlan": "YuE2 Save Plan", "OlmYuE2LoadPlan": "YuE2 Load Plan",
    "OlmYuE2SaveRun": "YuE2 Save Run", "OlmYuE2LoadRun": "YuE2 Load Run"}
