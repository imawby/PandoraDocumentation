#!/usr/bin/env python3

"""
Shared module for managing Doxygen groups based on project submodule structure.
"""

from pathlib import Path
from typing import Dict, Optional

# High-level group descriptions for documentation purposes. These are used in
# the generated ModuleGroups.dox file, which in turn are surfaced in the Doxygen
# topics page.
GROUP_DESCRIPTIONS: Dict[str, str] = {
    "PandoraSDK": "Core Pandora Software Development Kit (SDK) classes and algorithms, including the core framework, data structures, and utilities for particle flow reconstruction.",
    "PandoraMonitoring": "Monitoring tools for Pandora, mostly comprised of ROOT-integrations for visualisation and outputs.",
    "LArContent": "Core LArTPC algorithms and classes for 2D and 3D reconstruction.",
    "LArReco": "Top-level application for LArTPC reconstruction, to load and run over a given input file.",
    "LArRecoND": "Top-level application for 3D Pixel-based reconstruction for the DUNE ND and its prototypes, to load and run over a given input file.",
}

# Which subdirectories to scan for subgroups (depth configurable per module).
SUBGROUP_ROOTS: Dict[str, list[str]] = {
    "PandoraSDK": ["include", "src"],
    "PandoraMonitoring": ["include", "src"],
    "LArContent": ["larpandoracontent", "larpandoradlcontent"],
    "LArReco": ["include", "src"],
    "LArRecoND": ["include", "src"],
}

# Modules where each SUBGROUP_ROOT entry is itself exposed as a named subgroup
# (rather than being a silent scan root). The root dirs become intermediate nodes
# in the group hierarchy between the module and its subdirectories.
SUBGROUP_ROOT_AS_GROUP: set[str] = {"LArContent"}

# Optional path filters for each group, to format the display path relative to a
# specific subfolder within the module. I.e. PandoraSDK/src/Api/File.h would
# display as PandoraSDK/Api/File.h if "src" is in the filter list for PandoraSDK.
PATH_FILTERS: Dict[str, list[str]] = {
    "PandoraSDK": ["src", "include"],
    "PandoraMonitoring": ["src", "include"],
    "LArContent": [],
    "LArReco": ["src", "include", "test"],
    "LArRecoND": ["src", "include", "test"],
}


def repo_root() -> Path:
    """Get the root directory of the repository."""
    return Path(__file__).resolve().parents[1]


def resolve_extern_dir(extern_dir: str | Path | None = None) -> Path:
    """Resolve the extern/ directory relative to the repository root by default."""
    if extern_dir is None:
        return repo_root() / "extern"

    external_path = Path(extern_dir)
    if external_path.is_absolute():
        return external_path

    return (repo_root() / external_path).resolve()


def subgroup_id(module_name: str, parts: list[str]) -> str:
    """Build a stable subgroup identifier from module + relative path parts."""
    safe_parts = [p.replace("-", "_") for p in parts]
    return "_".join([module_name] + safe_parts)


def discover_groups(extern_dir: str = "extern") -> Dict[str, str]:
    """Discover top-level groups by scanning extern/."""
    extern_path = resolve_extern_dir(extern_dir)
    groups: Dict[str, str] = {}

    if extern_path.exists():
        for item in extern_path.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                group_name = item.name
                description = GROUP_DESCRIPTIONS.get(
                    group_name, f"{group_name} - Project documentation"
                )
                groups[group_name] = description

    if not groups:
        groups = GROUP_DESCRIPTIONS.copy()

    return groups


def discover_subgroups(extern_dir: str = "extern") -> Dict[str, Dict[str, str]]:
    """
    Discover nested subgroups within each module.

    Returns:
        {module_name: {subgroup_id: subgroup_path}, ...}
        e.g. {"LArContent": {"LArContent_LArThreeDReco": "LArThreeDReco", ...}}
    """
    extern_path = resolve_extern_dir(extern_dir)
    all_subgroups: Dict[str, Dict[str, str]] = {}

    for module_name in GROUP_DESCRIPTIONS.keys():
        module_path = extern_path / module_name
        if not module_path.exists():
            continue

        subgroups: Dict[str, str] = {}
        roots = SUBGROUP_ROOTS.get(module_name, ["include", "src"])

        for root_dir in roots:
            root_path = module_path / root_dir
            if not root_path.exists():
                continue

            if module_name in SUBGROUP_ROOT_AS_GROUP:
                # The root_dir itself becomes a subgroup under the module.
                root_parts = [root_dir]
                subgroups[subgroup_id(module_name, root_parts)] = root_dir
                # All children are prefixed with root_dir so they nest under it.
                for item in sorted(root_path.rglob("*")):
                    if not item.is_dir():
                        continue
                    rel_parts = list(item.relative_to(root_path).parts)
                    if not rel_parts:
                        continue
                    if any(part.startswith(".") or part.startswith("_") for part in rel_parts):
                        continue
                    full_parts = root_parts + rel_parts
                    subgroups[subgroup_id(module_name, full_parts)] = "/".join(full_parts)
            else:
                # Root dir is a silent scan root; its children appear directly under the module.
                for item in sorted(root_path.rglob("*")):
                    if not item.is_dir():
                        continue
                    rel_parts = list(item.relative_to(root_path).parts)
                    if not rel_parts:
                        continue
                    if any(part.startswith(".") or part.startswith("_") for part in rel_parts):
                        continue
                    subgroups[subgroup_id(module_name, rel_parts)] = "/".join(rel_parts)

        all_subgroups[module_name] = subgroups

    return all_subgroups


