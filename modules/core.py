from contextlib import contextmanager
from re import match


class Context:
    def __init__(self, name: str):
        self._path = [name]

    def _get_clean_name(self, name: str):
        clean_name = " ".join(name.split())
        if not clean_name:
            self.fail_prop("name", "name cannot be empty")
        elif not match(r"^[\w \-]+$", clean_name):
            self.fail_prop("name", "name contains invalid characters")
        else:
            return clean_name

    def _get_rule_suffix(self, rule: dict[object, object]):
        name = rule.get("name")
        if name is None:
            return ""
        elif not isinstance(name, str):
            self.fail_prop("name", "name must be a string")
        else:
            return f"({self._get_clean_name(name)})"

    @contextmanager
    def enter_rule(self, index: int, rule: dict[object, object]):
        self._path.append(f"[{index}]")
        try:
            self._path[-1] += self._get_rule_suffix(rule)
            yield
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

    def fail_rule(self, index: int, message: str):
        with self.enter_rule(index, {}):
            self.fail(message)

    def fail_prop(self, name: str, message: str):
        with self.enter_prop(name):
            self.fail(message)
