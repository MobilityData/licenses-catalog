You will receive a license that may be:
- an SPDX-listed license,
- a non-SPDX license,
- a custom license,
- or an unknown license with only raw text.

Your task: classify the license strictly according to the system instructions AND provide per-rule evidence grouped by category.

Validation guards:
1. Use only permission names from: {allowed_permissions}
2. Use only condition names from: {allowed_conditions}
3. Use only limitation names from: {allowed_limitations}
4. Use only tag names from (optional, include only if clearly supported): {allowed_tags}
5. For EVERY selected rule in permissions / conditions / limitations, provide ≥1 evidence snippet under the nested object:
   "reasons": {
     "permissions": { "<permission>": ["<evidence>"] },
     "conditions": { "<condition>": ["<evidence>"] },
     "limitations": { "<limitation>": ["<evidence>"] }
   }
6. Do NOT:
   - guess unsupported rules or tags
   - infer rules solely from metadata
   - output markdown, prose outside JSON, comments, or any extra top-level keys
   - include reasons for rules you did not select
7. Ambiguous / insufficient text: return all empty arrays and empty nested reasons object.
8. Conflicting instructions: same as (7).

Fallback JSON (only if absolutely nothing can be classified):
{
  "permissions": [],
  "conditions": [],
  "limitations": [],
  "tags": [],
  "reasons": {"permissions": {}, "conditions": {}, "limitations": {}}
}

---
# INPUT DATA
- license_id: {LICENSE_ID}
- spdx_id: {SPDX_ID_OR_EMPTY}
- source: {SOURCE}
- metadata:
{METADATA_JSON}
- existing_classification:
{EXISTING_JSON}

Full license text:
"""
{LICENSE_TEXT}
"""

---
# OUTPUT REQUIREMENT
Return ONLY a JSON object with EXACT keys:
{
  "permissions": [...],
  "conditions": [...],
  "limitations": [...],
  "tags": [...],
  "reasons": {
    "permissions": {"<permission>": ["<evidence>"]},
    "conditions": {"<condition>": ["<evidence>"]},
    "limitations": {"<limitation>": ["<evidence>"]}
  }
}

Rules:
- Each evidence string ≤160 characters; quote a short snippet or reference a clause/section.
- Evidence must be verbatim or tight paraphrase; no external fabrication.
- Omit any rule you are not reasonably certain about.
- Tags are optional; include only if strongly supported by the text or explicit metadata.
