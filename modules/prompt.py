from .tags import Tag, TagList


class Prompt:
    """
    Prompt that supports anchor-based mutations.
    """

    def __init__(self, parent: "Prompt | None", prompt: str):
        self._bind: dict[str, Tag] = {}
        self._parent = parent
        self._tags = TagList(prompt)

    def __contains__(self, key: object):
        return (self._parent and key in self._parent) or key in self._tags

    def __str__(self):
        return str(self._tags)

    def _get_or_create(self, anchor: Tag):
        try:
            return next(tag for tag in self._tags if tag == anchor)
        except StopIteration:
            if not self._parent:
                raise StopIteration()
            else:
                source = next(tag for tag in self._parent._tags if tag == anchor)
                anchor = Tag(False, source.name, source.pieces)
                self._tags.append(anchor)
                return anchor

    def add(self, anchor: Tag | None, enabled: bool, tags: TagList):
        # Resolve the semantic anchor.
        anchor = self._get_or_create(anchor) if anchor else None
        anchor_name = anchor.name if anchor else None
        anchor_weight = anchor.weight if anchor else 1

        # Resolve the positional anchor.
        while anchor and anchor.name in self._bind:
            anchor = self._bind[anchor.name]

        for tag in tags:
            # Create the tag on the semantic anchor weight.
            new_pieces = [(piece[0], anchor_weight * piece[1]) for piece in tag.pieces]
            new_tag = Tag(enabled, tag.name, new_pieces)

            try:
                # If the tag exists, enable it, and use the strongest weight.
                existing_tag = self._tags[self._tags.index(new_tag)]
                existing_tag.enabled = enabled
                if new_tag.weight >= existing_tag.weight:
                    existing_tag.pieces = new_tag.pieces
                    existing_tag.weight = new_tag.weight
            except ValueError:
                # Add the tag after the positional anchor.
                if anchor and anchor_name:
                    self._tags.insert(self._tags.index(anchor) + 1, new_tag)
                    self._bind[anchor_name] = new_tag
                    anchor = new_tag
                else:
                    self._tags.append(new_tag)

    def remove(self, tags: TagList):
        for tag in tags:
            try:
                existing_tag = self._tags[self._tags.index(tag)]
                existing_tag.enabled = False
            except ValueError:
                continue


class RegionPrompt(list[Prompt]):
    """
    Region prompt that overlays per-region tags on a shared base region.
    """

    def __init__(self, prompt: str):
        super().__init__(self._parse(prompt))

    def __str__(self):
        regions = [str(prompt) for prompt in self]

        # Clean trailing whitespaces.
        while regions and not regions[-1]:
            regions.pop()

        # Suffix each region divider.
        for index in range(1, len(regions)):
            regions[index - 1] = f"{regions[index - 1]} BREAK ".lstrip()

        return "".join(regions)

    def _parse(self, prompt: str):
        # Divide the prompt.
        regions = [tile for tile in prompt.split("BREAK")]
        base_region = Prompt(None, regions[0])

        # Return the base region.
        yield base_region

        # Return the other regions.
        for index in range(1, len(regions)):
            yield Prompt(base_region, regions[index])

    def get_or_create(self, index: int):
        while index > len(self) - 1:
            self.append(Prompt(self[0], ""))
        return self[index]
