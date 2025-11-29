from .tags import Tag, TagList


class Prompt:
    """
    Mutable prompt with anchor-based tag mutations.
    """

    def __init__(self, prompt: str):
        self._bind: dict[str, Tag] = {}
        self._tags = TagList(prompt)

    def __contains__(self, key: object):
        return key in self._tags

    def __str__(self):
        return str(self._tags)

    def add(self, anchor: Tag | None, tags: TagList):
        # Resolve the semantic anchor and store the original weight.
        anchor_tag = next((tag for tag in self._tags if tag == anchor), None)
        anchor_key = anchor_tag.name if anchor_tag else None
        anchor_weight = anchor_tag.weight if anchor_tag else 1

        # Resolve the positional anchor using the forward pointer.
        while anchor_tag and anchor_tag.name in self._bind:
            anchor_tag = self._bind[anchor_tag.name]

        for tag in tags:
            # Create a tag using the semantic anchor weight.
            new_weight = anchor_weight * tag.weight
            new_tag = Tag(tag.name, new_weight)

            try:
                # If the tag exists, use the strongest weight.
                existing_tag = self._tags[self._tags.index(new_tag)]
                existing_tag.enabled = True
                existing_tag.weight = max(existing_tag.weight, new_tag.weight)
            except ValueError:
                # Add the tag using the positional anchor.
                if anchor_key and anchor_tag:
                    self._tags.insert(self._tags.index(anchor_tag) + 1, new_tag)
                    self._bind[anchor_key] = new_tag
                    anchor_tag = new_tag
                else:
                    self._tags.append(new_tag)

    def remove(self, tags: TagList):
        for tag in tags:
            try:
                existing_tag = self._tags[self._tags.index(tag)]
                existing_tag.enabled = False
            except ValueError:
                continue
