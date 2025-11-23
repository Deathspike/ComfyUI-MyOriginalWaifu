from typing import TypeGuard


class Typing:
    @staticmethod
    def is_dict(value: object) -> TypeGuard[dict[object, object]]:
        return isinstance(value, dict)

    @staticmethod
    def is_list(value: object) -> TypeGuard[list[object] | tuple[object]]:
        return isinstance(value, (list, tuple))