def detect_group(file_path: str) -> Optional[str]:
    """Detect which top-level group a file belongs to."""
    norm = file_path.replace("\\", "/").lower()

    for group_name in GROUP_DESCRIPTIONS.keys():
        if (
            f"/extern/{group_name.lower()}/" in norm
            or f"/{group_name.lower()}/" in norm
        ):
            return group_name

    return None


def detect_subgroup(file_path: str) -> Optional[str]:
    """
    Detect which subgroup a file belongs to based on its directory structure.

    Returns:
        Subgroup ID like "LArContent_LArThreeDReco", or None.
    """
    path_norm = file_path.replace("\\", "/")
    norm = path_norm.lower()
    group = detect_group(file_path)

    if not group:
        return None

    subgroups = discover_subgroups()
    if group not in subgroups:
        return None

    subgroup_lookup = {name.lower(): name for name in subgroups[group].keys()}

    # Try to match subdirectories and pick the deepest discovered subgroup.
    best_match: Optional[tuple[int, str]] = None
    roots = SUBGROUP_ROOTS.get(group, [])
    for root_dir in roots:
        root_pattern = f"/{root_dir.lower()}/"
        idx = norm.find(root_pattern)
        if idx >= 0:
            after_root = path_norm[idx + len(root_pattern) :].lstrip("/")
            parts = [part for part in after_root.split("/") if part]

            if group in SUBGROUP_ROOT_AS_GROUP:
                # The root_dir itself is a valid subgroup (score 1).
                root_id = subgroup_id(group, [root_dir])
                actual_root_id = subgroup_lookup.get(root_id.lower())
                if actual_root_id is not None:
                    if best_match is None or 1 > best_match[0]:
                        best_match = (1, actual_root_id)

                # Deeper matches: root_dir + subdirectory parts (score = depth + 1).
                if len(parts) >= 2:
                    directory_parts = parts[:-1]
                    for depth in range(1, len(directory_parts) + 1):
                        candidate_parts = [root_dir] + directory_parts[:depth]
                        candidate_id = subgroup_id(group, candidate_parts)
                        actual_id = subgroup_lookup.get(candidate_id.lower())
                        if actual_id is not None:
                            score = depth + 1
                            if best_match is None or score > best_match[0]:
                                best_match = (score, actual_id)
            else:
                if len(parts) < 2:
                    continue

                directory_parts = parts[:-1]
                for depth in range(1, len(directory_parts) + 1):
                    candidate_parts = directory_parts[:depth]
                    candidate_id = subgroup_id(group, candidate_parts)
                    actual_id = subgroup_lookup.get(candidate_id.lower())
                    if actual_id is not None:
                        if best_match is None or depth > best_match[0]:
                            best_match = (depth, actual_id)

    return best_match[1] if best_match is not None else None


def get_module_relative_path(file_path: str) -> Optional[str]:
    """Convert file path to display path, stripping intermediate directories."""
    norm = file_path.replace("\\", "/")
    lower = norm.lower()

    markers = [
        ("/larcontent/larpandoracontent/", "LArContent/"),
        ("/larcontent/larpandoradlcontent/", "LArContent/larpandoradlcontent/"),
        ("/pandoramonitoring/", "PandoraMonitoring/"),
        ("/pandorasdk/", "PandoraSDK/"),
        ("/larreco/", "LArReco/"),
        ("/larrecond/", "LArRecoND/"),
    ]

    for marker, prefix in markers:
        idx = lower.find(marker)
        if idx >= 0:
            suffix = norm[idx + len(marker) :].lstrip("/")
            if suffix:
                group_name = prefix.rstrip("/")
                filters = PATH_FILTERS.get(group_name, [])

                # Strip specified directories
                parts = suffix.split("/")
                filtered_parts = [
                    p for p in parts if p.lower() not in [f.lower() for f in filters]
                ]
                filtered_suffix = "/".join(filtered_parts)

                return (
                    f"{prefix}{filtered_suffix}"
                    if filtered_suffix
                    else prefix.rstrip("/")
                )
            return prefix.rstrip("/")

    return None
