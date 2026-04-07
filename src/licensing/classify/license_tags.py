"""Tag registry and heuristics for license classification.

This module provides:
"""

import argparse
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[3]

LICENSES_DIR = BASE_DIR / "data" / "licenses"
TAGS_JSON_PATH = BASE_DIR / "data" / "tags.json"


class TagRegistry:
	"""Loads and validates tags from the tag registry (data/tags.json).

	Tags are of the form 'group:key'. Each group (e.g. 'license', 'domain') can contain:
	  - a special '_group' entry with {short, description}
	  - tag keys (e.g. 'creative-commons') with {description, url}
	"""

	def __init__(self, path: Path = TAGS_JSON_PATH) -> None:
		with path.open("r", encoding="utf-8") as f:
			self.registry: dict[str, dict[str, Any]] = json.load(f)

	def is_valid(self, tag: str) -> bool:
		group, _, key = tag.partition(":")
		if not group or not key:
			return False
		group_dict = self.registry.get(group)
		if not isinstance(group_dict, dict):
			return False
		if key == "_group":
			return False
		return key in group_dict

	def get_group_meta(self, group: str) -> dict[str, Any] | None:
		group_dict = self.registry.get(group)
		if not isinstance(group_dict, dict):
			return None
		meta = group_dict.get("_group")
		if isinstance(meta, dict):
			return meta
		return None

	def get_tag_info(self, tag: str) -> dict[str, Any] | None:
		group, _, key = tag.partition(":")
		group_dict = self.registry.get(group)
		if not isinstance(group_dict, dict):
			return None
		info = group_dict.get(key)
		if isinstance(info, dict):
			return info
		return None


def build_tags(spdx_id: str, spdx_info: dict[str, Any]) -> list[str]:
	"""Return raw tag list (strings) for a given SPDX ID using heuristics."""
	tags: list[str] = []
	sid = spdx_id.upper()

	osi = bool(spdx_info.get("isOsiApproved"))
	fsf = bool(spdx_info.get("isFsfLibre"))
	deprecated = bool(spdx_info.get("isDeprecatedLicenseId"))

	if osi:
		tags.append("spdx:osi-approved")
	if fsf:
		tags.append("spdx:fsf-free")
	if deprecated:
		tags.append("spdx:deprecated")

	public_domain = {"CC0-1.0", "UNLICENSE", "0BSD"}
	if sid in public_domain:
		tags += [
			"license:public-domain",
			"copyleft:none",
			"domain:content",
			"domain:data",
		]
		return tags

	if sid.startswith("CC-"):
		tags += [
			"license:creative-commons",
			"family:CC",
			"domain:content",
		]
		if "-BY-" in sid:
			tags.append("notes:attribution-required")
		if "-SA-" in sid:
			tags.append("notes:share-alike")
		if sid.startswith(("CC-BY-", "CC-BY-SA-")) and sid.endswith("-4.0"):
			tags.append("domain:data")
		return tags

	if sid.startswith(("ODBL", "ODC-", "PDDL")):
		tags += [
			"license:open-data-commons",
			"family:ODC",
			"domain:data",
		]
		if sid.startswith(("ODBL", "ODC-BY")):
			tags.append("notes:attribution-required")
			tags.append("notes:share-alike")
		return tags

	if sid.startswith(("OGL-", "NLOD-", "ETALAB-")):
		tags += [
			"license:government-open-license",
			"domain:data",
			"domain:content",
			"notes:government-open-license",
			"notes:attribution-required",
		]
		return tags

	if sid.startswith("GPL-"):
		tags += [
			"license:open-source",
			"family:GPL",
			"domain:software",
			"copyleft:strong",
		]
		return tags

	if sid.startswith("AGPL-"):
		tags += [
			"license:open-source",
			"family:AGPL",
			"domain:software",
			"copyleft:network",
		]
		return tags

	if sid.startswith("LGPL-"):
		tags += [
			"license:open-source",
			"family:LGPL",
			"domain:software",
			"copyleft:weak",
		]
		return tags

	if sid.startswith(("MPL-", "EPL-", "CDDL-")):
		tags += [
			"license:open-source",
			"domain:software",
			"copyleft:weak",
		]
		return tags

	if sid.startswith("GFDL-"):
		tags += [
			"license:open-source",
			"domain:documentation",
			"domain:content",
		]
		return tags

	if sid.startswith(("MIT", "BSD-", "APACHE-", "ISC", "ZLIB")):
		tags += [
			"license:open-source",
			"domain:software",
			"copyleft:permissive",
		]
		return tags

	tags += [
		"license:open-source",
		"domain:software",
	]
	return tags


def apply_tags_to_file(path: Path, registry: TagRegistry) -> None:
	"""Update a single merged license JSON file with tags in-place.

	Heuristic tags are merged with any existing tags already present in the
	file (e.g. tags set by the LLM classifier). Existing tags that are no
	longer valid according to the registry are dropped. The result is always
	a sorted, deduplicated list of valid tags regardless of call order.
	"""
	with path.open("r", encoding="utf-8") as f:
		data = json.load(f)

	spdx_info = data.get("spdx")
	if not isinstance(spdx_info, dict):
		return

	spdx_id = spdx_info.get("licenseId")
	if not spdx_id:
		return

	heuristic_tags = [t for t in build_tags(spdx_id, spdx_info) if registry.is_valid(t)]
	existing_tags = [t for t in data.get("tags", []) if registry.is_valid(t)]
	data["tags"] = sorted(set(existing_tags) | set(heuristic_tags))

	with path.open("w", encoding="utf-8") as f:
		json.dump(data, f, indent=2, ensure_ascii=False)


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
				data = json.load(f)
				if "tags" in data:
					continue
		apply_tags_to_file(json_file, registry)
