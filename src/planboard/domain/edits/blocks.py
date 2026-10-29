from __future__ import annotations

from ..draft import Draft
from ..json import JsonObject, JsonValue
from .document import Changes, apply_changes, objects_in, section_of
from .errors import EditError, UnknownIdError


def add_block(
    draft: Draft, section_id: str, block: JsonObject, at: int | None = None
) -> None:
    """Insert a block so it becomes number at (1-based), or append it."""
    blocks = _blocks(draft, section_id)
    index = len(blocks) if at is None else _insert_index(blocks, at)
    blocks.insert(index, block)
    _store(draft, section_id, blocks)


def set_block(draft: Draft, section_id: str, number: int, changes: Changes) -> None:
    """Change a block's fields; None removes one. The type stays."""
    blocks = _blocks(draft, section_id)
    apply_changes(blocks[_index(blocks, number, section_id)], changes)
    _store(draft, section_id, blocks)


def replace_block(
    draft: Draft, section_id: str, number: int, block: JsonObject
) -> None:
    blocks = _blocks(draft, section_id)
    blocks[_index(blocks, number, section_id)] = block
    _store(draft, section_id, blocks)


def move_block(draft: Draft, section_id: str, number: int, to: int) -> None:
    blocks = _blocks(draft, section_id)
    block = blocks.pop(_index(blocks, number, section_id))
    blocks.insert(_insert_index(blocks, to), block)
    _store(draft, section_id, blocks)


def remove_block(draft: Draft, section_id: str, number: int) -> None:
    blocks = _blocks(draft, section_id)
    del blocks[_index(blocks, number, section_id)]
    _store(draft, section_id, blocks)


def _blocks(draft: Draft, section_id: str) -> list[JsonObject]:
    return objects_in(section_of(draft, section_id).get("blocks"))


def _store(draft: Draft, section_id: str, blocks: list[JsonObject]) -> None:
    section_of(draft, section_id)["blocks"] = list[JsonValue](blocks)


def _index(blocks: list[JsonObject], number: int, section_id: str) -> int:
    if not 1 <= number <= len(blocks):
        raise UnknownIdError(
            f"Section '{section_id}' has {len(blocks)} block"
            f"{'' if len(blocks) == 1 else 's'}; there is no block {number}."
        )
    return number - 1


def _insert_index(blocks: list[JsonObject], at: int) -> int:
    if at < 1:
        raise EditError(f"Block numbers start at 1, not {at}.")
    return min(at, len(blocks) + 1) - 1
