## License Merge Utility

### `merge_spdx_with_choosealicense.py`

This script merges license metadata from the [SPDX license-list-data](https://github.com/spdx/license-list-data) and [choosealicense.com](https://github.com/github/choosealicense.com) datasets. It outputs one JSON file per license in the `data/licenses/` folder.

### Output

Each output file is named using the SPDX ID (e.g., `MIT.json`) and contains:

| Field | Type | Description |
|---|---|---|
| `spdx` | object | Full SPDX license metadata block |
| `categorized` | boolean | `true` if the license was categorized by merging with an external source, `false` otherwise |
| `permissions` | array | List of granted permissions (e.g., `commercial-use`, `modifications`) |
| `conditions` | array | List of conditions that must be met (e.g., `include-copyright`) |
| `limitations` | array | List of limitations and restrictions (e.g., `no-liability`) |
| `tags` | array | Descriptive tags in `group:key` format — set by the heuristic tagger and/or the LLM classifier (e.g., `license:open-source`, `family:MIT`, `domain:software`) |
| `reasons` | object | LLM-provided reasoning for each assigned permission, condition, limitation, and tag. Only present after running the LLM classifier. |

### Usage

```bash
python merge_spdx_with_choosealicense.py
```

#### Options

| Flag                    | Description                                        |
|-------------------------|----------------------------------------------------|
| `--update-submodules`   | Pull the latest data from git submodules           |
| `--only-uncategorized`  | Export only licenses that are not categorized      |

#### Example

```bash
python merge_spdx_with_choosealicense.py --update-submodules --only-uncategorized
```

---

## License Inspector CLI

### `inspect_licenses.py`

A command-line utility to explore the merged SPDX license metadata.

### Usage

```bash
python inspect_licenses.py <command> [options]
```

### Commands

#### `count`

Show totals for all licenses, categorized and uncategorized.

```bash
python inspect_licenses.py count
```

#### `list`

List all license SPDX IDs.

```bash
python inspect_licenses.py list
```

**Options**:

- `--only-categorized`: list only categorized licenses  
- `--only-uncategorized`: list only uncategorized licenses

#### `summary`

Show a summary grouped by categorized status.

```bash
python inspect_licenses.py summary
```

#### `get`

Show metadata for a single license by SPDX ID (case-insensitive).

```bash
python inspect_licenses.py get mit
```

Outputs:

- SPDX ID
- Permissions
- Conditions
- Limitations

### Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

---

## License Tagging Utility

### `licenses_tags.py`

The `licenses_tags.py` script is used to apply tags to license JSON files in the `data/licenses/` directory. Tags provide metadata about licenses, such as their permissions, conditions, limitations, and domains of applicability. This script ensures consistency and accuracy by validating tags against a predefined tag registry.

### Output

Each license JSON file is updated with a `tags` field, which contains a list of tags describing the license. Tags are categorized into the following groups:

- **License Type**: e.g., `license:public-domain`, `license:open-source`, `license:creative-commons`.
- **Domain**: e.g., `domain:content`, `domain:data`, `domain:software`.
- **Copyleft Strength**: e.g., `copyleft:none`, `copyleft:weak`, `copyleft:strong`.
- **Family**: e.g., `family:CC` (Creative Commons), `family:GPL` (GNU General Public License).
- **SPDX flags**: e.g., `spdx:osi-approved`, `spdx:fsf-free`, `spdx:deprecated`.
- **Notes**: e.g., `notes:attribution-required`, `notes:share-alike`.

### Usage

Run the script from the repository root:

```bash
python licenses_tags.py

---

## License Classifier

### `classify_license.sh`

Classifies a license using an LLM (default: `gpt-5.4`) and writes standardised
`permissions`, `conditions`, `limitations`, `tags`, and `reasons` fields into the
license JSON file.

The classifier automatically injects **few-shot examples** from already-classified
licenses in `data/licenses/` (those with a non-empty `reasons` block) to guide the
LLM. The number of injected examples is controlled by `--max-examples`.

### Usage

```bash
./classify_license.sh [OPTIONS] <license-path>
```

#### Options

| Flag | Description |
|---|---|
| `<license-path>` | Path to a merged SPDX JSON file or a plain license text file |
| `--output [PATH]` | Write results to PATH; omit PATH to update the input file in-place; omit flag entirely to print to stdout |
| `--dry-run` | Print classification JSON to stdout without writing any files |
| `--spdx-id ID` | Override the SPDX ID (useful for plain-text inputs) |
| `--model MODEL` | LLM model name (default: `gpt-5.4`) |
| `--max-examples N` | Maximum few-shot examples to inject from already-classified licenses (default: `5`; set to `0` to disable) |
| `--skip-tags` | Skip heuristic tag inference; only LLM-assigned tags are included |
| `--disable-llm` | Disable LLM calls and return an empty classification (useful for testing) |
| `--credentials-file PATH` | Path to a dcredentials file containing `OPENAI_API_KEY` |
| `--system-prompt PATH` | Path to the system prompt markdown file (default: bundled `src/licensing/classify/data/SYSTEM_PROMPT.md`) |
| `--user-prompt PATH` | Path to the user prompt markdown file (default: bundled `src/licensing/classify/data/USER_PROMPT.md`) |

#### Examples

```bash
# Classify a license and print to stdout
./classify_license.sh ./data/licenses/MIT.json

# Classify and update in-place
./classify_license.sh ./data/licenses/MIT.json --output

# Classify with more few-shot examples for better accuracy
./classify_license.sh ./data/licenses/MIT.json --max-examples 10

# Classify with no few-shot examples
./classify_license.sh ./data/licenses/MIT.json --max-examples 0

# Preview without writing
./classify_license.sh ./data/licenses/MIT.json --dry-run
```

### Few-shot example injection

Each time the classifier runs, it scans `data/licenses/` for files that already
have a non-empty `reasons` block and injects up to `--max-examples` of them as
calibration examples into the system prompt. The license being classified is
excluded from the pool to avoid self-reference.

This means the classifier improves automatically as more licenses are classified:
the growing pool of examples helps the LLM handle edge cases (e.g. distinguishing
licenses that explicitly restrict commercial use from those that merely omit the
word "commercial").

### Environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | API key for OpenAI LLM calls |
| `DCREDENTIALS_FILE` | Path to a dcredentials file containing `OPENAI_API_KEY` |
| `DISABLE_LLM` | Set to `1` to skip LLM calls (equivalent to `--disable-llm`) |