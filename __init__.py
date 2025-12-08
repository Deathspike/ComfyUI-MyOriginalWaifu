from .comfy.nodes import ClipProvider, TextProvider

NODE_CLASS_MAPPINGS: dict[str, object] = {
    "MyOriginalWaifu": TextProvider,
    "MyOriginalWaifuCLIP": ClipProvider,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MyOriginalWaifu": "My Original Waifu",
    "MyOriginalWaifuCLIP": "My Original Waifu (CLIP)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
