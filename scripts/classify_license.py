#!/usr/bin/env python
"""
Classify licenses (SPDX and non-SPDX) using an LLM.

Features:
- dry-run: print classification, do not write files
- SPDX mode: read from your license repo JSON structure and update classification in-place
- non-SPDX mode:
  * read license text from a file, OR
  * download license text from a URL (with caching and force-download)
- outputs classification JSON:
  * SPDX: merged into the original JSON structure (permissions/conditions/limitations updated)
  * non-SPDX: standalone JSON file with those three arrays

Environment:
- Prefers OPENAI_API_KEY from the environment.
- If OPENAI_API_KEY is not set, attempts to read it from a dcredentials file:
    * DCREDENTIALS_FILE env var path, or
    * ~/.dcredentials (first non-empty, non-comment line, or OPENAI_API_KEY=...).
 - DISABLE_LLM=1 to skip LLM calls and return an empty classification (useful for testing).
"""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

import requests  # type: ignore

# ---------------------------------------------------------------------------
# Load rules dynamically from data/rules.json (permissions, conditions, limitations)
# and tags from data/tags.json
# ---------------------------------------------------------------------------

RULES_PATH = (Path(__file__).resolve().parent.parent / "data" / "rules.json").resolve()
TAGS_PATH = (Path(__file__).resolve().parent.parent / "data" / "tags.json").resolve()

def load_rules(path: Path = RULES_PATH) -> Dict[str, list]:
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
                flat.append(tag_key)
    return sorted(set(flat))

RULE_NAMES = load_rules()
TAG_NAMES = load_tags()

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SYSTEM_PROMPT_PATH = BASE_DIR.parent / "docs" / "classification" / "SYSTEM_PROMPT.md"
DEFAULT_USER_PROMPT_PATH = BASE_DIR.parent / "docs" / "classification" / "USER_PROMPT.md"


def load_api_key_from_dcredentials() -> Optional[str]:
    """Optionally load OPENAI_API_KEY from a local dcredentials file.

    Resolution order:
    1. DCREDENTIALS_FILE environment variable (if set)
    2. ~/.dcredentials

    File format:
    - First non-empty, non-comment line is used, OR
    - A line of the form OPENAI_API_KEY=sk-... (KEY=VALUE), in which case
      the value part is used.
    """
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


# ---------------------------------------------------------------------------
# SPDX loader — aware of your repo structure
# ---------------------------------------------------------------------------

