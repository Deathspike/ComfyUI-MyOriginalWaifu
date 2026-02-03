from abc import ABC, abstractmethod
from contextlib import contextmanager
from re import match

from .tags import TagList
from .utils.typing import Typing


class Auditor:
    """
    Helper that tracks rule paths and raises validation errors.
    """

    def __init__(self, name: str):
        self._path = [name]

    def _add_node_name(self, name: str | None):
        if name:
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
        try:
            self._path.append(f"[{index}]")
            name = self._get_node_name(node)
            self._add_node_name(name)
            yield name
        finally:
            self._path.pop()

    @contextmanager
    def enter_prop(self, name: str):
        try:
            self._path.append(f".{name}")
            yield
        finally:
            self._path.pop()

    def fail(self, message: str):
        raise ValueError(f"Error at {''.join(self._path)}, {message}")

    def fail_node(self, index: int, message: str):
        with self.enter_node(index, {}):
            self.fail(message)

    def fail_prop(self, name: str, message: str):
        with self.enter_prop(name):
            self.fail(message)


class BaseRule(ABC):
    """
    Base rule that supports anchors with `anchor` and `anchor_negative`, and conditions with `any_of`, `all_of` and `none_of`.
    """

    @abstractmethod
    def __init__(self, auditor: Auditor, name: str | None, node: dict[object, object]):
        self.name = name
        self.anchor = None
        self.anchor_negative = None
        self.any_of = None
        self.all_of = None
        self.none_of = None

        # Parse node properties.
        for key, value in node.items():
            if not isinstance(key, str):
                auditor.fail("property names must be strings")
            elif key == "anchor":
                self.anchor = self._parse_tags(auditor, key, value, False)
            elif key == "anchor_negative":
                self.anchor_negative = self._parse_tags(auditor, key, value, False)
            elif key == "any_of":
                self.any_of = self._parse_tags(auditor, key, value, False)
            elif key == "all_of":
                self.all_of = self._parse_tags(auditor, key, value, False)
            elif key == "none_of":
                self.none_of = self._parse_tags(auditor, key, value, False)
            elif key not in {"name", "type"}:
                self._handle_property(auditor, key, value)

        # Validate contradictions.
        if self.none_of:
            if self.any_of and any(tag in self.any_of for tag in self.none_of):
                auditor.fail_prop("none_of", "none_of cannot conflict with any_of")
            elif self.all_of and any(tag in self.all_of for tag in self.none_of):
                auditor.fail_prop("none_of", "none_of cannot conflict with all_of")

    def _handle_property(self, auditor: Auditor, key: str, value: object) -> None:
        auditor.fail_prop(key, f"'{key}' property is not supported")

    def _parse_tags(self, auditor: Auditor, key: str, value: object, weights: bool):
        if not isinstance(value, str) and not Typing.is_list(value):
            auditor.fail_prop(key, f"{key} must be a list or string")
        else:
            tags = TagList(value)
            if not len(tags):
                auditor.fail_prop(key, f"{key} cannot be empty")
            elif not weights and tags.uses_weight():
                auditor.fail_prop(key, f"{key} cannot contain weights")
            else:
                return tags


class GroupRule(BaseRule):
    """
    Group rule that runs *all* rules in `children` whose conditions match.
    """

    def __init__(self, auditor: Auditor, name: str | None, node: dict[object, object]):
        if "children" not in node:
            auditor.fail("children property is required")
        else:
            super().__init__(auditor, name, node)

    def _handle_property(self, auditor: Auditor, key: str, value: object):
        if key == "children":
            self.children = self._parse_children(auditor, value)
        else:
            super()._handle_property(auditor, key, value)

    def _parse_children(self, auditor: Auditor, children: object):
        if not Typing.is_list(children):
            auditor.fail_prop("children", "children must be a list")
        with auditor.enter_prop("children"):
            return UnionRuleList(auditor, children)


