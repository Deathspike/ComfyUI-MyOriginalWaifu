from abc import ABC, abstractmethod
from typing import Optional
from .utils.typing import Typing
from .core import Context
from .tags import TagList


class ConditionRule(ABC):
    @abstractmethod
    def __init__(self, context: Context, rule: dict[object, object]):
        self.any_of = None
        self.all_of = None
        self.none_of = None

        for key, value in rule.items():
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

    @abstractmethod
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
    def __init__(self, context: Context, rule: dict[object, object]):
        if "children" not in rule:
            context.fail("children property is required")
        else:
            super().__init__(context, rule)

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
    def __init__(self, context: Context, rule: dict[object, object]):
        if "children" not in rule:
            context.fail("children property is required")
        else:
            super().__init__(context, rule)

    def _handle_property(self, context: Context, key: str, value: object):
        if key == "children":
            self.children, self.default = self._parse_children(context, value)
        else:
            super()._handle_property(context, key, value)

    def _parse_children(self, context: Context, children: object):
        if not Typing.is_list(children):
            context.fail_prop("children", "children must be a list")
        with context.enter_prop("children"):
            default_index: Optional[int] = None
            rules: list[object] = []

            for index, rule in enumerate(children):
                if not Typing.is_dict(rule):
                    context.fail_rule(index, "rule must be a dict")
                with context.enter_rule(index, rule):
                    default = rule.get("default", None)
                    if default is None:
                        rules.append(rule)
                    elif not isinstance(default, bool):
                        context.fail_prop("default", "default must be a bool")
                    elif default is not True:
                        context.fail_prop("default", "default must be true")
                    elif default_index is not None:
                        context.fail("default rule is already in use")
                    elif {"any_of", "all_of", "none_of"} & rule.keys():
                        context.fail("default rule cannot contain conditions")
                    else:
                        default_index = index
                        copy = rule.copy()
                        copy.pop("default", None)
                        rules.append(copy)

            children = UnionRuleList(context, rules)
            return children, default_index


class TagRule(ConditionRule):
    def __init__(self, context: Context, rule: dict[object, object]):
        if not {"add", "add_negative", "remove", "remove_negative"} & rule.keys():
            context.fail("a tag property is required")
        else:
            self.add = None
            self.add_negative = None
            self.remove = None
            self.remove_negative = None
            super().__init__(context, rule)

    def _handle_property(self, context: Context, key: str, value: object):
        if key == "add":
            self.add = self._parse_tags(context, key, value, True)
        elif key == "add_negative":
            self.add_negative = self._parse_tags(context, key, value, True)
        elif key == "remove":
            self.remove = self._parse_tags(context, key, value, True)
        elif key == "remove_negative":
            self.remove_negative = self._parse_tags(context, key, value, True)
        else:
            super()._handle_property(context, key, value)


class UnionRuleList(list[GroupRule | SwitchRule | TagRule]):
    def __init__(self, context: Context, rules: list[object] | tuple[object]):
        self.extend(self._parse(context, rules))

    def _parse(self, context: Context, rules: list[object] | tuple[object]):
        result: list[GroupRule | SwitchRule | TagRule] = []

        for index, rule in enumerate(rules):
            if not Typing.is_dict(rule):
                context.fail_rule(index, "rule must be a dict")
            with context.enter_rule(index, rule):
                result.append(self._parse_rule(context, rule))

        return result

    def _parse_rule(self, context: Context, rule: dict[object, object]):
        type = rule.get("type")
        if type is None:
            return TagRule(context, rule)
        elif type == "group":
            return GroupRule(context, rule)
        elif type == "switch":
            return SwitchRule(context, rule)
        else:
            context.fail_prop("type", f"'{type}' type is not supported")
