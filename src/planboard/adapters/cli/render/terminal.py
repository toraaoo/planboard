from __future__ import annotations

import re
from collections.abc import Sequence

from rich import box
from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from ....application.catalog import Catalog
from ....application.ports import LoadedPlan
from ....domain import references
from ....domain.blocks import (
    Block,
    CalloutBlock,
    CodeBlock,
    DiagramBlock,
    HeadingBlock,
    ListBlock,
    ListItem,
    TableBlock,
    TextBlock,
)
from ....domain.layout import section_file
from ....domain.plan import TASK_STATUSES, Plan, Section, Task, TaskStatus
from ....domain.search import Hit

STATUS_STYLES = {
    "todo": "white",
    "doing": "cyan",
    "blocked": "red",
    "done": "green",
    "draft": "yellow",
    "approved": "green",
    "archived": "bright_black",
}

_MARKUP = re.compile(
    r"`(?P<code>[^`]+)`|\*\*(?P<bold>.+?)\*\*|\[(?P<label>[^\]]+)\]\((?P<href>[^)\s]+)\)"
)


def inline(text: str) -> Text:
    rendered = Text()
    position = 0
    for match in _MARKUP.finditer(text):
        rendered.append(text[position : match.start()])
        if match["code"] is not None:
            rendered.append(match["code"], style="bold magenta")
        elif match["bold"] is not None:
            rendered.append(match["bold"], style="bold")
        elif match["href"].startswith(("http:", "https:", "mailto:")):
            rendered.append(match["label"], style=f"underline link {match['href']}")
        else:
            rendered.append(match["label"], style="underline")
            rendered.append(f" [{match['href']}]", style="dim")
        position = match.end()
    rendered.append(text[position:])
    return rendered


def status(name: str) -> Text:
    return Text(name, style=STATUS_STYLES.get(name, ""))


def plan_document(
    snapshot: Catalog, entry: LoadedPlan, anchor: str | None
) -> RenderableType:
    plan = entry.plan
    if anchor is not None and anchor in plan.diagrams:
        block = DiagramBlock(type="diagram", ref=f"#{anchor}")
        return _diagram(snapshot, entry.id, block)
    sections = [s for s in plan.sections if anchor is None or s.id == anchor]
    parts: list[RenderableType] = []
    if anchor is None:
        parts.append(_title_block(snapshot, entry))
    parts += [_section(snapshot, entry, section) for section in sections]
    return Group(*parts)


def board(
    snapshot: Catalog,
    plan_ids: Sequence[str],
    statuses: Sequence[TaskStatus] = TASK_STATUSES,
) -> RenderableType:
    table = Table(box=box.SIMPLE_HEAVY, expand=True, show_lines=False)
    columns: dict[str, list[RenderableType]] = {name: [] for name in statuses}
    for name in statuses:
        table.add_column(status(name), ratio=1, overflow="fold")
    plans = snapshot.plans
    for plan_id in plan_ids:
        for task in plans[plan_id].tasks:
            if task.status in columns:
                columns[task.status].append(
                    _card(plan_id, task, plans, show_plan=len(plan_ids) > 1)
                )
    table.add_row(*(Group(*cards) for cards in columns.values()))
    return table


type Pair = tuple[str, Task]


def ready(
    snapshot: Catalog,
    started: Sequence[Pair],
    ready_now: Sequence[Pair],
    waiting: Sequence[Pair],
    readies: dict[str, list[str]],
) -> RenderableType:
    plans = snapshot.plans
    parts: list[RenderableType] = []
    if started:
        table = _task_table("In progress")
        for plan_id, task in started:
            notes = Text()
            early = references.waiting_on(plan_id, task, plans)
            if early:
                refs = ", ".join(item.ref for item in early)
                notes.append(f"started before {refs} are done", "yellow")
            freed = readies.get(f"{plan_id}#{task.id}")
            if freed:
                notes.append("\n" if notes else "")
                notes.append(f"finishing it readies {_local(freed, plan_id)}", "green")
            if task.note:
                notes.append("\n" if notes else "")
                notes.append_text(inline(task.note))
            table.add_row(
                f"{plan_id}#{task.id}", status(task.status), task.title, notes
            )
        parts.append(table)
    if ready_now:
        table = _task_table("Ready")
        for plan_id, task in ready_now:
            summary = inline(task.summary) if task.summary else Text("")
            table.add_row(
                f"{plan_id}#{task.id}", status(task.status), task.title, summary
            )
        parts.append(table)
        return _spaced(parts)
    if not waiting:
        parts.append(Text("Nothing is ready: there are no todo tasks."))
        return _spaced(parts)
    count = len(waiting)
    parts.append(
        Text(
            f"Nothing is ready: {count} todo task{'' if count == 1 else 's'} "
            "wait on unfinished work."
        )
    )
    table = _task_table("Waiting")
    for plan_id, task in waiting:
        refs = ", ".join(
            item.ref for item in references.waiting_on(plan_id, task, plans)
        )
        table.add_row(
            f"{plan_id}#{task.id}",
            status(task.status),
            task.title,
            Text(f"waits on {refs}", "yellow"),
        )
    parts.append(table)
    return _spaced(parts)


