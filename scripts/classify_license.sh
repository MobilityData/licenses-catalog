#!/usr/bin/env bash
set -euo pipefail

#===============================================================================
# License Classification Script
#===============================================================================
# Wrapper script to run the Python-based license classifier with automatic
# virtual environment management.
#
# Usage:
#   ./classify_license.sh [OPTIONS]
#
# Description:
#   This script automates the setup and execution of the license classification
#   tool. It handles:
#   - Virtual environment creation (if not present)
#   - Python dependency installation/updates
#   - Execution of the classifier with all provided arguments
#
# Features:
#   - Automatic venv creation in scripts/.venv/
#   - Dependency installation from requirements.txt
#   - Safe activation and argument forwarding
#   - Idempotent: safe to run multiple times
#
# Input Source Options (one required):
#   --spdx-json PATH
#       Path to license JSON file in the repo (with top-level 'spdx' block)
#       Used for SPDX licenses with structured metadata
#
#   --non-spdx-file PATH
#       Path to text/markdown file containing the full license text
#       For local non-SPDX licenses
#
#   --non-spdx-url URL
#       URL to download the license text from
#       For remote non-SPDX licenses (with caching support)
#
# Optional Arguments:
#   --license-id ID
#       Logical license identifier (if omitted, derived from filename or URL)
#
#   --existing-classification PATH
#       JSON file with existing classification to use as a hint
#       Overrides any classification in --spdx-json file
#
#   --system-prompt-file PATH
#       Path to system prompt markdown file
#       Default: docs/classification/SYSTEM_PROMPT.md
#
#   --user-prompt-file PATH
#       Path to user prompt markdown file
#       Default: docs/classification/USER_PROMPT.md
#
#   --cache-dir PATH
#       Cache directory for downloaded license texts (non-SPDX URL mode)
#       Default: .cache/licenses
#
#   --force-download
#       Force re-download of license text even if cached
#
#   --output PATH
#       Output JSON file for classification results
#       - SPDX mode: defaults to updating --spdx-json file in-place
#       - Non-SPDX mode: defaults to <license_id>.classification.json
#
#   --dry-run
#       Print classification JSON to stdout without writing files
#
#   --model MODEL_NAME
#       LLM model name for the provider
#       Default: gpt-4.1-mini
#
#   --disable-llm
#       Disable LLM calls and return an empty classification.
#       Shorthand for setting DISABLE_LLM=1 (useful for testing).
#
#   --credentials-file PATH
#       Path to a "dcredentials"-style file containing OPENAI_API_KEY.
#       When provided, this overrides DCREDENTIALS_FILE and the default
#       ~/.dcredentials lookup used by classify_license.py.
#
# Examples:
#   # Classify a single license URL
#   ./classify_license.sh --non-spdx-url "https://creativecommons.org/licenses/by/4.0/" --dry-run
#
#   # Classify from SPDX JSON file (updates in-place)
#   ./classify_license.sh --spdx-json data/licenses/MIT.json
#
#   # Classify from SPDX JSON with custom output
#   ./classify_license.sh --spdx-json licenses.json --output results.json
#
#   # Classify from CSV file containing non-SPDX licenses
#   ./classify_license.sh --non-spdx-file licenses.csv --output results.json
#
#   # Force re-download with custom model
#   ./classify_license.sh --non-spdx-url "https://example.com/license" --force-download --model gpt-4o
#
#   # Dry run to preview classification
#   ./classify_license.sh --non-spdx-url "https://example.com/license" --dry-run
#
# Environment Variables:
#   OPENAI_API_KEY  - API key for OpenAI LLM calls. Recommended to set:
#                     export OPENAI_API_KEY="sk-..."
#                     If not set, the Python script will look for a
#                     dcredentials file (see below).
#   DCREDENTIALS_FILE - Optional path to a "dcredentials" file containing
#                     OPENAI_API_KEY. If not set, ~/.dcredentials is used.
#                     File format:
#                       - First non-empty, non-comment line is treated as
#                         the API key, OR
#                       - A line of the form:
#                           OPENAI_API_KEY=sk-...
#   DISABLE_LLM     - Set to 1 to skip LLM calls and return an empty
#                     classification. Equivalent to passing --disable-llm.
#   VENV_DIR        - Override default virtual environment location
#   SCRIPT_DIR      - Auto-detected directory of this script
#
# Requirements:
#   - Python 3.8+
#   - requirements.txt in same directory as script
#   - Either OPENAI_API_KEY set in the environment OR a valid dcredentials
#     file as described above (for LLM classification)
#
# Exit Codes:
#   0 - Success
#   1 - General error (missing dependencies, invalid arguments)
#   2 - Python execution error
#
# Notes:
#   - Virtual environment is created only once and reused
#   - Dependencies are installed/upgraded on each run
#   - Downloaded license texts are cached in .cache/licenses/
#   - Script must be executable: chmod +x classify_license.sh
#===============================================================================

# Directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

# 1. Create venv if missing
if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Creating virtualenv in ${VENV_DIR}..."
  python3 -m venv "${VENV_DIR}"
fi

# 2. Activate venv
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

# 3. Install requirements if requirements.txt exists
if [[ -f "${SCRIPT_DIR}/requirements.txt" ]]; then
  echo "Installing/updating Python dependencies..."
  if ! pip install --upgrade pip >/dev/null; then
    echo "Error: failed to upgrade pip in ${VENV_DIR}" >&2
    exit 1
  fi
  if ! pip install -r "${SCRIPT_DIR}/requirements.txt" >/dev/null; then
    echo "Error: failed to install Python dependencies from requirements.txt" >&2
    exit 1
  fi
fi

# 4. Call the Python classifier module in src/ with all passed arguments

# Ensure the src/ directory (which contains the "licensing" package) is on PYTHONPATH
REPO_ROOT="${SCRIPT_DIR}/.."
SRC_DIR="${REPO_ROOT}/src"
export PYTHONPATH="${SRC_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

python -m licensing.classify.classify_license "$@"
