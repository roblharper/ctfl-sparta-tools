"""Command-line interface for ctfl-sparta-tools.

Usage examples
--------------
# Generate .in from a TOML case file
sparta-tools gen my_case.toml

# Generate and write to a specific path
sparta-tools gen my_case.toml -o run.in

# Load a GUI JSON save
sparta-tools gen my_case.json -o run.in

# Print derived quantities summary without writing
sparta-tools info my_case.toml

# Dump case back as TOML (round-trip / template creation)
sparta-tools dump my_case.toml

# Override individual fields on the command line
sparta-tools gen my_case.toml --set velocity=5000 --set n_ppc=50 -o run.in
"""

from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _load_case(path: str):
    from sparta_tools.case import SPARTACase
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        return SPARTACase.from_json(path)
    elif ext in (".toml", ""):
        return SPARTACase.from_toml(path)
    else:
        # try TOML first, fall back to JSON
        try:
            return SPARTACase.from_toml(path)
        except Exception:
            return SPARTACase.from_json(path)


def _apply_overrides(case, overrides: list[str]):
    """Apply --set key=value overrides to a loaded case."""
    if not overrides:
        return
    # Flat mapping of all settable leaf fields across sub-configs
    import dataclasses
    sub_map = {
        "freestream": case.freestream,
        "wall":       case.wall,
        "physics":    case.physics,
        "sim":        case.sim,
        "compute_dump": case.compute_dump,
    }
    # Build flat name→(obj, field) lookup
    flat: dict[str, tuple] = {}
    for sub_name, obj in sub_map.items():
        for f in dataclasses.fields(obj):
            # Qualified name always wins; unqualified only set if not already claimed
            qualified = f"{sub_name}.{f.name}"
            flat[qualified] = (obj, f)
            if f.name not in flat:
                flat[f.name] = (obj, f)
    # Also allow grid fields
    for f in dataclasses.fields(case.grid):
        flat[f.name] = (case.grid, f)
        flat[f"grid.{f.name}"] = (case.grid, f)
    flat["name"] = None  # handled specially

    for kv in overrides:
        if "=" not in kv:
            print(f"  Warning: ignoring malformed --set '{kv}' (expected key=value)", file=sys.stderr)
            continue
        key, _, raw_val = kv.partition("=")
        key = key.strip(); raw_val = raw_val.strip()

        if key == "name":
            case.name = raw_val
            continue
        if key == "species_file":
            case.species_file = raw_val
            continue

        if key not in flat or flat[key] is None:
            print(f"  Warning: unknown field '{key}', skipping", file=sys.stderr)
            continue

        obj, field = flat[key]
        # coerce to the field's type
        try:
            current = getattr(obj, field.name)
            t = type(current)
            if t is bool:
                setattr(obj, field.name, raw_val.lower() not in ("0", "false", "no"))
            elif t is int:
                setattr(obj, field.name, int(float(raw_val)))
            elif t is float:
                setattr(obj, field.name, float(raw_val))
            else:
                setattr(obj, field.name, raw_val)
        except Exception as e:
            print(f"  Warning: could not set {key}={raw_val}: {e}", file=sys.stderr)

    case.recompute()


# ── Sub-commands ──────────────────────────────────────────────────────────────

def cmd_gen(args):
    """Generate a SPARTA .in file."""
    case = _load_case(args.case_file)
    _apply_overrides(case, args.set or [])

    if case.derived.error:
        print(f"Error computing derived quantities: {case.derived.error}", file=sys.stderr)
        sys.exit(1)

    script = case.generate()

    out_path = args.output
    if not out_path:
        # derive from case name
        out_path = f"{case.name}.in"

    if out_path == "-":
        print(script)
    else:
        with open(out_path, "w") as f:
            f.write(script)
        print(f"Written: {out_path}")
        if not args.quiet:
            case.print_summary()


def cmd_info(args):
    """Print derived quantities summary."""
    case = _load_case(args.case_file)
    _apply_overrides(case, args.set or [])
    case.print_summary()


def cmd_dump(args):
    """Dump case as TOML (useful for generating templates or round-tripping GUI saves)."""
    case = _load_case(args.case_file)
    _apply_overrides(case, args.set or [])
    toml_str = case.to_toml()

    out_path = args.output
    if not out_path or out_path == "-":
        print(toml_str)
    else:
        with open(out_path, "w") as f:
            f.write(toml_str)
        print(f"Written: {out_path}")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sparta-tools",
        description="ctfl-sparta-tools: headless SPARTA DSMC pre-processor",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # gen
    pg = sub.add_parser("gen", help="Generate SPARTA .in input file")
    pg.add_argument("case_file", help="Path to case TOML or GUI JSON file")
    pg.add_argument("-o", "--output", default="",
                    help="Output path (default: <case_name>.in); use - for stdout")
    pg.add_argument("--set", action="append", metavar="key=value",
                    help="Override a case field (repeatable); e.g. --set velocity=5000")
    pg.add_argument("-q", "--quiet", action="store_true",
                    help="Suppress summary output")
    pg.set_defaults(func=cmd_gen)

    # info
    pi = sub.add_parser("info", help="Print derived quantities summary")
    pi.add_argument("case_file", help="Path to case TOML or GUI JSON file")
    pi.add_argument("--set", action="append", metavar="key=value")
    pi.set_defaults(func=cmd_info)

    # dump
    pd = sub.add_parser("dump", help="Dump case as TOML")
    pd.add_argument("case_file", help="Path to case TOML or GUI JSON file")
    pd.add_argument("-o", "--output", default="-",
                    help="Output path (default: stdout)")
    pd.add_argument("--set", action="append", metavar="key=value")
    pd.set_defaults(func=cmd_dump)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
