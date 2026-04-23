#
#   MobilityData 2026
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

#!/usr/bin/env python
"""Classify licenses (SPDX and non-SPDX) using an LLM.

Library + CLI module extracted from the original scripts/classify_license.py.
"""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import requests  # type: ignore

from licensing.classify.license_tags import TagRegistry, build_tags


BASE_DIR = Path(__file__).resolve().parents[3]
RULES_PATH = (BASE_DIR / "data" / "rules.json").resolve()
TAGS_PATH = (BASE_DIR / "data" / "tags.json").resolve()


def load_rules(path: Path = RULES_PATH) -> dict[str, list]:
	if not path.exists():
		raise FileNotFoundError(f"Rules file not found: {path}")
	data = json.loads(path.read_text(encoding="utf-8"))

	def extract(names_list: list) -> list:
		return [item.get("name") for item in names_list if isinstance(item, dict) and item.get("name")]

	return {
		"permissions": extract(data.get("permissions", [])),
		"conditions": extract(data.get("conditions", [])),
		"limitations": extract(data.get("limitations", [])),
	}


def load_tags(path: Path = TAGS_PATH) -> list:
	if not path.exists():
		raise FileNotFoundError(f"Tags file not found: {path}")
	data = json.loads(path.read_text(encoding="utf-8"))
	flat: list[str] = []
	for category, entries in data.items():
		if isinstance(entries, dict):
			for tag_key in entries.keys():
				if tag_key == "_group":
					continue
				flat.append(f"{category}:{tag_key}")
	return sorted(set(flat))


RULE_NAMES = load_rules()
TAG_NAMES = load_tags()

DEFAULT_SYSTEM_PROMPT_PATH = BASE_DIR / "docs" / "classification" / "SYSTEM_PROMPT.md"
DEFAULT_USER_PROMPT_PATH = BASE_DIR / "docs" / "classification" / "USER_PROMPT.md"


def load_api_key_from_dcredentials() -> str | None:
	"""Optionally load OPENAI_API_KEY from a local dcredentials file."""

	path_env = os.environ.get("DCREDENTIALS_FILE")
	candidates: list[Path] = []
	if path_env:
		candidates.append(Path(path_env).expanduser())
	candidates.append(Path.home() / ".dcredentials")

	for path in candidates:
		if not path.exists():
			continue
		try:
			text = path.read_text(encoding="utf-8")
		except OSError:
			continue

		for raw_line in text.splitlines():
			line = raw_line.strip()
			if not line or line.startswith("#"):
				continue
			if "=" in line:
				key, value = line.split("=", 1)
				if key.strip() == "OPENAI_API_KEY" and value.strip():
					return value.strip()
			else:
				return line
	return None


def load_spdx_license(spdx_json_path: Path) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
	"""Load license text + metadata + existing classification from merged JSON."""
	with spdx_json_path.open("r", encoding="utf-8") as f:
		data = json.load(f)

	if "spdx" in data and isinstance(data["spdx"], dict):
		spdx_block = data["spdx"]
	else:
		spdx_block = data

	text_candidates = [
		"licenseText",
		"license_text",
		"standardLicenseTemplate",
		"content",
		"text",
	]

	license_text = None
	for key in text_candidates:
		candidate = spdx_block.get(key)
		if isinstance(candidate, str) and candidate.strip():
			license_text = candidate
			break

	if not license_text:
		raise ValueError(
			f"Could not find license text in SPDX JSON {spdx_json_path} "
			f"(looked in spdx.{', spdx.'.join(text_candidates)})"
		)

	metadata = {"spdx": dict(spdx_block)}
	for key in text_candidates:
		metadata["spdx"].pop(key, None)

	for k, v in data.items():
		if k in ("permissions", "conditions", "limitations", "tags", "categorized"):
			continue
		if k == "spdx":
			continue
		metadata[k] = v

	existing_classification = {
		"permissions": data.get("permissions") or [],
		"conditions": data.get("conditions") or [],
		"limitations": data.get("limitations") or [],
	}

	return license_text, metadata, existing_classification, data