class SwitchRule(BaseRule):
    """
    Switch rule that runs the *first* rule in `children` whose conditions match, or the optional *default* rule.
    """

    def __init__(self, auditor: Auditor, name: str | None, node: dict[object, object]):
        if "children" not in node:
            auditor.fail("children property is required")
        else:
            super().__init__(auditor, name, node)

    def _handle_property(self, auditor: Auditor, key: str, value: object):
        if key == "children":
            self.children, self.default = self._parse_children(auditor, value)
        else:
            super()._handle_property(auditor, key, value)

    def _has_conditions(self, node: dict[object, object]):
        return {"any_of", "all_of", "none_of"} & node.keys()

    def _parse_children(self, auditor: Auditor, children: object):
        if not Typing.is_list(children):
            auditor.fail_prop("children", "children must be a list")
        with auditor.enter_prop("children"):
            default_index: int | None = None
            nodes: list[object] = []

            # Parse child nodes and resolve the optional default node.
            for index, node in enumerate(children):
                if not Typing.is_dict(node):
                    auditor.fail_node(index, "rule must be a dict")
                with auditor.enter_node(index, node):
                    default = node.get("default", None)
                    if default is None:
                        nodes.append(self._validate_conditions(auditor, node))
                    elif not isinstance(default, bool):
                        auditor.fail_prop("default", "default must be a bool")
                    elif default is not True:
                        auditor.fail_prop("default", "default must be true")
                    elif default_index is not None:
                        auditor.fail("default rule is already in use")
                    elif self._has_conditions(node):
                        auditor.fail("default rule cannot contain conditions")
                    else:
                        default_index = index
                        copy = node.copy()
                        del copy["default"]
                        nodes.append(copy)

            # Parse child nodes into rules.
            children = UnionRuleList(auditor, nodes)
            return children, default_index

    def _validate_conditions(self, auditor: Auditor, node: dict[object, object]):
        if not self._has_conditions(node):
            auditor.fail("branch rule cannot omit conditions")
        else:
            return node


class TagRule(BaseRule):
    """
    Tag rule that supports mutations with `add`, `add_negative`, `remove` and `remove_negative`.
    """

    def __init__(self, auditor: Auditor, name: str | None, node: dict[object, object]):
        if not {"add", "add_negative", "remove", "remove_negative"} & node.keys():
            auditor.fail("a tag property is required")
        else:
            self.add = None
            self.add_negative = None
            self.remove = None
            self.remove_negative = None
            super().__init__(auditor, name, node)

    def _handle_property(self, auditor: Auditor, key: str, value: object):
        if key == "add":
            self.add = self._parse_tags(auditor, key, value, True)
        elif key == "add_negative":
            self.add_negative = self._parse_tags(auditor, key, value, True)
        elif key == "remove":
            self.remove = self._parse_tags(auditor, key, value, False)
        elif key == "remove_negative":
            self.remove_negative = self._parse_tags(auditor, key, value, False)
        else:
            super()._handle_property(auditor, key, value)


class UnionRuleList(list[GroupRule | SwitchRule | TagRule]):
    """
    Union list of `GroupRule`, `SwitchRule` and `TagRule` rules.
    """

    def __init__(self, auditor: Auditor, nodes: list[object] | tuple[object]):
        super().__init__(self._parse(auditor, nodes))

    def _parse(self, auditor: Auditor, nodes: list[object] | tuple[object]):
        for index, node in enumerate(nodes):
            if not Typing.is_dict(node):
                auditor.fail_node(index, "rule must be a dict")
            with auditor.enter_node(index, node) as name:
                type = node.get("type")
                if type is None:
                    yield TagRule(auditor, name, node)
                elif type == "group":
                    yield GroupRule(auditor, name, node)
                elif type == "switch":
                    yield SwitchRule(auditor, name, node)
                else:
                    auditor.fail_prop("type", f"'{type}' type is not supported")
