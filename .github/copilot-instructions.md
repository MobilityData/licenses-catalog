# Copilot Instructions

## Ground Rules

- **Never commit to git.** Prepare changes and leave them for a human to review and commit locally.
- **Never comment on pull requests.** Leave PR review and commentary to humans.
- **Preserve backward compatibility.** This is a public PyPI package — refactoring must not break existing public APIs or data schemas. If a breaking change is genuinely unavoidable, flag it explicitly and note that the version in `pyproject.toml` must be bumped accordingly before release.

## Commands

```bash
# Install (required before running tests)
pip install -e ".[dev]"

# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_classify_license.py -v

# Run a single test by name
python -m pytest tests/test_classify_license.py::test_load_rules -v

# Classify a single license (LLM-based, requires OPENAI_API_KEY)
./scripts/classify_license.sh ./data/licenses/MIT.json --dry-run
```

## Architecture

The repo has two layers that mirror each other:

- **`data/`** — the live catalog used when running from the repo
  - `data/licenses/*.json` — one file per license, named by SPDX ID
  - `data/rules.json` — closed vocabulary of permissions/conditions/limitations
  - `data/tags.json` — closed vocabulary of tags (see Tag format below)

- **`src/licensing/`** — the Python package (published to PyPI)
  - `classify/classify_license.py` — LLM-based classifier (library + CLI entry point)
  - `classify/license_tags.py` — heuristic tag inference (`TagRegistry`, `build_tags`)
  - `inspect_licenses.py` — pandas-based CLI to query/count the catalog
  - `merge_spdx_with_choosealicense.py` — merges upstream SPDX + choosealicense.com data
  - `classify/data/` — **bundled copies** of `rules.json`, `tags.json`, prompt files, and a small set of few-shot examples; kept in sync with `data/` via `scripts/sync_package_data.py`

- **`scripts/`** — thin wrappers that set `PYTHONPATH` and call into `src/licensing/`

Data pipeline order: `merge_spdx_with_choosealicense.py` → `classify_license.sh` → `sync_package_data.py`.

Source repositories for upstream data live in `.spdx_license_repo/` and `.choosealicense_repo/` (git submodules).

## License JSON Schema

Every file in `data/licenses/` follows this structure:

```json
{
  "spdx": { "licenseId": "...", "licenseText": "...", "isOsiApproved": true, ... },
  "categorized": true,
  "permissions": ["commercial-use", "modifications"],
  "conditions": ["include-copyright"],
  "limitations": ["liability", "warranty"],
  "tags": ["license:open-source", "domain:software", "copyleft:permissive"],
  "reasons": {
    "permissions": { "commercial-use": ["[verbatim] \"...quote from license...\""] },
    "conditions": { "include-copyright": ["[verbatim] \"...\""] },
    "limitations": { "warranty": ["[verbatim] \"...\""] }
  }
}
```

## Key Conventions

**Rules** (`permissions`, `conditions`, `limitations`) are a closed vocabulary defined in `data/rules.json`. Never add rule names that aren't in that file.

**Tags** use `group:key` format (e.g., `license:open-source`, `domain:data`, `copyleft:weak`, `spdx:osi-approved`). Valid tags come from `data/tags.json`. The `TagRegistry` class validates them; `build_tags` infers them heuristically from SPDX metadata and rule combinations.

**Evidence prefixes** in `reasons` must be one of:
- `[verbatim]` — directly quotes or tightly paraphrases the license text
- `[inferred]` — implied by the overall grant or absence of a restriction

A single rule may have multiple evidence strings. Split a combined verbatim+inference into two separate strings.

**LLM credentials**: The classifier reads `OPENAI_API_KEY` from the environment, or falls back to `~/.dcredentials` (first non-comment line, or `OPENAI_API_KEY=sk-...`). Set `DISABLE_LLM=1` or pass `--disable-llm` to skip LLM calls during testing.

**Few-shot examples** for the LLM are loaded from `src/licensing/classify/data/examples/` (bundled) or from `data/licenses/` when running from the repo. Only licenses with non-empty `reasons` qualify. Up to 5 are selected via a greedy max-coverage strategy across rule profiles.

**Package data sync**: When `data/rules.json`, `data/tags.json`, or the prompt files change, run `scripts/sync_package_data.py` to update the bundled copies in `src/licensing/classify/data/`.

## Contributing a License

1. Add `data/licenses/<SPDX-ID>.json` following the schema above
2. Licenses must have a valid SPDX identifier
3. Use only rule names from `data/rules.json` and tag keys from `data/tags.json`
4. Every rule in `permissions`/`conditions`/`limitations` needs a corresponding entry in `reasons` with a `[verbatim]` or `[inferred]` evidence string
