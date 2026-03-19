#!/usr/bin/env python3

# Helper script to assign Doxygen input files to module groups/subgroups based
# on file path.
#
# I.e. We make sure LArContent/** files are in the right module/subgroup.
# This is done by normalizing the first doc block containing a \file command,
# or by injecting a new doc block if no such block exists. Existing \ingroup
# commands are rewritten to the detected target group.

import os
import re
import sys

from groups import detect_group, detect_subgroup, get_module_relative_path


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


def update_file_block(text: str, group: str, file_label: str) -> str | None:
    """
    Normalize the first \\file/@file block and enforce \\ingroup.

    Args:
        text: The content of a Doxygen input file as a string.
        group: The group name to insert.
        file_label: The label/path to use for the \\file command.
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

    ingroup_pattern = re.compile(r"((?:\\|@)ingroup)\s+\w+")
    if ingroup_pattern.search(updated_block):
        updated_block = ingroup_pattern.sub(rf"\1 {group}", updated_block, count=1)
    elif "\n *" in updated_block:
        updated_block = updated_block.replace(
            "\n */", f"\n * \\ingroup {group}\n */", 1
        )
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
    subgroup = detect_subgroup(abs_input)
    file_label = get_module_relative_path(abs_input)

    if not group:
        sys.stdout.write(original)
        return 0

    target_group = subgroup if subgroup else group
    needs_ingroup = not has_ingroup(original)

    if has_file_command(original):
        updated = update_file_block(
            original, target_group, file_label or os.path.basename(input_file)
        )
        if updated is not None:
            sys.stdout.write(updated)
            return 0

    if not needs_ingroup:
        # File has no \file block but does declare a group: normalize that group.
        ingroup_pattern = re.compile(r"((?:\\|@)ingroup)\s+\w+")
        updated = ingroup_pattern.sub(rf"\1 {target_group}", original, count=1)
        sys.stdout.write(updated)
        return 0

    injected = "".join(
        [
            "/**\n",
            f" * \\file {file_label or os.path.basename(input_file)}\n",
            f" * \\ingroup {target_group}\n",
            " */\n",
        ]
    )

    sys.stdout.write(injected)
    sys.stdout.write(original)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