def load_non_spdx_from_file(path: Path) -> tuple[str, dict[str, Any]]:
	with path.open("r", encoding="utf-8") as f:
		text = f.read()
	metadata = {
		"source": "file",
		"path": str(path),
	}
	return text, metadata


def _url_to_cache_path(url: str, cache_dir: Path) -> Path:
	h = hashlib.sha256(url.encode("utf-8")).hexdigest()
	return cache_dir / f"{h}.txt"


def load_non_spdx_from_url(url: str, cache_dir: Path, force_download: bool = False) -> tuple[str, dict[str, Any]]:
	cache_dir.mkdir(parents=True, exist_ok=True)
	cache_path = _url_to_cache_path(url, cache_dir)

	if cache_path.exists() and not force_download:
		text = cache_path.read_text(encoding="utf-8")
	else:
		resp = requests.get(url, timeout=20)
		resp.raise_for_status()
		text = resp.text
		cache_path.write_text(text, encoding="utf-8")

	metadata = {
		"source": "url",
		"url": url,
		"cached_path": str(cache_path),
	}
	return text, metadata


_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z0-9_]+)}")


def _sub_placeholders(text: str, mapping: dict[str, Any]) -> str:
	def repl(match):
		key = match.group(1)
		if key in mapping:
			return str(mapping[key])
		return match.group(0)

	return _PLACEHOLDER_PATTERN.sub(repl, text)


def _allowed_mapping() -> dict[str, Any]:
	return {
		"allowed_permissions": json.dumps(RULE_NAMES["permissions"], ensure_ascii=False),
		"allowed_conditions": json.dumps(RULE_NAMES["conditions"], ensure_ascii=False),
		"allowed_limitations": json.dumps(RULE_NAMES["limitations"], ensure_ascii=False),
		"allowed_tags": json.dumps(TAG_NAMES, ensure_ascii=False),
	}


def load_system_prompt(path: str | Path = DEFAULT_SYSTEM_PROMPT_PATH, mapping: dict[str, Any] | None = None) -> str:
	p = Path(path)
	if not p.is_absolute():
		p = (BASE_DIR / p).resolve()
	if not p.exists():
		raise FileNotFoundError(f"System prompt file not found: {p}")
	text = p.read_text(encoding="utf-8")
	merged_mapping = {**_allowed_mapping(), **(mapping or {})}
	return _sub_placeholders(text, merged_mapping)


def build_user_prompt(
	template_path: Path,
	license_id: str,
	spdx_id: str | None,
	source: str,
	metadata: dict[str, Any],
	existing_classification: dict[str, Any] | None,
	license_text: str,
) -> str:
	template = template_path.read_text(encoding="utf-8")
	mapping: dict[str, Any] = {
		"LICENSE_ID": license_id,
		"SPDX_ID_OR_EMPTY": spdx_id or "",
		"SOURCE": source,
		"METADATA_JSON": json.dumps(metadata, indent=2, ensure_ascii=False),
		"EXISTING_JSON": json.dumps(existing_classification or {}, indent=2, ensure_ascii=False),
		"LICENSE_TEXT": license_text,
		**_allowed_mapping(),
	}
	return _sub_placeholders(template, mapping)


def _extract_json_obj(raw: str) -> dict[str, Any] | None:
	import json as _json
	raw = raw.strip()
	if raw.startswith("```"):
		# Split on fences and strip any language identifier (e.g. "json") from
		# the first line of each fenced block before reassembling.
		parts = raw.split("```")
		cleaned = []
		for p in parts:
			lines = p.splitlines()
			if lines and lines[0].strip().isalpha():
				p = "\n".join(lines[1:])
			if p.strip():
				cleaned.append(p.strip())
		raw = "\n".join(cleaned)
	try:
		return _json.loads(raw)
	except Exception:
		pass
	start = raw.find("{")
	depth = 0
	candidate: list[str] = []
	capturing = False
	for ch in raw[start:]:
		if ch == "{":
			depth += 1
			capturing = True
		if capturing:
			candidate.append(ch)
		if ch == "}":
			depth -= 1
			if depth == 0:
				break
	if candidate:
		snippet = "".join(candidate)
		try:
			return _json.loads(snippet)
		except Exception:
			return None
	return None


