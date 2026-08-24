from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import ToolError, load_yaml
from .checklists import (
    CHECKLIST_KIND as PROJECT_CHECKLIST_KIND,
    materialize_checklist_manifest,
    normalize_checklist,
    prepare_checklist,
    run_checklist,
)
from .m_sdk import (
    CHECKLIST_KIND as M_SDK_CHECKLIST_KIND,
    materialize_m_sdk_manifest,
    normalize_m_sdk_checklist,
    prepare_m_sdk_checklist,
    run_m_sdk_checklist,
)


def checklist_kind(path: Path) -> str | None:
    value = load_yaml(path, "compile input")
    return value.get("kind") if isinstance(value, dict) else None


def is_public_checklist(path: Path) -> bool:
    return checklist_kind(path) in {PROJECT_CHECKLIST_KIND, M_SDK_CHECKLIST_KIND}


def normalize_public_checklist(path: Path) -> dict[str, Any]:
    kind = checklist_kind(path)
    if kind == PROJECT_CHECKLIST_KIND:
        value = normalize_checklist(path)
        value["checklist_kind"] = kind
        return value
    if kind == M_SDK_CHECKLIST_KIND:
        return normalize_m_sdk_checklist(path)
    raise ToolError(f"unsupported public compile checklist kind: {kind!r}")


def materialize_public_manifest(
    checklist: dict[str, Any], *, stack: set[str] | None = None
) -> dict[str, Any]:
    kind = checklist.get("checklist_kind")
    if kind == PROJECT_CHECKLIST_KIND:
        return materialize_checklist_manifest(checklist, stack=stack)
    if kind == M_SDK_CHECKLIST_KIND:
        return materialize_m_sdk_manifest(checklist, stack=stack)
    raise ToolError(f"unsupported normalized compile checklist kind: {kind!r}")


def prepare_public_checklist(path: Path) -> int:
    kind = checklist_kind(path)
    if kind == PROJECT_CHECKLIST_KIND:
        return prepare_checklist(path)
    if kind == M_SDK_CHECKLIST_KIND:
        return prepare_m_sdk_checklist(path)
    raise ToolError(f"unsupported public compile checklist kind: {kind!r}")


def run_public_checklist(path: Path) -> int:
    kind = checklist_kind(path)
    if kind == PROJECT_CHECKLIST_KIND:
        return run_checklist(path)
    if kind == M_SDK_CHECKLIST_KIND:
        return run_m_sdk_checklist(path)
    raise ToolError(f"unsupported public compile checklist kind: {kind!r}")
