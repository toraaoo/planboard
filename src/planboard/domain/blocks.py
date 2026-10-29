from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .base import Model
from .ids import AnchorRef, Inline


class HeadingBlock(Model):
    type: Literal["heading"]
    text: str = Field(min_length=1)


class TextBlock(Model):
    type: Literal["text"]
    text: Inline


class ListItem(Model):
    text: Inline
    items: list[Inline | ListItem] = Field(
        default_factory=lambda: list[Inline | ListItem]()
    )


class ListBlock(Model):
    type: Literal["list"]
    ordered: bool = False
    items: list[Inline | ListItem] = Field(min_length=1)


class TableBlock(Model):
    type: Literal["table"]
    columns: list[str] = Field(min_length=1)
    rows: list[list[Inline | None]] = Field(
        min_length=1, description="One list per row, a cell per column; null is empty."
    )
    caption: Inline | None = None


class CalloutBlock(Model):
    type: Literal["callout"]
    tone: Literal["note", "warning"] = "note"
    title: str = Field(min_length=1)
    text: Inline


class CodeBlock(Model):
    type: Literal["code"]
    language: str | None = None
    code: str = Field(min_length=1)
    caption: Inline | None = None


class DiagramBlock(Model):
    type: Literal["diagram"]
    ref: AnchorRef = Field(
        description="A diagram from a plan's diagrams map: #id or folder/plan#id."
    )
    caption: Inline | None = None


Block = Annotated[
    HeadingBlock
    | TextBlock
    | ListBlock
    | TableBlock
    | CalloutBlock
    | CodeBlock
    | DiagramBlock,
    Field(discriminator="type"),
]
