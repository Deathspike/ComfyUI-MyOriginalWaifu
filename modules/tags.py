from re import search
from typing import Iterable, Iterator

from .utils.typing import Typing


class _Group:
    """
    Group used by `_TagBuilder` and `_TagListParser` to calculate `Tag` piece weights.
    """

    def __init__(self, defaultWeight: float, parent: "_Group | None"):
        self.defaultWeight = defaultWeight
        self.parent = parent
        self.weight = defaultWeight

    def calculate_weight(self) -> float:
        if self.parent:
            return self.parent.calculate_weight() * self.weight
        else:
            return self.weight


class _TagBuilder:
    """
    Builder that accumulates pieces, associates groups, and creates `Tag` objects.
    """

    def __init__(self, group: _Group):
        self._groups = [group]
        self._pieces = [""]

    def append(self, char: str):
        self._pieces[-1] += char

    def enter(self, group: _Group):
        self._groups.append(group)
        self._pieces.append("")

    def validate_and_build(self):
        index = 1

        # Clean leading whitespaces.
        while True:
            if not self._pieces:
                return None
            elif not self._pieces[0].strip():
                self._groups.pop(0)
                self._pieces.pop(0)
            else:
                break

        # Clean remaining whitespaces.
        while index < len(self._pieces):
            if not self._pieces[index]:
                self._groups.pop(index)
                self._pieces.pop(index)
            elif not self._pieces[index].strip():
                self._pieces[index - 1] = self._pieces[index - 1].rstrip() + " "
                self._groups.pop(index)
                self._pieces.pop(index)
            elif self._pieces[index][0].isspace():
                self._pieces[index - 1] = self._pieces[index - 1].rstrip() + " "
                self._pieces[index] = self._pieces[index].lstrip()
                index += 1
            else:
                index += 1

        # Clean whitespaces on the outer edges.
        self._pieces[0] = self._pieces[0].lstrip()
        self._pieces[-1] = self._pieces[-1].rstrip()

        # Create the validated tag.
        name = "".join(self._pieces)
        pieces = zip(self._pieces, (group.calculate_weight() for group in self._groups))
        return Tag(name, list(pieces))


class _TagListParser:
    """
    Iterator that parses an input string to `Tag` objects.
    """

    def __init__(self, value: str):
        self._value = value

    def __iter__(self):
        self._group = _Group(1, None)
        self._index = 0
        self._tags = [_TagBuilder(self._group)]
        return self._parse()

    def _parse(self):
        while self._index < len(self._value):
            current = self._value[self._index]
            previous = self._value[self._index - 1] if self._index else None

            # Parse each input character.
            if current == "(" and previous != "\\":
                self._group = _Group(1.1, self._group)
                self._tags[-1].enter(self._group)
            elif current == ")" and previous != "\\":
                self._group = self._group.parent or _Group(1, None)
                self._tags[-1].enter(self._group)
            elif current == ":" and self._parse_weight():
                self._group = _Group(self._group.defaultWeight, self._group.parent)
                self._tags[-1].enter(self._group)
            elif current == "," or current == "\n":
                self._group = _Group(self._group.defaultWeight, self._group.parent)
                self._tags.append(_TagBuilder(self._group))
            else:
                self._tags[-1].append(current)

            # Increment the index.
            self._index += 1

        # Validate and build tags.
        for tag_builder in self._tags:
            tag = tag_builder.validate_and_build()
            if tag:
                yield tag

    def _parse_weight(self):
        start = self._index + 1
        end = start

        # Accumulate the weight.
        while end < len(self._value):
            current = self._value[end]
            if current == "." or current.isdigit() or current.isspace():
                end += 1
            else:
                break

        # Find the weight.
        value = self._value[start:end]
        match = search(r"\d*\.\d+|\d+\.?\d*", value)

        # Parse the weight.
        if match:
            self._group.weight = float(match.group(0))
            self._index += len(value.rstrip())
            return True
        else:
            return False


class _TagListRenderer:
    """
    Iterator that renders an iterable of `Tag` objects into a weighted-tag string.
    """

    def __init__(self, enable_filter: bool, tags: Iterable["Tag"]):
        self._enable_filter = enable_filter
        self._tags = tags

    def __iter__(self):
        return self._render()

    def _get_filtered(self):
        if self._enable_filter:
            return (tag for tag in self._tags if tag.enabled)
        else:
            return self._tags

    def _get_group_end(self, weight: float):
        if weight != 1.1:
            return f":{weight:.2g})"
        else:
            return ")"

    def _render(self):
        divide = False
        weight = 1

        for tag in self._get_filtered():
            # Emit each weighted piece.
            for piece_text, piece_weight in tag.pieces:
                if piece_weight != weight:
                    if weight != 1:
                        yield self._get_group_end(weight)
                    if divide:
                        yield ", "
                        divide = False
                    if piece_weight != 1:
                        yield "("
                    weight = piece_weight
                elif divide:
                    yield ", "
                    divide = False

                yield piece_text

            # Divide the next tag.
            divide = True

        # Emit trailing group.
        if weight != 1:
            yield self._get_group_end(weight)


class Tag:
    """
    Tag with a name, weighted pieces, and a semantic weight.
    """

    def __init__(self, name: str, pieces: list[tuple[str, float]]):
        self.enabled = True
        self.name = name
        self.pieces = pieces
        self.weight = max(piece[1] for piece in pieces)

    def __eq__(self, value: object):
        if isinstance(value, Tag):
            return value.name == self.name
        else:
            return False

    def __str__(self):
        return "".join(_TagListRenderer(False, (self,)))

    def uses_weight(self):
        return any(piece[1] != 1 for piece in self.pieces)


class TagList(list[Tag]):
    """
    Ordered list of `Tag` objects parsed from an input.
    """

    def __init__(self, tags: list[object] | tuple[object] | str):
        super().__init__(self._parse(tags))

    def __str__(self):
        return "".join(_TagListRenderer(True, self))

    def _parse(self, tags: list[object] | tuple[object] | str):
        if not isinstance(tags, str):
            return self._parse_list(tags)
        else:
            return _TagListParser(tags)

    def _parse_list(self, tags: list[object] | tuple[object]) -> Iterator[Tag]:
        for value in tags:
            if Typing.is_list(value):
                yield from self._parse_list(value)
            elif isinstance(value, (bool, float, int)):
                yield from _TagListParser(str(value))
            elif isinstance(value, str):
                yield from _TagListParser(value)

    def uses_weight(self):
        return any(tag.uses_weight() for tag in self)