def call_llm(system_prompt: str, user_prompt: str, license_text: str, model: str = "gpt-5.4") -> dict[str, Any]:
	import sys
	empty = {
		"permissions": [],
		"conditions": [],
		"limitations": [],
		"tags": [],
		"reasons": {
			"permissions": {},
			"conditions": {},
			"limitations": {},
		},
	}
	api_key = os.environ.get("OPENAI_API_KEY") or load_api_key_from_dcredentials()
	provider_disabled = os.environ.get("DISABLE_LLM") == "1"
	if provider_disabled:
		print("LLM disabled via DISABLE_LLM=1; returning empty classification.", file=sys.stderr)
		return empty
	if not api_key:
		raise RuntimeError(
			"No OpenAI API key configured. Set OPENAI_API_KEY or provide a dcredentials file "
			"(DCREDENTIALS_FILE or ~/.dcredentials, or use --credentials-file).",
		)
	os.environ.setdefault("OPENAI_API_KEY", api_key)
	try:
		import openai  # type: ignore
	except Exception as exc:
		print(f"OpenAI import failed: {exc}; returning empty classification.", file=sys.stderr)
		return empty
	modern_client_cls = getattr(openai, "OpenAI", None)
	if modern_client_cls is not None:
		try:
			client = modern_client_cls(api_key=api_key)
			resp = client.chat.completions.create(
				model=model,
				messages=[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": user_prompt},
				],
				temperature=0,
			)
			content = resp.choices[0].message.content or ""
			parsed = _extract_json_obj(content)
			if parsed is None:
				print("Could not parse JSON from model output; returning empty classification.", file=sys.stderr)
				return empty
			return parsed
		except Exception as exc:
			print(f"Modern OpenAI client call failed: {exc}; trying legacy client...", file=sys.stderr)
	legacy_chat = getattr(openai, "ChatCompletion", None)
	if legacy_chat is None:
		print("No compatible OpenAI ChatCompletion client; returning empty classification.", file=sys.stderr)
		return empty
	try:
		resp = legacy_chat.create(
			model=model,
			messages=[
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": user_prompt},
			],
			temperature=0,
		)
		content = resp["choices"][0]["message"]["content"]
		parsed = _extract_json_obj(content)
		if parsed is None:
			print("Could not parse JSON from legacy model output; returning empty classification.", file=sys.stderr)
			return empty
		return parsed
	except Exception as exc:
		print(f"Legacy OpenAI client call failed: {exc}; returning empty classification.", file=sys.stderr)
		return empty


