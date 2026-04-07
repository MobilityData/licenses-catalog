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