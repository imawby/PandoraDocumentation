#!/usr/bin/env python3

# Helper script to generate a Doxygen file defining top-level module groups.
#
# I.e. We want both high-level groups like "LArContent" and "PandoraSDK", but
# also subgroups for the various folders within those modules.

from pathlib import Path
import sys

from groups import discover_groups, discover_subgroups, resolve_extern_dir

def generate_dox() -> int:
    """Generate ModuleGroups.dox with top-level and nested subgroups."""
    extern_dir = resolve_extern_dir()
    groups = discover_groups(extern_dir)
    subgroups = discover_subgroups(extern_dir)

    lines = ["/**"]

    # Generate top-level groups
    for group_name, description in groups.items():
        lines.append(f" * \\defgroup {group_name} {group_name}")
        lines.append(f" * \\brief {description}")
        lines.append(" *")

    # Generate subgroups nested under their parent groups
    for module_name in sorted(groups.keys()):
        if module_name in subgroups:
            for subgroup_id, subgroup_path in sorted(subgroups[module_name].items()):
                lines.append(f" * \\defgroup {subgroup_id} {module_name}/{subgroup_path}")
                lines.append(f" * \\ingroup {module_name}")
                lines.append(" *")

    lines.append(" */")

    output = "\n".join(lines) + "\n"

    # Check if we are writing in the write place, i.e. next to the Doxyfile.
    current_dir = Path(__file__).parent
    doxyfile_path = current_dir / "Doxyfile"

    if not doxyfile_path.exists():
        doxyfile_path = current_dir / "doxygen" / "Doxyfile"

        if not doxyfile_path.exists():
            print("Warning: Could not find Doxyfile! Output will be written to current directory.", file=sys.stderr)
        else:
            output_file = current_dir / "doxygen" / "ModuleGroups.dox"
    else:
        output_file = current_dir / "ModuleGroups.dox"

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Generated {output_file}")
        return 0
    except OSError as e:
        print(f"Error writing {output_file}: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(generate_dox())
