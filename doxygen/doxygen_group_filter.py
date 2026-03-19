#!/usr/bin/env python3

# Helper script to assign Doxygen input files to module groups/subgroups based
# on file path.
#
# For header files: normalises the \file path label and wraps the file content
# with @addtogroup ... @{ ... @}, so that classes/structs/functions appear as
# members of the correct group. The \file block itself does NOT get an \ingroup
# tag, so the file page is never listed as a group member -- only its contents.
#
# For source files (.cc, .cpp, etc.): passed through unchanged. Their classes
# are already documented in headers and will appear there via @addtogroup.

import os
import re
import sys

from groups import detect_group, detect_subgroup, get_module_relative_path

HEADER_EXTENSIONS = {".h", ".hh", ".hpp", ".hxx"}


def wrap_with_addtogroup(text: str, group: str, after_pos: int) -> str:
    """Wrap file content after after_pos with \\addtogroup ... @{ ... @}."""
    open_tag = f"\n/** @addtogroup {group}\n *  @{{ */\n"
    close_tag = "\n/** @} */\n"
    return text[:after_pos] + open_tag + text[after_pos:] + close_tag


def has_file_command(text: str) -> bool:
    """Return True if the text contains a \\file or @file command."""
    return re.search(r"(?:\\|@)file\b", text) is not None


def normalize_file_block(text: str, file_label: str) -> tuple[str, int] | None:
    """
    Normalize the \\file path in the first file doc block and strip any
    \\ingroup from it. Group membership is handled exclusively by @addtogroup.

    Returns:
        (updated_text, end_pos_of_block) or None if no file block is found.
    """
    pattern = re.compile(r"/\*\*.*?(?:\\|@)file\b.*?\*/", re.DOTALL)
    match = pattern.search(text)
    if not match:
        return None

    block = match.group(0)
    # Normalise the \file path.
    block = re.compile(r"((?:\\|@)file)\b[^\n\r]*").sub(rf"\1 {file_label}", block, count=1)
    # Remove any existing \ingroup line -- we don't want the file page itself
    # listed as a group member.
    block = re.sub(r"\n[ \t]*\*[ \t]*(?:\\|@)ingroup\b[^\n]*", "", block)

    updated = text[: match.start()] + block + text[match.end() :]
    new_end = match.start() + len(block)
    return updated, new_end


def main() -> int:
    if len(sys.argv) != 2:
        return 1

    input_file = sys.argv[1]

    try:
        with open(input_file, "r", encoding="utf-8", errors="replace") as handle:
            original = handle.read()
    except OSError:
        return 1

    ext = os.path.splitext(input_file)[1].lower()

    # Source files pass through unchanged: their classes are documented in
    # headers and will be picked up there via @addtogroup.
    if ext not in HEADER_EXTENSIONS:
        sys.stdout.write(original)
        return 0

    abs_input = os.path.abspath(input_file)
    group = detect_group(abs_input)
    subgroup = detect_subgroup(abs_input)
    file_label = get_module_relative_path(abs_input)

    if not group:
        sys.stdout.write(original)
        return 0

    target_group = subgroup if subgroup else group

    if has_file_command(original):
        result = normalize_file_block(original, file_label or os.path.basename(input_file))
        if result is not None:
            updated, block_end = result
            updated = wrap_with_addtogroup(updated, target_group, block_end)
            sys.stdout.write(updated)
            return 0

    # No \file block: inject a minimal one, then wrap the rest.
    file_block = f"/**\n * \\file {file_label or os.path.basename(input_file)}\n */\n"
    sys.stdout.write(file_block)
    sys.stdout.write(f"\n/** @addtogroup {target_group}\n *  @{{ */\n")
    sys.stdout.write(original)
    sys.stdout.write("\n/** @} */\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
