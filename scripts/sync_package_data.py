#!/usr/bin/env python3
"""Sync bundled package data in src/licensing/classify/data/.

Run this script after:
  - Classifying a new license (to add it to the few-shot examples bundle)

Note: rules.json and tags.json are symlinks to data/rules.json and data/tags.json —
no sync needed for those. SYSTEM_PROMPT.md and USER_PROMPT.md live in
src/licensing/classify/data/ as canonical sources — edit them there directly.

Usage:
    python scripts/sync_package_data.py [--dry-run]

What it does:
  1. Ensures rules.json / tags.json symlinks exist in src/licensing/classify/data/
  2. For every license in data/licenses/ that has a non-empty reasons block,
     writes a slim version (licenseId, permissions, conditions, limitations, tags,
     reasons) to src/licensing/classify/data/examples/<SPDX-ID>.json

Slim versions strip the large spdx.licenseText / licenseTextHtml / standardLicenseTemplate
fields so the bundled package stays small (~47 KB vs ~581 KB for the full files).
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PKG_DATA_DIR = REPO_ROOT / "src" / "licensing" / "classify" / "data"
PKG_EXAMPLES_DIR = PKG_DATA_DIR / "examples"

_EMPTY_REASONS: dict = {"permissions": {}, "conditions": {}, "limitations": {}}

_SPDX_STRIP_KEYS = {
    "licenseText",
    "standardLicenseTemplate",
    "licenseTextHtml",
    "crossRef",
    "seeAlso",
}


def _slim_example(data: dict) -> dict:
    """Return a minimal copy of a license JSON suitable for few-shot injection."""
    spdx_block = data.get("spdx", {})
    slim_spdx = {k: v for k, v in spdx_block.items() if k not in _SPDX_STRIP_KEYS}
    return {
        "spdx": slim_spdx,
        "permissions": data.get("permissions") or [],
        "conditions": data.get("conditions") or [],
        "limitations": data.get("limitations") or [],
        "tags": data.get("tags") or [],
        "reasons": data.get("reasons") or {},
    }


def sync(dry_run: bool = False) -> None:
    """Sync all bundled package data."""

    def write(dest: Path, content: str) -> None:
        if dry_run:
            print(f"  [dry-run] would write {dest.relative_to(REPO_ROOT)}")
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

    # --- ensure symlinks for rules.json / tags.json ---
    symlinks = [
        (DATA_DIR / "rules.json", PKG_DATA_DIR / "rules.json"),
        (DATA_DIR / "tags.json", PKG_DATA_DIR / "tags.json"),
    ]
    for target, link in symlinks:
        rel_target = Path(os.path.relpath(target, link.parent))
        if link.is_symlink() and Path(os.readlink(link)) == rel_target:
            print(f"  symlink ok {link.relative_to(REPO_ROOT)}")
        elif dry_run:
            print(f"  [dry-run] would symlink {link.relative_to(REPO_ROOT)} -> {rel_target}")
        else:
            link.parent.mkdir(parents=True, exist_ok=True)
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(rel_target)
            print(f"  symlinked {link.relative_to(REPO_ROOT)} -> {rel_target}")

    # --- classified examples ---
    licenses_dir = DATA_DIR / "licenses"
    if not licenses_dir.exists():
        print(f"WARNING: licenses dir not found: {licenses_dir}", file=sys.stderr)
        return

    added = skipped = 0
    for path in sorted(licenses_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"WARNING: could not parse {path.name}: {exc}", file=sys.stderr)
            continue
        reasons = data.get("reasons", {})
        if not reasons or reasons == _EMPTY_REASONS:
            continue
        slim = _slim_example(data)
        license_id = slim["spdx"].get("licenseId") or path.stem
        dest = PKG_EXAMPLES_DIR / f"{license_id}.json"
        new_content = json.dumps(slim, indent=2, ensure_ascii=False)
        if dest.exists() and dest.read_text(encoding="utf-8") == new_content:
            skipped += 1
            continue
        write(dest, new_content)
        print(f"  {'would write' if dry_run else 'wrote'} example {dest.relative_to(REPO_ROOT)}")
        added += 1

    print(f"\nDone: {added} example(s) {'would be ' if dry_run else ''}written, {skipped} unchanged.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written without writing anything.")
    args = parser.parse_args()
    sync(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
