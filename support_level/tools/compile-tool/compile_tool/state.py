from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .common import ToolError, atomic_write_yaml, hash_data, load_yaml, mapping_value


STATE_SCHEMA_VERSION = 1


def state_path(manifest: dict[str, Any]) -> Path:
    return Path(manifest["case_root"]) / "state" / "software-state.yaml"


def empty_state(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "generated_by": "compile-tool 2.0",
        "case": manifest["case"],
        "target": manifest["target"],
        "identity": manifest["identity"],
        "profile_hash": manifest["profile"]["hash"],
        "manifest_hash": manifest["hash"],
        "components": {},
    }


def _integrity_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if key != "integrity_hash"}


def load_state(manifest: dict[str, Any]) -> dict[str, Any]:
    path = state_path(manifest)
    if not path.exists():
        return empty_state(manifest)
    raw = mapping_value(load_yaml(path, "software state"), "software state")
    if raw.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ToolError(f"unsupported software state schema at {path}")
    supplied = raw.get("integrity_hash")
    if not isinstance(supplied, str) or supplied != hash_data(_integrity_payload(raw)):
        raise ToolError(f"software state integrity check failed: {path}")
    if raw.get("case") != manifest["case"] or raw.get("target") != manifest["target"]:
        raise ToolError(f"software state belongs to a different case or target: {path}")
    if raw.get("identity") != manifest["identity"]:
        raise ToolError(
            "software state identity differs from the manifest; use a new case "
            "instead of mixing target identities"
        )
    if not isinstance(raw.get("components"), dict):
        raise ToolError(f"software state components are invalid: {path}")
    return raw


def write_state(manifest: dict[str, Any], state: dict[str, Any]) -> None:
    result = deepcopy(state)
    result["schema_version"] = STATE_SCHEMA_VERSION
    result["generated_by"] = "compile-tool 2.0"
    result["case"] = manifest["case"]
    result["target"] = manifest["target"]
    result["identity"] = manifest["identity"]
    result["profile_hash"] = manifest["profile"]["hash"]
    result["manifest_hash"] = manifest["hash"]
    result["integrity_hash"] = hash_data(_integrity_payload(result))
    atomic_write_yaml(state_path(manifest), result)
