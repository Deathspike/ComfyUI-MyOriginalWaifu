from os import path
from tomllib import load


def get_project_version():
    base_path = path.dirname(__file__)
    full_path = path.join(base_path, "../../pyproject.toml")
    with open(full_path, "rb") as file_stream:
        project = load(file_stream).get("project")
        version = str(project.get("version")) if project else "0.0.0"
        return version
