#!/usr/bin/env python3

# Helper script to assign Doxygen input files to top-level module groups based
# on file path.
#
# I.e. We make sure LArContent/** files are in the LArContent group, etc. This
# is done by inserting an \ingroup line into the first doc block containing a
# \file command, or by injecting a new doc block if no such block exists. If the
# file already contains an \ingroup command, it is left unchanged.

import os
import re
import sys


def detect_group(path: str) -> str | None:
    """
    Detect the project group based on the file path.

    Args:
        path: A file path string that may contain backslashes or forward slashes.

    Returns:
        A string representing the detected group name, or None if no group is detected.
    """
    norm = path.replace("\\", "/").lower()

    if "/larcontent/" in norm:
        return "LArContent"
    if "/pandoramonitoring/" in norm:
        return "PandoraMonitoring"
    if "/pandorasdk/" in norm:
        return "PandoraSDK"
    if "/larreco/" in norm:
        return "LArReco"
    if "/larrecond/" in norm:
        return "LArRecoND"

    return None


def module_relative_path(path: str) -> str | None:
    """
    Compute a display path for \file relative to the module input root.

    Examples:
        .../LArContent/larpandoracontent/LArCheating/Foo.h ->
            LArContent/LArCheating/Foo.h
        .../PandoraSDK/include/Api/Foo.h ->
            PandoraSDK/include/Api/Foo.h
    """
    norm = path.replace("\\", "/")
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
                return f"{prefix}{suffix}"
            return prefix.rstrip("/")

    return None


def has_ingroup(text: str) -> bool:
    """
    Check if the text contains an \\ingroup or @ingroup command.
    We don't want/need to modify files that already specify a group.

    Args:
        text: The content of a Doxygen input file as a string.

    Returns:
        True if an \\ingroup or @ingroup command is found, False otherwise.
    """
    return re.search(r"(?:\\|@)ingroup\s+\w+", text) is not None


def has_file_command(text: str) -> bool:
    """
    Check if the text contains a \\file or @file command.

    Args:
        text: The content of a Doxygen input file as a string.

    Returns:
        True if a \\file or @file command is found, False otherwise.
    """
    return re.search(r"(?:\\|@)file\b", text) is not None


def update_file_block(text: str, group: str, file_label: str, add_ingroup: bool) -> str | None:
    """
    Normalize the first \\file/@file block and optionally add \\ingroup.

    Args:
        text: The content of a Doxygen input file as a string.
        group: The group name to insert.
        file_label: The label/path to use for the \\file command.
        add_ingroup: Whether to add an \\ingroup line.

    Returns:
        The updated text, or None if no file block is found.
    """
    pattern = re.compile(r"/\*\*.*?(?:\\|@)file\b.*?\*/", re.DOTALL)
    match = pattern.search(text)

    if not match:
        return None

    block = match.group(0)
    file_cmd_pattern = re.compile(r"((?:\\|@)file)\b[^\n\r]*")
    updated_block = file_cmd_pattern.sub(rf"\1 {file_label}", block, count=1)

    if add_ingroup:
        if "\n *" in updated_block:
            updated_block = updated_block.replace("\n */", f"\n * \\ingroup {group}\n */", 1)
        else:
            updated_block = updated_block.replace("*/", f" \\ingroup {group} */", 1)

    return text[: match.start()] + updated_block + text[match.end() :]


def main() -> int:
    if len(sys.argv) != 2:
        return 1

    input_file = sys.argv[1]

    try:
        with open(input_file, "r", encoding="utf-8", errors="replace") as handle:
            original = handle.read()
    except OSError:
        return 1

    abs_input = os.path.abspath(input_file)
    group = detect_group(abs_input)
    file_label = module_relative_path(abs_input)

    if not group:
        sys.stdout.write(original)
        return 0

    needs_ingroup = not has_ingroup(original)

    if has_file_command(original):
        updated = update_file_block(original, group, file_label or os.path.basename(input_file), needs_ingroup)
        if updated is not None:
            sys.stdout.write(updated)
            return 0

    if not needs_ingroup:
        # File already controls its group and has no \file command: keep as-is.
        sys.stdout.write(original)
        return 0

    injected = "".join(
        [
            "/**\n",
            f" * \\file {file_label or os.path.basename(input_file)}\n",
            f" * \\ingroup {group}\n",
            " */\n",
        ]
    )

    sys.stdout.write(injected)
    sys.stdout.write(original)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