def task(snapshot: Catalog, plan_id: str, task: Task) -> RenderableType:
    plans = snapshot.plans
    plan = plans[plan_id]
    resolved = references.resolve_all(plan_id, plans)
    number = plan.tasks.index(task) + 1
    facts = Text.assemble(
        status(task.status),
        f" · task {number} of {len(plan.tasks)} in ",
        (plan.title, "bold"),
    )
    rows = Table.grid(padding=(0, 2))
    rows.add_column(style="dim")
    rows.add_column()
    if task.summary:
        rows.add_row("summary", inline(task.summary))
    if task.note:
        rows.add_row("note", inline(task.note))
    if task.depends_on:
        deps = ", ".join(f"{t} ({resolved[t].state})" for t in task.depends_on)
        rows.add_row("depends on", deps)
    if plan.depends_on:
        deps = ", ".join(f"{t} ({resolved[t].state})" for t in plan.depends_on)
        rows.add_row("plan needs", deps)
    needed = references.needed_by(plan_id, task.id, plans)
    if needed:
        rows.add_row("needed by", _local(needed, plan_id))
    freed = references.readies(plans).get(f"{plan_id}#{task.id}")
    if freed and task.status != "done":
        rows.add_row("readies", Text(_local(freed, plan_id), "green"))
    if task.sections:
        rows.add_row("sections", ", ".join(task.sections))
    if task.diagrams:
        rows.add_row("diagrams", ", ".join(task.diagrams))
    parts: list[RenderableType] = [facts]
    if rows.row_count:
        parts += [Text(), rows]
    return Panel(
        Group(*parts),
        title=Text(task.title, style="bold"),
        subtitle=Text(f"{plan_id}#{task.id}", style="dim"),
        border_style=STATUS_STYLES[task.status],
    )


def preview(block: Block) -> str:
    """One line of what a block holds."""
    match block:
        case HeadingBlock() | TextBlock():
            return block.text
        case ListBlock():
            texts = [
                item if isinstance(item, str) else item.text for item in block.items
            ]
            return f"{len(texts)} items: {'; '.join(texts)}"
        case TableBlock():
            return f"{len(block.rows)} rows: {' | '.join(block.columns)}"
        case CalloutBlock():
            return f"{block.tone} · {block.title}: {block.text}"
        case CodeBlock():
            first = block.code.splitlines()[0] if block.code.strip() else ""
            return f"{block.language or 'text'} · {first}"
        case DiagramBlock():
            return block.ref + (f" · {block.caption}" if block.caption else "")


def hits(found: Sequence[Hit]) -> RenderableType:
    if not found:
        return Text("No matches.")
    table = Table(box=None, show_header=False, padding=(0, 1), pad_edge=True)
    table.add_column("ref", no_wrap=True)
    table.add_column("where", style="dim", no_wrap=True)
    table.add_column("snippet", ratio=1, overflow="ellipsis", no_wrap=True)
    for hit in found:
        table.add_row(hit.ref, f"{hit.kind} {hit.field}", hit.snippet)
    return table


def _task_table(title: str) -> Table:
    table = Table(
        box=None,
        title=title,
        title_justify="left",
        title_style="bold",
        show_header=False,
        padding=(0, 1),
        pad_edge=True,
    )
    table.add_column("task", no_wrap=True)
    table.add_column("status", no_wrap=True)
    table.add_column("title")
    table.add_column("notes", ratio=1, overflow="fold")
    return table


def _spaced(parts: list[RenderableType]) -> RenderableType:
    spaced: list[RenderableType] = []
    for part in parts:
        spaced += [Text(), part] if spaced else [part]
    return Group(*spaced)


def _local(refs: Sequence[str], plan_id: str) -> str:
    """References, as #id when they are in plan_id."""
    return ", ".join(
        ref.removeprefix(plan_id) if ref.startswith(f"{plan_id}#") else ref
        for ref in refs
    )


