from re import split


class Tag:
    """
    Tag with an optional weight modifier.
    """

    def __init__(self, name: str, weight: float = 1):
        self.name = name
        self.weight = weight

    def __eq__(self, value: object):
        if isinstance(value, Tag):
            return value.name == self.name
        elif isinstance(value, str):
            return value == self.name
        else:
            return False

    def __str__(self):
        return self.name


class TagList(list[Tag]):
    """
    Ordered list of `Tag` objects parsed from an input.
    """

    def __init__(self, tags: list[object] | tuple[object] | str):
        super().__init__(self._parse(tags))

    def __str__(self):
        return ", ".join(tag.name for tag in self)

    def _parse(self, tags: list[object] | tuple[object] | str):
        if not isinstance(tags, str):
            return self._parse_list(tags)
        else:
            return self._parse_str(tags)

    def _parse_list(self, tags: list[object] | tuple[object]):
        result: list[Tag] = []

        for value in tags:
            if isinstance(value, str):
                result.extend(self._parse_str(value))

        return result

    def _parse_str(self, tags: str):
        result: list[Tag] = []

        for tag in split(r"[,\n]", tags):
            clean_tag = tag.strip()
            if clean_tag:
                result.append(Tag(clean_tag))

        return result
