from abc import ABC, abstractmethod
from .utils.typing import Typing
from .core import Context
from .tags import TagList


class ConditionRule(ABC):
    """
    Base rule that supports `any_of`, `all_of` and `none_of` conditions.
    """

    @abstractmethod
    def __init__(self, context: Context, name: str | None, node: dict[object, object]):
        self.name = name
        self.any_of = None
        self.all_of = None
        self.none_of = None

        for key, value in node.items():
            if not isinstance(key, str):
                context.fail("property names must be strings")
            elif key == "any_of":
                self.any_of = self._parse_tags(context, key, value, False)
            elif key == "all_of":
                self.all_of = self._parse_tags(context, key, value, False)
            elif key == "none_of":
                self.none_of = self._parse_tags(context, key, value, False)
            elif key not in {"name", "type"}:
                self._handle_property(context, key, value)

    def _handle_property(self, context: Context, key: str, value: object) -> None:
        context.fail_prop(key, f"'{key}' property is not supported")

    def _parse_tags(self, context: Context, key: str, value: object, weights: bool):
        if not isinstance(value, str) and not Typing.is_list(value):
            context.fail_prop(key, f"{key} must be a list or string")
        else:
            tags = TagList(value)
            if not len(tags):
                context.fail_prop(key, f"{key} cannot be empty")
            elif not weights and any(tag.weight != 1 for tag in tags):
                context.fail_prop(key, f"{key} cannot contain weights")
            else:
                return tags


class GroupRule(ConditionRule):
    """
    Structural rule that runs *all* rules in `children` whose conditions match.
    """

    def __init__(self, context: Context, name: str | None, node: dict[object, object]):
        if "children" not in node:
            context.fail("children property is required")
        else:
            super().__init__(context, name, node)

    def _handle_property(self, context: Context, key: str, value: object):
        if key == "children":
            self.children = self._parse_children(context, value)
        else:
            super()._handle_property(context, key, value)

    def _parse_children(self, context: Context, children: object):
        if not Typing.is_list(children):
            context.fail_prop("children", "children must be a list")
        with context.enter_prop("children"):
            return UnionRuleList(context, children)


class SwitchRule(ConditionRule):
    """
    Structural rule that runs the *first* rule in `children` whose conditions match, or the *default* rule.
    """

    def __init__(self, context: Context, name: str | None, node: dict[object, object]):
        if "children" not in node:
            context.fail("children property is required")
        else:
            super().__init__(context, name, node)

    def _handle_property(self, context: Context, key: str, value: object):
        if key == "children":
            self.children, self.default = self._parse_children(context, value)
        else:
            super()._handle_property(context, key, value)

    def _parse_children(self, context: Context, children: object):
        if not Typing.is_list(children):
            context.fail_prop("children", "children must be a list")
        with context.enter_prop("children"):
            default_index: int | None = None
            nodes: list[object] = []

            # Parse child nodes and resolve the optional default node.
            for index, node in enumerate(children):
                if not Typing.is_dict(node):
                    context.fail_node(index, "rule must be a dict")
                with context.enter_node(index, node):
                    default = node.get("default", None)
                    if default is None:
                        nodes.append(node)
                    elif not isinstance(default, bool):
                        context.fail_prop("default", "default must be a bool")
                    elif default is not True:
                        context.fail_prop("default", "default must be true")
                    elif default_index is not None:
                        context.fail("default rule is already in use")
                    elif {"any_of", "all_of", "none_of"} & node.keys():
                        context.fail("default rule cannot contain conditions")
                    else:
                        default_index = index
                        copy = node.copy()
                        copy.pop("default", None)
                        nodes.append(copy)

            # Parse child nodes into rules.
            children = UnionRuleList(context, nodes)
            return children, default_index


class TagRule(ConditionRule):
    """
    Leaf rule that supports `add`, `add_negative`, `remove` and `remove_negative` modifications.
    """

    def __init__(self, context: Context, name: str | None, node: dict[object, object]):
        if not {"add", "add_negative", "remove", "remove_negative"} & node.keys():
            context.fail("a tag property is required")
        else:
            self.add = None
            self.add_negative = None
            self.remove = None
            self.remove_negative = None
            super().__init__(context, name, node)

    def _handle_property(self, context: Context, key: str, value: object):
        if key == "add":
            self.add = self._parse_tags(context, key, value, True)
        elif key == "add_negative":
            self.add_negative = self._parse_tags(context, key, value, True)
        elif key == "remove":
            self.remove = self._parse_tags(context, key, value, False)
        elif key == "remove_negative":
            self.remove_negative = self._parse_tags(context, key, value, False)
        else:
            super()._handle_property(context, key, value)


class UnionRuleList(list[GroupRule | SwitchRule | TagRule]):
    """
    Typed list of parsed `GroupRule`, `SwitchRule` and `TagRule` rules.
    """

    def __init__(self, context: Context, nodes: list[object] | tuple[object]):
        super().__init__(self._parse(context, nodes))

    def _parse(self, context: Context, nodes: list[object] | tuple[object]):
        result: list[GroupRule | SwitchRule | TagRule] = []

        for index, node in enumerate(nodes):
            if not Typing.is_dict(node):
                context.fail_node(index, "rule must be a dict")
            with context.enter_node(index, node) as name:
                type = node.get("type")
                if type is None:
                    result.append(TagRule(context, name, node))
                elif type == "group":
                    result.append(GroupRule(context, name, node))
                elif type == "switch":
                    result.append(SwitchRule(context, name, node))
                else:
                    context.fail_prop("type", f"'{type}' type is not supported")

        return result