def load_spdx_license(spdx_json_path: Path) -> Tuple[str, Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Load license text + metadata + existing classification from your repo JSON.

    Expected structure (simplified):

    {
      "spdx": {
        "licenseId": "...",
        "licenseText": "...",
        ...
      },
      "categorized": true/false,
      "permissions": [...],
      "conditions": [...],
      "limitations": [...],
      "tags": [...]
    }

    Returns:
        license_text: the full license text to classify
        metadata: dict without the big licenseText
        existing_classification: dict with permissions/conditions/limitations arrays
        raw_json: the complete parsed JSON (so we can merge classification back)
    """
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


# ---------------------------------------------------------------------------
# Non-SPDX loaders
# ---------------------------------------------------------------------------

def load_non_spdx_from_file(path: Path) -> Tuple[str, Dict[str, Any]]:
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


def load_non_spdx_from_url(
    url: str,
    cache_dir: Path,
    force_download: bool = False,
) -> Tuple[str, Dict[str, Any]]:
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


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

# Remove SafeFormatter; use regex-based substitution to avoid issues with JSON braces

# Regex pattern to match simple placeholders like {allowed_permissions}
_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z0-9_]+)}")


def _sub_placeholders(text: str, mapping: Dict[str, Any]) -> str:
    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key in mapping:
            return str(mapping[key])
        return match.group(0)  # leave untouched
    return _PLACEHOLDER_PATTERN.sub(repl, text)


def _allowed_mapping() -> Dict[str, Any]:
    # Provide the allowed lists as JSON arrays (human- and machine-friendly).
    return {
        "allowed_permissions": json.dumps(RULE_NAMES["permissions"], ensure_ascii=False),
        "allowed_conditions": json.dumps(RULE_NAMES["conditions"], ensure_ascii=False),
        "allowed_limitations": json.dumps(RULE_NAMES["limitations"], ensure_ascii=False),
        "allowed_tags": json.dumps(TAG_NAMES, ensure_ascii=False),
    }


def load_system_prompt(path: str | Path = DEFAULT_SYSTEM_PROMPT_PATH, mapping: Optional[Dict[str, Any]] = None) -> str:
    """
    Read `path` (resolved relative to this script if not absolute) and format placeholders.
    Known keys from `_allowed_mapping()` are supplied by default so `allowed_*` placeholders
    are replaced rather than left untouched.
    """
    p = Path(path)
    if not p.is_absolute():
        p = (BASE_DIR / p).resolve()

    if not p.exists():
        raise FileNotFoundError(f"System prompt file not found: {p}")

    text = p.read_text(encoding="utf-8")
    # Merge default allowed mappings with any user-provided mapping (user mapping wins).
    merged_mapping = {**_allowed_mapping(), **(mapping or {})}

    return _sub_placeholders(text, merged_mapping)


def build_user_prompt(
    template_path: Path,
    license_id: str,
    spdx_id: Optional[str],
    source: str,
    metadata: Dict[str, Any],
    existing_classification: Optional[Dict[str, Any]],
    license_text: str,
) -> str:
    """
    Read the user prompt template and format it with the provided values.
    Also inject `allowed_permissions`, `allowed_conditions`, and `allowed_limitations`
    so templates that reference those keys are filled in.
    """
    template = template_path.read_text(encoding="utf-8")

    mapping: Dict[str, Any] = {
        "LICENSE_ID": license_id,
        "SPDX_ID_OR_EMPTY": spdx_id or "",
        "SOURCE": source,
        "METADATA_JSON": json.dumps(metadata, indent=2, ensure_ascii=False),
        "EXISTING_JSON": json.dumps(existing_classification or {}, indent=2, ensure_ascii=False),
        "LICENSE_TEXT": license_text,
        # include allowed lists (lowercase keys commonly used in templates)
        **_allowed_mapping(),
    }

    return _sub_placeholders(template, mapping)


def _extract_json_obj(raw: str) -> Optional[Dict[str, Any]]:
    """Attempt to extract a JSON object from raw model output.
    Tries direct parse, then searches for first {...} block, ignoring code fences.
    """
    import json as _json
    raw = raw.strip()
    # Remove code fences if present
    if raw.startswith("```"):
        # strip the first fence
        parts = raw.split("```")
        # join middle parts excluding language identifiers
        raw = "\n".join([p for p in parts if not p.strip().startswith("json") and p.strip()])
    try:
        return _json.loads(raw)
    except Exception:
        pass
    # Find first JSON object heuristically
    start = raw.find('{')
    depth = 0
    candidate = []
    capturing = False
    for ch in raw[start:]:
        if ch == '{':
            depth += 1
            capturing = True
        if capturing:
            candidate.append(ch)
        if ch == '}':
            depth -= 1
            if depth == 0:
                break
    if candidate:
        snippet = ''.join(candidate)
        try:
            return _json.loads(snippet)
        except Exception:
            return None
    return None


def call_llm(system_prompt: str, user_prompt: str, license_text: str, model: str = "gpt-4.1") -> Dict[str, Any]:
    """Call the LLM and return parsed JSON classification.

    Behavior:
    - Attempts OpenAI modern client (>=1.0).
    - Falls back to legacy ChatCompletion if available.
    - On any failure or missing configuration returns an empty classification stub.
    """
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

    # Try environment first, then dcredentials file.
    api_key = os.environ.get("OPENAI_API_KEY") or load_api_key_from_dcredentials()
    provider_disabled = os.environ.get("DISABLE_LLM") == "1"

    if provider_disabled:
        print("LLM disabled via DISABLE_LLM=1; returning empty classification.", file=sys.stderr)
        return empty

    if not api_key:
        raise RuntimeError(
            "No OpenAI API key configured. Set OPENAI_API_KEY or provide a dcredentials file "
            "(DCREDENTIALS_FILE or ~/.dcredentials, or use --credentials-file)."
        )

    # Ensure OpenAI clients can see the key via env
    os.environ.setdefault("OPENAI_API_KEY", api_key)

    try:
        import openai  # type: ignore
    except Exception as exc:
        print(f"OpenAI import failed: {exc}; returning empty classification.", file=sys.stderr)
        return empty

    modern_client_cls = getattr(openai, "OpenAI", None)
    if modern_client_cls is not None:
        try:
            client = modern_client_cls()
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
            )
            content = None
            try:
                content = resp.choices[0].message.content
            except Exception:
                try:
                    content = resp.choices[0].text
                except Exception:
                    content = None
            if content:
                parsed = _extract_json_obj(content)
                if isinstance(parsed, dict):
                    parsed.setdefault("permissions", [])
                    parsed.setdefault("conditions", [])
                    parsed.setdefault("limitations", [])
                    parsed.setdefault("tags", [])
                    parsed.setdefault("reasons", {})
                    return parsed
                print("Model response lacked parseable JSON; returning empty classification.", file=sys.stderr)
                return empty
        except Exception as exc:
            print(f"Modern OpenAI client failed: {exc}; attempting legacy interface.", file=sys.stderr)
    else:
        print("Modern OpenAI client class not found; attempting legacy interface.", file=sys.stderr)

    legacy_client = getattr(openai, "ChatCompletion", None)
    if legacy_client is not None:
        try:
            resp = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
            )
            content = None
            try:
                content = resp.choices[0].message.content
            except Exception:
                try:
                    content = resp.choices[0].text
                except Exception:
                    content = None
            if content:
                parsed = _extract_json_obj(content)
                if isinstance(parsed, dict):
                    parsed.setdefault("permissions", [])
                    parsed.setdefault("conditions", [])
                    parsed.setdefault("limitations", [])
                    parsed.setdefault("tags", [])
                    parsed.setdefault("reasons", {})
                    return parsed
                print("Legacy client response lacked parseable JSON; returning empty classification.", file=sys.stderr)
                return empty
            print("Legacy client returned no content; returning empty classification.", file=sys.stderr)
            return empty
        except Exception as exc:
            print(f"Legacy OpenAI client failed: {exc}; returning empty classification.", file=sys.stderr)
            return empty
    else:
        print("Legacy ChatCompletion interface not available; returning empty classification.", file=sys.stderr)
        return empty


# ---------------------------------------------------------------------------
# Classification normalization
# ---------------------------------------------------------------------------

def _rule_category(rule: str) -> Optional[str]:
    if rule in RULE_NAMES["permissions"]: return "permissions"
    if rule in RULE_NAMES["conditions"]: return "conditions"
    if rule in RULE_NAMES["limitations"]: return "limitations"
    return None

def normalize_classification(classification: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure arrays exist
    for k in ("permissions", "conditions", "limitations"):
        if k not in classification or not isinstance(classification[k], list):
            classification[k] = []
    # Tags (optional)
    tags = classification.get("tags")
    if isinstance(tags, list):
        classification["tags"] = [t for t in tags if isinstance(t, str) and t in TAG_NAMES]
    else:
        classification["tags"] = []
    # Normalize reasons to nested form
    reasons = classification.get("reasons")
    nested = {"permissions": {}, "conditions": {}, "limitations": {}}
    if isinstance(reasons, dict):
        # Case 1: already nested (category keys mapping to dicts)
        if all(cat in reasons for cat in ("permissions", "conditions", "limitations")) and any(isinstance(reasons[cat], dict) for cat in reasons):
            for cat in ("permissions", "conditions", "limitations"):
                cat_map = reasons.get(cat)
                if isinstance(cat_map, dict):
                    for rule, evidences in cat_map.items():
                        if rule in classification[cat] and isinstance(evidences, list):
                            cleaned = [e for e in evidences if isinstance(e, str) and e.strip()]
                            if cleaned:
                                nested[cat][rule] = cleaned
            classification["reasons"] = nested
            return classification
        # Case 2: flat mapping rule->evidence list
        for rule, evidences in reasons.items():
            cat = _rule_category(rule)
            if cat and rule in classification[cat] and isinstance(evidences, list):
                cleaned = [e for e in evidences if isinstance(e, str) and e.strip()]
                if cleaned:
                    nested[cat][rule] = cleaned
    classification["reasons"] = nested
    return classification


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify licenses (SPDX and non-SPDX) using an LLM.")
    src_group = parser.add_mutually_exclusive_group(required=True)
    src_group.add_argument("--spdx-json", type=Path, help="Path to license JSON in the repo (with a top-level 'spdx' block).")
    src_group.add_argument("--non-spdx-file", type=Path, help="Path to text/markdown file containing the full license text.")
    src_group.add_argument("--non-spdx-url", type=str, help="URL to download the license text from.")
    parser.add_argument("--license-id", type=str, help="Logical license identifier (if omitted, derived from filename or URL).")
    parser.add_argument("--existing-classification", type=Path, help=(
        "Optional JSON file with existing classification to pass as a hint. "
        "If using --spdx-json, the top-level permissions/conditions/limitations in that file "
        "are used by default, and this file (if provided) overrides them."))
    parser.add_argument("--system-prompt-file", type=Path, default=DEFAULT_SYSTEM_PROMPT_PATH, help=f"Path to system prompt markdown file (default: {DEFAULT_SYSTEM_PROMPT_PATH}).")
    parser.add_argument("--user-prompt-file", type=Path, default=DEFAULT_USER_PROMPT_PATH, help=f"Path to user prompt markdown file (default: {DEFAULT_USER_PROMPT_PATH}).")
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/licenses"), help="Cache directory for downloaded license texts (non-SPDX URL mode).")
    parser.add_argument("--force-download", action="store_true", help="Force re-download of license text even if cached.")
    parser.add_argument("--output", type=Path, help=(
        "Output JSON file for classification. "
        "SPDX mode: if omitted, updates the same --spdx-json file in-place. "
        "Non-SPDX mode: if omitted, defaults to <license_id>.classification.json."))
    parser.add_argument("--dry-run", action="store_true", help="Do not write any files; print classification JSON to stdout only.")
    parser.add_argument("--model", type=str, default="gpt-4.1-mini", help="LLM model name for the provider (default: gpt-4.1-mini).")
    parser.add_argument(
        "--disable-llm",
        action="store_true",
        help=(
            "Disable LLM calls and return an empty classification. "
            "Equivalent to setting DISABLE_LLM=1 (useful for testing)."
        ),
    )
    parser.add_argument(
        "--credentials-file",
        type=Path,
        help=(
            "Path to a dcredentials-style file containing OPENAI_API_KEY. "
            "If provided, this overrides DCREDENTIALS_FILE and the default ~/.dcredentials lookup."
        ),
    )
    return parser.parse_args()


def derive_default_license_id(args: argparse.Namespace) -> str:
    if args.license_id: return args.license_id
    if args.spdx_json: return args.spdx_json.stem
    if args.non_spdx_file: return args.non_spdx_file.stem
    if args.non_spdx_url:
        clean = args.non_spdx_url.rstrip('/').split('/')[-1] or "non_spdx_license"
        return clean
    return "license"


def derive_default_output_path(args: argparse.Namespace, license_id: str, is_spdx: bool) -> Optional[Path]:
    if args.dry_run: return None
    if args.output: return args.output
    if is_spdx and args.spdx_json: return args.spdx_json
    return Path(f"{license_id}.classification.json")


def load_external_existing_classification(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path: return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    # CLI flag to disable LLM calls takes precedence and maps to DISABLE_LLM.
    if getattr(args, "disable_llm", False):
        os.environ["DISABLE_LLM"] = "1"
    # If provided, this overrides the default dcredentials resolution in
    # load_api_key_from_dcredentials().
    if getattr(args, "credentials_file", None) is not None:
        os.environ["DCREDENTIALS_FILE"] = str(args.credentials_file)
    license_id = derive_default_license_id(args)
    is_spdx_mode = args.spdx_json is not None
    if is_spdx_mode:
        license_text, metadata, existing_from_file, raw_json = load_spdx_license(args.spdx_json)
        spdx_id = metadata.get("spdx", {}).get("licenseId") or metadata.get("spdx", {}).get("licenseid", "")
        source_label = "spdx"
        existing_classification = existing_from_file
    elif args.non_spdx_file:
        license_text, metadata = load_non_spdx_from_file(args.non_spdx_file)
        spdx_id = ""
        source_label = "non-spdx"
        raw_json = None
        existing_classification = {"permissions": [], "conditions": [], "limitations": []}
    else:
        license_text, metadata = load_non_spdx_from_url(
            args.non_spdx_url,
            cache_dir=args.cache_dir,
            force_download=args.force_download,
        )
        spdx_id = ""
        source_label = "non-spdx"
        raw_json = None
        existing_classification = {"permissions": [], "conditions": [], "limitations": []}
    external_class = load_external_existing_classification(args.existing_classification)
    if external_class is not None:
        existing_classification = external_class
    system_prompt = load_system_prompt(args.system_prompt_file)
    user_prompt = build_user_prompt(
        template_path=args.user_prompt_file,
        license_id=license_id,
        spdx_id=spdx_id,
        source=source_label,
        metadata=metadata,
        existing_classification=existing_classification,
        license_text=license_text,
    )
    try:
        classification = call_llm(system_prompt, user_prompt, license_text=license_text, model=args.model)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    classification = normalize_classification(classification)
    output_path = derive_default_output_path(args, license_id, is_spdx_mode)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    if is_spdx_mode:
        merged = dict(raw_json)
        merged["permissions"] = classification.get("permissions", [])
        merged["conditions"] = classification.get("conditions", [])
        merged["limitations"] = classification.get("limitations", [])
        merged["tags"] = classification.get("tags", []) or merged.get("tags", [])  # overwrite only if provided
        merged["categorized"] = True
        merged["reasons"] = classification.get("reasons", {})
        if args.dry_run or not output_path:
            print(json.dumps(merged, indent=2, ensure_ascii=False))
        else:
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
            print(f"Updated SPDX license JSON written to {output_path}")
    else:
        # Non-SPDX classification include tags
        if args.dry_run or not output_path:
            print(json.dumps(classification, indent=2, ensure_ascii=False))
        else:
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(classification, f, indent=2, ensure_ascii=False)
            print(f"Non-SPDX classification written to {output_path}")

if __name__ == "__main__":
    main()
