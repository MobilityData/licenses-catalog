#!/usr/bin/env python
#!/usr/bin/env python
"""
licenses_tags.py

This script applies tag heuristics to license JSON files in the `data/licenses/` directory.
Tags provide metadata about licenses, such as their permissions, restrictions, and domains
of applicability. The script validates tags against a tag registry (`data/tags.json`) and
updates the `tags` field in each license JSON file.

Usage:
    python licenses_tags.py [--only-missing]

Options:
    --only-missing    Only add tags to files that do not already have a `tags` field.

Features:
- **Tag Generation**: Automatically generates tags for licenses based on their SPDX ID and metadata.
- **Validation**: Ensures generated tags are valid according to the tag registry.
- **Heuristics**: Applies predefined rules to assign tags based on license characteristics.

Tagging Categories:
- **License Type**: e.g., `license:public-domain`, `license:open-source`, `license:creative-commons`.
- **Domain**: e.g., `domain:content`, `domain:data`, `domain:software`.
- **Copyleft Strength**: e.g., `copyleft:none`, `copyleft:weak`, `copyleft:strong`.
- **Family**: e.g., `family:CC` (Creative Commons), `family:GPL` (GNU General Public License).
- **Notes**: e.g., `notes:attribution-required`, `notes:share-alike`.

Dependencies:
- Python 3.8+
- `data/tags.json`: The tag registry file containing valid tags and their metadata.

Examples:
1. Apply tags to all license files:
    python licenses_tags.py

2. Apply tags only to files missing the `tags` field:
    python licenses_tags.py --only-missing

Notes:
- Public domain licenses (e.g., `CC0-1.0`, `UNLICENSE`) are tagged as `license:public-domain` and apply to both `domain:content` and `domain:data`.
- Creative Commons licenses (e.g., `CC-BY-4.0`) are tagged as `license:creative-commons` and may include additional notes like `notes:attribution-required` or `notes:share-alike`.
- Open Data Commons licenses (e.g., `ODBL`, `PDDL`) are tagged as `license:open-data-commons` and focus on `domain:data`.

"""
import argparse
import json
import sys
from pathlib import Path

# Ensure the src/ package root is on sys.path when running this script
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
	sys.path.insert(0, str(SRC_DIR))

from licensing.classify.license_tags import BASE_DIR, LICENSES_DIR, TAGS_JSON_PATH, TagRegistry, apply_tags_to_file


def main() -> None:
	parser = argparse.ArgumentParser(
		description="Apply tag heuristics to merged license JSON files (data/licenses/*.json).",
	)
	parser.add_argument(
		"--only-missing",
		action="store_true",
		help="Only add tags to files that do not already have a 'tags' field.",
	)
	args = parser.parse_args()

	if not TAGS_JSON_PATH.exists():
		raise FileNotFoundError(f"Tag registry not found at {TAGS_JSON_PATH}")

	registry = TagRegistry(TAGS_JSON_PATH)

	for json_file in sorted(LICENSES_DIR.glob("*.json")):
		if args.only_missing:
			with json_file.open("r", encoding="utf-8") as f:
				try:
					data = json.load(f)
				except json.JSONDecodeError:
					continue
			if "tags" in data:
				continue
		apply_tags_to_file(json_file, registry)


if __name__ == "__main__":
	main()
