from contextlib import contextmanager
from re import match


class Context:
    def __init__(self, name: str):
        self._path = [name]

    def _add_node_name(self, name: str | None):
        if name is not None:
            self._path[-1] += f"({name})"

    def _get_clean_name(self, name: str):
        clean_name = " ".join(name.split())
        if not clean_name:
            self.fail_prop("name", "name cannot be empty")
        elif not match(r"^[\w \-]+$", clean_name):
            self.fail_prop("name", "name contains invalid characters")
        else:
            return clean_name

    def _get_node_name(self, node: dict[object, object]):
        name = node.get("name")
        if name is None:
            return None
        elif not isinstance(name, str):
            self.fail_prop("name", "name must be a string")
        else:
            return self._get_clean_name(name)

    @contextmanager
    def enter_node(self, index: int, node: dict[object, object]):
        self._path.append(f"[{index}]")
        try:
            name = self._get_node_name(node)
            self._add_node_name(name)
            yield name
        finally:
            self._path.pop()

    @contextmanager
    def enter_prop(self, name: str):
        self._path.append(f".{name}")
        try:
            yield
        finally:
            self._path.pop()

    def fail(self, message: str):
        path = "".join(self._path)
        raise ValueError(f"Error at {path}, {message}")

    def fail_node(self, index: int, message: str):
        with self.enter_node(index, {}):
            self.fail(message)

    def fail_prop(self, name: str, message: str):
        with self.enter_prop(name):
            self.fail(message)