def normalize_classification(obj: dict[str, Any]) -> dict[str, Any]:
	def ensure_str_list(value: Any) -> list[str]:
		if isinstance(value, list):
			return [str(v) for v in value]
		if value is None:
			return []
		return [str(value)]
	return {
		"permissions": ensure_str_list(obj.get("permissions")),
		"conditions": ensure_str_list(obj.get("conditions")),
		"limitations": ensure_str_list(obj.get("limitations")),
		"tags": ensure_str_list(obj.get("tags")),
	}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	"""Parse CLI arguments.

	The new CLI primarily expects a single positional ``license_path`` argument,
	but we also support legacy flags used by classify_license.sh such as
	``--spdx-json`` and ``--dry-run`` for backwards compatibility.
	"""
	parser = argparse.ArgumentParser(description="Classify a license using an LLM.")
	parser.add_argument(
		"license_path",
		nargs="?",
		help="Path to merged SPDX JSON file or license text file.",
	)
	parser.add_argument("--spdx-json", help="(legacy) Path to merged SPDX JSON file; alias for license_path.")
	parser.add_argument("--dry-run", action="store_true", help="(legacy) Print classification JSON to stdout without writing files.")
	parser.add_argument("--spdx-id", help="Optional SPDX ID for the license.")
	parser.add_argument("--credentials-file", help="Path to a dcredentials file with OPENAI_API_KEY.")
	parser.add_argument("--skip-tags", action="store_true", help="Skip heuristic tag inference; only LLM-assigned tags are included.")
	parser.add_argument("--disable-llm", action="store_true", help="Disable the LLM and return empty classification.")
	parser.add_argument("--system-prompt", default=str(DEFAULT_SYSTEM_PROMPT_PATH), help="Path to system prompt file.")
	parser.add_argument("--user-prompt", default=str(DEFAULT_USER_PROMPT_PATH), help="Path to user prompt template.")
	parser.add_argument("--model", default="gpt-4.1", help="LLM model name to use (default: gpt-4.1).")
	parser.add_argument(
		"--output",
		nargs="?",
		const="",
		default=None,
		metavar="PATH",
		help=(
			"Write results to PATH. "
			"If PATH is omitted, merges classification into the input SPDX JSON file in-place. "
			"If not provided at all, prints to stdout."
		),
	)
	return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
	args = parse_args(argv)
	if args.credentials_file:
		os.environ["DCREDENTIALS_FILE"] = args.credentials_file
	if args.disable_llm:
		os.environ["DISABLE_LLM"] = "1"
	path_str = args.license_path or args.spdx_json
	if not path_str:
		raise SystemExit("Error: you must provide either license_path or --spdx-json")
	path = Path(path_str)
	if not path.exists():
		raise FileNotFoundError(path)
	if path.suffix.lower() == ".json":
		license_text, metadata, existing_classification, raw_json = load_spdx_license(path)
		license_id = metadata["spdx"].get("licenseId", path.stem)
		spdx_id = metadata["spdx"].get("licenseId")
		source = "spdx-json"
	else:
		license_text, metadata = load_non_spdx_from_file(path)
		license_id = path.stem
		spdx_id = args.spdx_id
		existing_classification = None
		raw_json = None
		source = "file-text"
	system_prompt = load_system_prompt(args.system_prompt)
	user_prompt = build_user_prompt(
		Path(args.user_prompt),
		license_id=license_id,
		spdx_id=spdx_id,
		source=source,
		metadata=metadata,
		existing_classification=existing_classification,
		license_text=license_text,
	)
	try:
		raw_obj = call_llm(system_prompt, user_prompt, license_text, model=args.model)
	except RuntimeError as exc:
		print(f"Error: {exc}", file=os.sys.stderr)
		raise SystemExit(1)
	normalized = normalize_classification(raw_obj)

	# Merge LLM tags with heuristic tags for SPDX inputs so the result is
	# the same regardless of whether classify_license or licenses_tags runs first.
	llm_tags = normalized["tags"]
	if raw_json is not None and spdx_id and not args.skip_tags:
		registry = TagRegistry()
		heuristic_tags = [t for t in build_tags(spdx_id, raw_json.get("spdx", {})) if registry.is_valid(t)]
		merged_tags = sorted(set(llm_tags) | set(heuristic_tags))
	else:
		merged_tags = llm_tags

	classification = {
		"permissions": normalized["permissions"],
		"conditions": normalized["conditions"],
		"limitations": normalized["limitations"],
		"tags": merged_tags,
		"reasons": raw_obj.get("reasons", {}),
	}

	output_arg = args.output  # None = stdout, "" = in-place, non-empty = file path

	if output_arg is None or args.dry_run:
		output = {
			"license_id": license_id,
			"spdx_id": spdx_id,
			**classification,
		}
		print(json.dumps(output, indent=2, ensure_ascii=False))
		return

	if output_arg == "":
		if raw_json is None:
			raise SystemExit("Error: --output without a path requires a SPDX JSON input file")
		output_path = path
	else:
		output_path = Path(output_arg)

	if raw_json is not None:
		raw_json.update(classification)
		data_to_write = raw_json
	else:
		data_to_write = {"license_id": license_id, "spdx_id": spdx_id, **classification}

	output_path.write_text(json.dumps(data_to_write, indent=2, ensure_ascii=False), encoding="utf-8")
	print(f"Classification written to {output_path}", file=os.sys.stderr)


if __name__ == "__main__":
	main()
