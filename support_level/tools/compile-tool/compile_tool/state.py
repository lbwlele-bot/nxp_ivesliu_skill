from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from . import __version__
from .common import ToolError, atomic_write_yaml, hash_data, load_yaml, mapping_value


STATE_SCHEMA_VERSION = 2


def state_path(manifest: dict[str, Any]) -> Path:
    return Path(manifest["case_root"]) / "state" / "software-state.yaml"


def empty_state(manifest: dict[str, Any]) -> dict[str, Any]:
    root = {
        "schema_version": STATE_SCHEMA_VERSION,
        "generated_by": f"compile-tool {__version__}",
        "case": manifest["case"],
        "targets": {},
    }
    return {
        "profile_hash": manifest["profile"]["hash"],
        "manifest_hash": manifest["hash"],
        "components": {},
        "_root_state": root,
    }


def _integrity_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if key != "integrity_hash"}


def load_state(manifest: dict[str, Any]) -> dict[str, Any]:
    path = state_path(manifest)
    if not path.exists():
        return empty_state(manifest)
    raw = mapping_value(load_yaml(path, "software state"), "software state")
    version = raw.get("schema_version")
    if version not in {1, STATE_SCHEMA_VERSION}:
        raise ToolError(f"unsupported software state schema at {path}")
    supplied = raw.get("integrity_hash")
    if not isinstance(supplied, str) or supplied != hash_data(_integrity_payload(raw)):
        raise ToolError(f"software state integrity check failed: {path}")
    if raw.get("case") != manifest["case"]:
        raise ToolError(f"software state belongs to a different case: {path}")
    if version == 1:
        if not isinstance(raw.get("target"), str) or not isinstance(
            raw.get("components"), dict
        ):
            raise ToolError(f"legacy software state is invalid: {path}")
        root = {
            "schema_version": STATE_SCHEMA_VERSION,
            "generated_by": f"compile-tool {__version__}",
            "case": raw["case"],
            "targets": {
                raw["target"]: {
                    "profile_hash": raw.get("profile_hash"),
                    "manifest_hash": raw.get("manifest_hash"),
                    "components": deepcopy(raw["components"]),
                }
            },
        }
    else:
        if not isinstance(raw.get("targets"), dict):
            raise ToolError(f"software state targets are invalid: {path}")
        root = deepcopy(raw)
        root.pop("integrity_hash", None)
        root.pop("identity", None)
    target_state = root["targets"].get(manifest["target"])
    if target_state is None:
        target_state = {
            "profile_hash": manifest["profile"]["hash"],
            "manifest_hash": manifest["hash"],
            "components": {},
        }
    if not isinstance(target_state, dict) or not isinstance(
        target_state.get("components"), dict
    ):
        raise ToolError(
            f"software state target {manifest['target']!r} is invalid: {path}"
        )
    result = deepcopy(target_state)
    result["_root_state"] = root
    return result


def write_state(manifest: dict[str, Any], state: dict[str, Any]) -> None:
    root = deepcopy(state.get("_root_state") or empty_state(manifest)["_root_state"])
    target_state = {
        key: deepcopy(value)
        for key, value in state.items()
        if not key.startswith("_")
    }
    target_state["profile_hash"] = manifest["profile"]["hash"]
    target_state["manifest_hash"] = manifest["hash"]
    root["schema_version"] = STATE_SCHEMA_VERSION
    root["generated_by"] = f"compile-tool {__version__}"
    root["case"] = manifest["case"]
    root.pop("identity", None)
    root.setdefault("targets", {})[manifest["target"]] = target_state
    root["integrity_hash"] = hash_data(_integrity_payload(root))
    atomic_write_yaml(state_path(manifest), root)
