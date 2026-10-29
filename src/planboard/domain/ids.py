from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Annotated

from pydantic import Field, StringConstraints

SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
PLAN_ID = rf"{SLUG}(?:/{SLUG})*"

Slug = Annotated[str, StringConstraints(pattern=rf"^{SLUG}$")]
RefText = Annotated[
    str, StringConstraints(pattern=rf"^(?:{PLAN_ID}(?:#{SLUG})?|#{SLUG})$")
]
AnchorRef = Annotated[str, StringConstraints(pattern=rf"^(?:{PLAN_ID})?#{SLUG}$")]

Inline = Annotated[
    str,
    Field(
        min_length=1,
        description="Inline text. Supports `code`, **bold** and [label](href); "
        "an href of #id links to a section or diagram in the plan.",
    ),
]

_REF = re.compile(rf"^(?P<plan>{PLAN_ID})?(?:#(?P<anchor>{SLUG}))?$")


def is_plan_id(text: str) -> bool:
    return re.fullmatch(PLAN_ID, text) is not None


@dataclass(frozen=True, slots=True)
class Ref:
    plan_id: str
    anchor: str | None

    @classmethod
    def parse(cls, text: str, current_plan_id: str) -> Ref:
        match = _REF.match(text)
        if match is None or not (match["plan"] or match["anchor"]):
            raise ValueError(f"'{text}' is not a reference")
        return cls(match["plan"] or current_plan_id, match["anchor"])

    def __str__(self) -> str:
        return self.plan_id if self.anchor is None else f"{self.plan_id}#{self.anchor}"
