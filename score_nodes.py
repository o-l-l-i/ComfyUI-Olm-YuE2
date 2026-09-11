"""Optional score presentation; ordinary ABC text remains the workflow state."""


class ScorePreview:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"plan": ("YUE2_PLAN",)}}

    RETURN_TYPES = ()
    CATEGORY = "YuE2/score"
    FUNCTION = "preview"
    OUTPUT_NODE = True
    DESCRIPTION = "Inspect a plan in the optional YuE2 Score sidebar. Enable score tools in Settings > YuE2."

    def preview(self, plan):
        value = plan.value
        return {"ui": {"yue2_score": [{
            "abc": value.abc or "",
            "mode": value.request.cot,
            "seed": value.request.seed,
            "abc_tokens": len(value.abc_ids),
            "truncated": value.truncated,
        }]}}


class ABCEditor:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"abc": ("STRING", {"multiline": True, "default": "",
            "tooltip": "ABC text, preserved exactly. Connect to Apply Edited Score to rebuild a plan."})}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("abc",)
    CATEGORY = "YuE2/score"
    FUNCTION = "text"
    DESCRIPTION = "Author ABC text for Apply Edited Score. Optional notation preview is available in the YuE2 Score sidebar."

    def text(self, abc):
        return (abc,)


NODE_CLASS_MAPPINGS = {"OlmYuE2ScorePreview": ScorePreview, "OlmYuE2ABCEditor": ABCEditor}
NODE_DISPLAY_NAME_MAPPINGS = {"OlmYuE2ScorePreview": "YuE2 Score Preview", "OlmYuE2ABCEditor": "YuE2 ABC Editor"}
