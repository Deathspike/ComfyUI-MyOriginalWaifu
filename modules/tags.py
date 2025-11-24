from re import split


class Tag:
    def __init__(self, name: str, weight: float):
        self.name = name
        self.weight = weight


class TagList(list[Tag]):
    def __init__(self, tags: list[object] | tuple[object] | str):
        super().__init__(self._parse(tags))

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
                result.append(Tag(clean_tag, 1))

        return result
