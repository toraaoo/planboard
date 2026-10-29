from __future__ import annotations

import copy
import datetime
import hashlib
import os
import shutil
import threading
from pathlib import Path

from ...application.ports import (
    BrokenPlan,
    Change,
    Check,
    EditResult,
    LoadedPlan,
    PlanEntry,
    PlanExistsError,
    PlanNotFoundError,
    UnreadableDiagramError,
)
from ...domain.draft import Draft, InvalidPlanError, assemble, plan_file
from ...domain.ids import is_plan_id
from ...domain.json import JsonObject
from ...domain.layout import (
    PLAN_FILE,
    PLAN_SCHEMA,
    SECTION_SCHEMA,
    SECTIONS_DIR,
    section_file,
)
from .files import (
    UnreadableFileError,
    inside,
    read_object,
    write_json,
    write_text,
)
from .schemas import write_missing


class FilePlanRepository:
    """Plans as folders of JSON and Mermaid files under one root folder.

    When schema_dir is set, every file it writes links its JSON Schema with a
    relative $schema path, and the schema files are written if they are missing.
    """

    def __init__(self, root: Path, schema_dir: Path | None = None) -> None:
        self._root = root.resolve()
        self.schema_dir = schema_dir.resolve() if schema_dir else None
        self._writes = threading.Lock()

    @property
    def root(self) -> Path:
        return self._root

    def ids(self) -> list[str]:
        folders = sorted(
            path.parent
            for path in self.root.rglob(PLAN_FILE)
            if path.parent != self.root
        )
        plans: list[Path] = []
        for folder in folders:
            if not any(folder.is_relative_to(plan) for plan in plans):
                plans.append(folder)
        return [folder.relative_to(self.root).as_posix() for folder in plans]

    def folder_for(self, plan_id: str) -> Path:
        if not is_plan_id(plan_id):
            raise PlanNotFoundError(plan_id)
        return self.root / plan_id

    def load(self, plan_id: str) -> PlanEntry:
        folder = self.root / plan_id
        if not is_plan_id(plan_id):
            return BrokenPlan(plan_id, folder, ("names must be lowercase-kebab-case",))
        if not (folder / PLAN_FILE).is_file():
            raise PlanNotFoundError(plan_id)
        try:
            document = _read(folder, PLAN_FILE, plan_id)
            plan = assemble(
                plan_id,
                document,
                lambda section_id: _read(folder, section_file(section_id), plan_id),
            )
            return LoadedPlan(plan_id, folder, plan)
        except InvalidPlanError as error:
            return BrokenPlan(plan_id, folder, error.errors)

    def load_all(self) -> list[PlanEntry]:
        return [self.load(plan_id) for plan_id in self.ids()]

    def unlisted_sections(self, entry: LoadedPlan) -> list[str]:
        listed = {section.id for section in entry.plan.sections}
        return sorted(
            section_file(path.stem)
            for path in (entry.path / SECTIONS_DIR).glob("*.json")
            if path.stem not in listed
        )

    def read_diagram(self, entry: LoadedPlan, file: str) -> str:
        path = (entry.path / file).resolve()
        if not path.is_relative_to(entry.path.resolve()):
            raise UnreadableDiagramError(f"'{file}' is outside the plan folder")
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            raise UnreadableDiagramError(f"'{file}' cannot be read") from None

    def version(self) -> str:
        digest = hashlib.sha256()
        files = sorted([*self.root.rglob("*.json"), *self.root.rglob("*.mmd")])
        for path in files:
            stat = path.stat()
            name = path.relative_to(self.root).as_posix()
            digest.update(f"{name}:{stat.st_mtime_ns}:{stat.st_size};".encode())
        return digest.hexdigest()[:16]

    def create(
        self, plan_id: str, document: JsonObject, *, dry_run: bool = False
    ) -> Path:
        folder = self.folder_for(plan_id)
        if (folder / PLAN_FILE).exists():
            raise PlanExistsError(plan_id)
        draft = Draft.from_document(document)
        draft.validate(plan_id)
        if not dry_run:
            self._commit(folder, Draft({}, {}), draft)
        return folder

    def edit(
        self,
        plan_id: str,
        change: Change,
        *,
        dry_run: bool = False,
        check: Check | None = None,
    ) -> EditResult:
        folder = self.folder_for(plan_id)
        with self._writes:
            original = self._open(folder, plan_id)
            draft = copy.deepcopy(original)
            change(draft)
            draft.plan["updated"] = datetime.date.today().isoformat()
            plan = draft.validate(plan_id)
            if check is not None:
                check(plan)
            written, removed = _diff(original, draft)
            if not dry_run:
                self._commit(folder, original, draft)
            return EditResult(plan, written, removed)

    def move(
        self,
        plan_id: str,
        new_id: str,
        change: Change,
        *,
        dry_run: bool = False,
        check: Check | None = None,
    ) -> EditResult:
        folder = self.folder_for(plan_id)
        target = self.folder_for(new_id)
        with self._writes:
            original = self._open(folder, plan_id)
            if target.exists():
                raise PlanExistsError(new_id)
            draft = copy.deepcopy(original)
            change(draft)
            draft.plan["updated"] = datetime.date.today().isoformat()
            plan = draft.validate(new_id)
            if check is not None:
                check(plan)
            files = _files(folder)
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                folder.rename(target)
                _prune(folder.parent, self.root)
                if self.schema_dir is not None:  # $schema paths are relative
                    for document in [draft.plan, *draft.sections.values()]:
                        document.pop("$schema", None)
                self._commit(target, Draft({}, {}), draft)
            return EditResult(plan, files, files)

    def remove(self, plan_id: str, *, dry_run: bool = False) -> tuple[str, ...]:
        folder = self.folder_for(plan_id)
        with self._writes:
            if not (folder / PLAN_FILE).is_file():
                raise PlanNotFoundError(plan_id)
            files = _files(folder)
            if not dry_run:
                shutil.rmtree(folder)
                _prune(folder.parent, self.root)
            return files

    def _open(self, folder: Path, plan_id: str) -> Draft:
        """A plan's documents as stored, after checking they are valid."""
        if not (folder / PLAN_FILE).is_file():
            raise PlanNotFoundError(plan_id)
        document = _read(folder, PLAN_FILE, plan_id)
        file = plan_file(plan_id, document)
        sections = {
            section_id: _read(folder, section_file(section_id), plan_id)
            for section_id in file.sections
        }
        draft = Draft(document, sections)
        draft.validate(plan_id)
        for diagram in file.diagrams.values():
            if diagram.file is not None:
                try:
                    source = inside(folder, diagram.file).read_text(encoding="utf-8")
                except (OSError, ValueError):
                    continue
                draft.diagram_sources[diagram.file] = source
        return draft

    def _commit(self, folder: Path, original: Draft, draft: Draft) -> None:
        if self.schema_dir is not None:
            write_missing(self.schema_dir)
        for section_id, section in draft.sections.items():
            if original.sections.get(section_id) != section:
                path = folder / section_file(section_id)
                write_json(path, self._with_schema(section, SECTION_SCHEMA, path))
        for name, source in draft.diagram_files.items():
            if source is not None:
                write_text(inside(folder, name), source)
        path = folder / PLAN_FILE
        write_json(path, self._with_schema(draft.plan, PLAN_SCHEMA, path))
        for section_id in original.sections.keys() - draft.sections.keys():
            (folder / section_file(section_id)).unlink(missing_ok=True)
        for name, source in draft.diagram_files.items():
            if source is None:
                inside(folder, name).unlink(missing_ok=True)

    def _with_schema(self, document: JsonObject, schema: str, path: Path) -> JsonObject:
        if self.schema_dir is None or "$schema" in document:
            return document
        relative = os.path.relpath(self.schema_dir / schema, path.parent)
        return {"$schema": relative, **document}


def _diff(original: Draft, draft: Draft) -> tuple[tuple[str, ...], tuple[str, ...]]:
    written = [
        section_file(section_id)
        for section_id, section in draft.sections.items()
        if original.sections.get(section_id) != section
    ]
    written += [name for name, source in draft.diagram_files.items() if source]
    removed = [
        section_file(section_id)
        for section_id in sorted(original.sections.keys() - draft.sections.keys())
    ]
    removed += [name for name, source in draft.diagram_files.items() if not source]
    return (PLAN_FILE, *written), tuple(removed)


def _files(folder: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            path.relative_to(folder).as_posix()
            for path in folder.rglob("*")
            if path.is_file()
        )
    )


def _prune(folder: Path, root: Path) -> None:
    """Remove empty folders from folder up to, not including, root."""
    while folder != root and folder.is_relative_to(root) and not any(folder.iterdir()):
        folder.rmdir()
        folder = folder.parent


def _read(folder: Path, name: str, plan_id: str) -> JsonObject:
    try:
        return read_object(folder / name)
    except UnreadableFileError as error:
        raise InvalidPlanError(plan_id, (f"{name}: {error}",)) from None
