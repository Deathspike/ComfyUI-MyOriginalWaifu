from ..modules.pipeline import Pipeline
from ..modules.prompt import Prompt


class MyOriginalWaifu:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive": ("STRING", {"multiline": True, "dynamicPrompts": True}),
                "negative": ("STRING", {"multiline": True, "dynamicPrompts": True}),
            }
        }

    CATEGORY = "deathspike"
    FUNCTION = "process"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive", "negative")

    @classmethod
    def IS_CHANGED(cls, positive: str, negative: str):
        return Pipeline.DEFAULT.get_cache_key(positive, negative)

    def process(self, positive: str, negative: str):
        positive_prompt = Prompt(positive)
        negative_prompt = Prompt(negative)
        Pipeline.DEFAULT.run(positive_prompt, negative_prompt)

        positive = str(positive_prompt)
        negative = str(negative_prompt)
        return (positive, negative)
