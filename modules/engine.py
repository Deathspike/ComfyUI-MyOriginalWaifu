from contextlib import contextmanager

from .prompt import Prompt
from .rules import GroupRule, SwapRule, SwitchRule, TagRule, UnionRuleList
from .tags import Tag


class _Anchor:
    """
    Semantic anchor used by the `Engine` for tag insertion.
    """

    def __init__(self, positive: Tag | None, negative: Tag | None):
        self.positive = positive
        self.negative = negative


class _Logger:
    """
    Helper that tracks rule paths and prints indented debug output.
    """

    def __init__(self):
        self._depth = 0

    def _enter(self, property: str, rule: GroupRule | SwapRule | SwitchRule | TagRule):
        indent = "  " * self._depth
        prefix = self._get_rule_prefix(rule)
        suffix = f"({rule.name})" if rule.name else ""
        print(f"{indent}{prefix} {property} {{{self._get_rule_type(rule)}}} {suffix}")

    def _get_rule_prefix(self, rule: GroupRule | SwapRule | SwitchRule | TagRule):
        if isinstance(rule, GroupRule) or isinstance(rule, SwitchRule):
            return ">"
        else:
            return "$"

    def _get_rule_type(self, rule: GroupRule | SwapRule | SwitchRule | TagRule):
        if isinstance(rule, GroupRule):
            return "group"
        elif isinstance(rule, SwapRule):
            return "swap"
        elif isinstance(rule, SwitchRule):
            return "switch"
        else:
            return "tag"

    def add(self, prefix: str, message: str):
        indent = "  " * self._depth
        print(f"{indent}{prefix} {message}")

    @contextmanager
    def enter(self, property: str, rule: GroupRule | SwapRule | SwitchRule | TagRule):
        try:
            self._enter(property, rule)
            self._depth += 1
            yield
        finally:
            self._depth -= 1


class Engine:
    """
    Rule evaluation engine that applies declarative rules to positive and negative prompts.
    """

    def __init__(self, positive: Prompt, negative: Prompt):
        self._log = _Logger()
        self._positive = positive
        self._negative = negative

    def _check_conditions(self, rule: GroupRule | SwapRule | SwitchRule | TagRule):
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

        # Validate conditions.
        if not enabled:
            self._log.add("x", "skipped (conditions not met)")
            return False
        else:
            return True

    def _get_anchor(self, anchor: _Anchor, rule: GroupRule | SwitchRule | TagRule):
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

        return _Anchor(positive, negative)

    def _run(self, anchor: _Anchor, rule: GroupRule | SwapRule | SwitchRule | TagRule):
        if not self._check_conditions(rule):
            return False
        elif isinstance(rule, GroupRule):
            return self._run_group(self._get_anchor(anchor, rule), rule)
        elif isinstance(rule, SwapRule):
            return self._run_swap(anchor, rule)
        elif isinstance(rule, SwitchRule):
            return self._run_switch(self._get_anchor(anchor, rule), rule)
        else:
            return self._run_tag(self._get_anchor(anchor, rule), rule)

    def _run_group(self, anchor: _Anchor, group: GroupRule):
        # Evaluate children.
        for index, rule in enumerate(group.children):
            with self._log.enter(f"children[{index}]", rule):
                self._run(anchor, rule)

        return True

    def _run_swap(self, anchor: _Anchor, swap: SwapRule):
        # Evaluate `match` condition.
        positive = next((tag for tag in swap.match if tag in self._positive), None)
        negative = positive if positive in self._negative else None
        self._log.add("?", f"match({swap.match}) = {positive}")

        # Validate conditions.
        if not positive:
            self._log.add("x", "skipped (no match)")
            return False
        else:
            # Evaluate add.
            if swap.add:
                self._log.add("=", f"swap({positive}): {swap.add}")
                self._positive.add(positive, True, swap.add)

            # Evaluate add_negative.
            if swap.add_negative:
                if negative:
                    tags = swap.add_negative
                    self._log.add("=", f"swap_negative({negative}): {tags}")
                    self._negative.add(negative, True, tags)
                else:
                    self._log.add("+", f"add_negative: {swap.add_negative}")
                    self._negative.add(anchor.negative, True, swap.add_negative)

            # Remove matches.
            self._positive.remove((positive,))
            self._negative.remove((negative,)) if negative else None
            return True

    def _run_switch(self, anchor: _Anchor, switch: SwitchRule):
        default = None if switch.default is None else switch.children[switch.default]

        # Log the default branch.
        if default:
            prefix = f"children[{switch.default}]"
            suffix = f"({default.name})" if default.name else ""
            self._log.add("→", f"{prefix} set as default {suffix}")

        # Evaluate conditional children.
        for index, rule in enumerate(switch.children):
            if default != rule:
                with self._log.enter(f"children[{index}]", rule):
                    if self._run(anchor, rule):
                        return True

        # Evaluate the default branch.
        if default:
            with self._log.enter("default", default):
                self._run(anchor, default)

        return True

    def _run_tag(self, anchor: _Anchor, tag: TagRule):
        # Evaluate add mutations.
        if tag.add:
            self._log.add("+", f"add: {tag.add}")
            self._positive.add(anchor.positive, True, tag.add)
        if tag.add_negative:
            self._log.add("+", f"add_negative: {tag.add_negative}")
            self._negative.add(anchor.negative, True, tag.add_negative)

        # Evaluate remove mutations.
        if tag.remove:
            self._log.add("-", f"remove: {tag.remove}")
            self._positive.remove(tag.remove)
        if tag.remove_negative:
            self._log.add("-", f"remove_negative: {tag.remove_negative}")
            self._negative.remove(tag.remove_negative)

        # Evaluate tmp mutations.
        if tag.tmp:
            self._log.add("~", f"tmp: {tag.tmp}")
            self._positive.add(anchor.positive, False, tag.tmp)
            self._negative.add(anchor.negative, False, tag.tmp)

        return True

    def run(self, rules: UnionRuleList):
        for index, rule in enumerate(rules):
            with self._log.enter(f":root[{index}]", rule):
                self._run(_Anchor(None, None), rule)
