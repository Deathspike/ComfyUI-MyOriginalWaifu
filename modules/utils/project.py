from os import path
from tomllib import load
from typing import Any


def get_project_info():
    base_path = path.dirname(__file__)
    full_path = path.join(base_path, "../../pyproject.toml")
    with open(full_path, "rb") as file_stream:
        file_info: Any = load(file_stream)
        displayName = str(file_info.get("tool").get("comfy").get("DisplayName"))
        version = str(file_info.get("project").get("version"))
        return displayName, version
