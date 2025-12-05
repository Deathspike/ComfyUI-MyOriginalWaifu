from .tags import Tag, TagList


class Prompt:
    """
    Prompt that supports anchor-based mutations.
    """

    def __init__(self, prompt: str):
        self._bind: dict[str, Tag] = {}
        self._tags = TagList(prompt)

    def __contains__(self, key: object):
        return key in self._tags

    def __str__(self):
        return str(self._tags)

    def add(self, anchor: Tag | None, tags: TagList):
        # Resolve the semantic anchor.
        anchor = next((tag for tag in self._tags if tag == anchor), None)
        anchor_key = anchor.name if anchor else None
        anchor_weight = anchor.weight if anchor else 1

        # Resolve the positional anchor.
        while anchor and anchor.name in self._bind:
            anchor = self._bind[anchor.name]

        for tag in tags:
            # Create the tag on the semantic anchor weight.
            new_pieces = [(piece[0], anchor_weight * piece[1]) for piece in tag.pieces]
            new_tag = Tag(tag.name, new_pieces)

            try:
                # If the tag exists, use the strongest weight.
                existing_tag = self._tags[self._tags.index(new_tag)]
                existing_tag.enabled = True
                existing_tag.weight = max(existing_tag.weight, new_tag.weight)
            except ValueError:
                # Add the tag after the positional anchor.
                if anchor and anchor_key:
                    self._tags.insert(self._tags.index(anchor) + 1, new_tag)
                    self._bind[anchor_key] = new_tag
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