def _card(
    plan_id: str, task: Task, plans: dict[str, Plan], *, show_plan: bool
) -> RenderableType:
    body = Text()
    body.append(task.title, style="bold")
    body.append(f"\n{plan_id}#{task.id}" if show_plan else f"\n#{task.id}", "dim")
    waiting = references.waiting_on(plan_id, task, plans)
    if waiting and task.status != "done":
        body.append(f"\nwaits on {', '.join(item.ref for item in waiting)}", "yellow")
    if task.note:
        body.append("\n")
        body.append(inline(task.note))
    return Panel(body, border_style=STATUS_STYLES[task.status], padding=(0, 1))


def _title_block(snapshot: Catalog, entry: LoadedPlan) -> RenderableType:
    plan = entry.plan
    facts = Text.assemble(
        status(plan.status),
        f" · updated {plan.updated.isoformat()}" if plan.updated else "",
        f" · branch {plan.branch}" if plan.branch else "",
        f" · tags {', '.join(plan.tags)}" if plan.tags else "",
        style="",
    )
    progress = references.progress(plan)
    done = Text(f"{progress['done']}/{len(plan.tasks)} tasks done", "dim")
    parts: list[RenderableType] = [facts, Text(), inline(plan.summary), Text(), done]
    if plan.depends_on:
        resolved = references.resolve_all(entry.id, snapshot.plans)
        deps = ", ".join(f"{t} ({resolved[t].state})" for t in plan.depends_on)
        parts.append(Text(f"depends on {deps}", "dim"))
    return Panel(
        Group(*parts),
        title=Text(plan.title, style="bold"),
        subtitle=Text(f"{entry.id}", style="dim"),
        border_style="blue",
    )


def _section(snapshot: Catalog, entry: LoadedPlan, section: Section) -> RenderableType:
    heading = Text.assemble(
        ("\n" + section.title, "bold underline"),
        (f"  #{section.id} · {section_file(section.id)}", "dim"),
    )
    builders = [task for task in entry.plan.tasks if section.id in task.sections]
    parts: list[RenderableType] = [heading]
    if builders:
        built = Text("built by ", "dim")
        for index, task in enumerate(builders):
            built.append(", " if index else "")
            built.append(f"#{task.id} ")
            built.append_text(status(task.status))
        parts.append(built)
    parts += [_block(snapshot, entry.id, block) for block in section.blocks]
    return Group(*parts)


def _block(snapshot: Catalog, plan_id: str, block: Block) -> RenderableType:
    match block:
        case HeadingBlock():
            return Padding(Text(block.text, style="bold"), (1, 0, 0, 0))
        case TextBlock():
            return Padding(inline(block.text), (1, 0, 0, 0))
        case ListBlock():
            return Padding(_list(block.items, block.ordered), (1, 0, 0, 0))
        case TableBlock():
            return _table(block)
        case CalloutBlock():
            return Panel(
                inline(block.text),
                title=block.title,
                title_align="left",
                border_style="yellow" if block.tone == "warning" else "blue",
            )
        case CodeBlock():
            return Panel(
                Syntax(block.code, block.language or "text", word_wrap=True),
                subtitle=inline(block.caption) if block.caption else None,
                border_style="bright_black",
            )
        case DiagramBlock():
            return _diagram(snapshot, plan_id, block)


def _list(items: Sequence[str | ListItem], ordered: bool, depth: int = 0) -> Text:
    rendered = Text()
    for number, item in enumerate(items, start=1):
        marker = f"{number}." if ordered else "•"
        text = item if isinstance(item, str) else item.text
        if rendered:
            rendered.append("\n")
        rendered.append(f"{'  ' * depth}{marker} ")
        rendered.append_text(inline(text))
        if isinstance(item, ListItem) and item.items:
            rendered.append("\n")
            rendered.append_text(_list(item.items, ordered=False, depth=depth + 1))
    return rendered


def _table(block: TableBlock) -> RenderableType:
    table = Table(
        box=box.ROUNDED,
        show_lines=True,
        caption=inline(block.caption) if block.caption else None,
    )
    for index, column in enumerate(block.columns):
        table.add_column(column, style="bold" if index == 0 else None)
    for row in block.rows:
        table.add_row(*(inline(cell) if cell else Text("") for cell in row))
    return table


def _diagram(snapshot: Catalog, plan_id: str, block: DiagramBlock) -> RenderableType:
    resolved = snapshot.diagrams.resolve(block.ref, plan_id)
    origin = resolved.file or "inline"
    body: list[RenderableType] = []
    if resolved.alt:
        body.append(Text(resolved.alt, style="italic"))
    if resolved.source:
        body.append(Syntax(resolved.source.rstrip(), "text", word_wrap=True))
    if resolved.error:
        body.append(Text(resolved.error, style="red"))
    return Panel(
        Group(*body),
        title=Text(f"diagram {block.ref} · {origin}", style="dim"),
        title_align="left",
        subtitle=inline(block.caption) if block.caption else None,
        border_style="magenta",
    )
