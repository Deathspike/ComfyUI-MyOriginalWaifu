from contextlib import contextmanager

from .prompt import Prompt
from .rules import GroupRule, SwitchRule, TagRule, UnionRuleList
from .tags import Tag


class Anchor:
    """
    Semantic anchor reference used by the `Engine` for tag insertion.
    """

    def __init__(self, positive: Tag | None, negative: Tag | None):
        self.positive = positive
        self.negative = negative


class Engine:
    """
    Rule evaluation engine that applies declarative rules to positive and negative prompts.
    """

    def __init__(self, positive: Prompt, negative: Prompt):
        self._log = Logger()
        self._positive = positive
        self._negative = negative

    def _check_conditions(self, rule: GroupRule | SwitchRule | TagRule):
        enabled = True

        # Evaluate `any_of` condition.
        if rule.any_of:
            any_of = any(tag in self._positive for tag in rule.any_of)
            self._log.add("?", f"any_of({rule.any_of}) = {any_of}")
            enabled = enabled and any_of

        # Evaluate `all_of` condition.
        if rule.all_of:
            all_of = all(tag in self._positive for tag in rule.all_of)
            self._log.add("?", f"all_of({rule.all_of}) = {all_of}")
            enabled = enabled and all_of

        # Evaluate `none_of` condition.
        if rule.none_of:
            none_of = not any(tag in self._positive for tag in rule.none_of)
            self._log.add("?", f"none_of({rule.none_of}) = {none_of}")
            enabled = enabled and none_of

        return enabled

    def _get_anchor(self, anchor: Anchor, rule: GroupRule | SwitchRule | TagRule):
        positive = anchor.positive
        negative = anchor.negative

        # Determine the positive anchor.
        if rule.anchor:
            matches = (tag for tag in rule.anchor if tag in self._positive)
            positive = next(matches, None) or positive
            self._log.add("@", f"anchor({rule.anchor}) = {positive}")

        # Determine the negative anchor.
        if rule.anchor_negative:
            matches = (tag for tag in rule.anchor_negative if tag in self._negative)
            negative = next(matches, None) or negative
            self._log.add("@", f"anchor_negative({rule.anchor_negative}) = {negative}")

        return Anchor(positive, negative)

    def _run(self, anchor: Anchor, rule: GroupRule | SwitchRule | TagRule):
        if not self._check_conditions(rule):
            self._log.add("x", f"skipped (conditions not met)")
            return False
        elif isinstance(rule, GroupRule):
            self._run_group(self._get_anchor(anchor, rule), rule)
            return True
        elif isinstance(rule, SwitchRule):
            self._run_switch(self._get_anchor(anchor, rule), rule)
            return True
        else:
            self._run_tag(self._get_anchor(anchor, rule), rule)
            return True

    def _run_group(self, anchor: Anchor, group: GroupRule):
        for index, rule in enumerate(group.children):
            with self._log.enter(f"children[{index}]", rule):
                self._run(anchor, rule)

    def _run_switch(self, anchor: Anchor, switch: SwitchRule):
        default = None if switch.default is None else switch.children[switch.default]

        # Log the default branch.
        if default:
            prefix = f"children[{switch.default}]"
            suffix = f"({default.name})" if default.name else ""
            self._log.add("→", f"{prefix} set as default {suffix}")

        # Evaluate conditional branches.
        for index, rule in enumerate(switch.children):
            if default != rule:
                with self._log.enter(f"children[{index}]", rule):
                    if self._run(anchor, rule):
                        return

        # Evaluate the default branch.
        if default:
            with self._log.enter(f"default", default):
                self._run(anchor, default)

    def _run_tag(self, anchor: Anchor, rule: TagRule):
        # Evaluate add mutations.
        if rule.add:
            self._log.add("+", f"add: {rule.add}")
            self._positive.add(anchor.positive, rule.add)
        if rule.add_negative:
            self._log.add("+", f"add_negative: {rule.add_negative}")
            self._negative.add(anchor.negative, rule.add_negative)

        # Evaluate remove mutations.
        if rule.remove:
            self._log.add("-", f"remove: {rule.remove}")
            self._positive.remove(rule.remove)
        if rule.remove_negative:
            self._log.add("-", f"remove_negative: {rule.remove_negative}")
            self._negative.remove(rule.remove_negative)

    def run(self, rules: UnionRuleList):
        for index, rule in enumerate(rules):
            with self._log.enter(f":root[{index}]", rule):
                self._run(Anchor(None, None), rule)


class Logger:
    """
    Helper that tracks rule paths and prints indented debug output.
    """

    def __init__(self):
        self._depth = 0

    def _enter(self, property: str, rule: GroupRule | SwitchRule | TagRule):
        indent = "  " * self._depth
        prefix = self._get_rule_prefix(rule)
        suffix = f"({rule.name})" if rule.name else ""
        print(f"{indent}{prefix} {property} {{{self._get_rule_type(rule)}}} {suffix}")

    def _get_rule_prefix(self, rule: GroupRule | SwitchRule | TagRule):
        if isinstance(rule, GroupRule) or isinstance(rule, SwitchRule):
            return ">"
        else:
            return "$"

    def _get_rule_type(self, rule: GroupRule | SwitchRule | TagRule):
        if isinstance(rule, GroupRule):
            return "group"
        elif isinstance(rule, SwitchRule):
            return "switch"
        else:
            return "tag"

    def add(self, prefix: str, message: str):
        indent = "  " * self._depth
        print(f"{indent}{prefix} {message}")

    @contextmanager
    def enter(self, property: str, rule: GroupRule | SwitchRule | TagRule):
        try:
            self._enter(property, rule)
            self._depth += 1
            yield
        finally:
            self._depth -= 1
