#!/usr/bin/env python3

# Helper script to generate a Doxygen file defining top-level module groups.
#
# I.e. We want both high-level groups like "LArContent" and "PandoraSDK", but
# also subgroups for the various folders within those modules.

from pathlib import Path
import sys

from groups import discover_groups, discover_subgroups, resolve_extern_dir, subgroup_id

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
            items = sorted(
                subgroups[module_name].items(),
                key=lambda item: (item[1].count("/"), item[1].lower()),
            )
            for subgroup_name, subgroup_path in items:
                parent = module_name
                parts = [part for part in subgroup_path.split("/") if part]
                if len(parts) > 1:
                    parent = subgroup_id(module_name, parts[:-1])

                # The label is just the last part of the path, which is usually
                # the most descriptive. Otherwise we could end up with the group
                # being LArContent/LArThreeDReco/LArThreeDBase...but part
                # of the LArContent + LArContent/LArThreeDReco groups...which is
                # very redundant.
                #
                # Instead, just the last part, so we end up with a LArContent group,
                # then a LArThreeDReco subgroup, and then a LArThreeDBase
                # subgroup nested inside that.
                label = parts[-1]
                lines.append(f" * \\defgroup {subgroup_name} {label}")
                lines.append(f" * \\ingroup {parent}")
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
