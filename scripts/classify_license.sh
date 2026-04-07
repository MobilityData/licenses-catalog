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
# Input Source (one required):
#   PATH  (positional)
#       Path to a merged SPDX JSON file (with top-level 'spdx' block) or a
#       plain license text file.
#
#   --spdx-json PATH
#       (legacy) Alias for the positional PATH argument.
#
# Optional Arguments:
#   --spdx-id ID
#       Override the SPDX ID for the license (useful for plain text inputs).
#
#   --output [PATH]
#       Write classification results to a file.
#       - With PATH: writes to the specified file.
#       - Without PATH: merges classification into the input SPDX JSON file
#         in-place. Requires the input to be a SPDX JSON file.
#       - Omitted entirely: prints JSON to stdout.
#
#   --dry-run
#       Print classification JSON to stdout without writing any files.
#       Takes precedence over --output.
#
#   --system-prompt PATH
#       Path to the system prompt markdown file.
#       Default: docs/classification/SYSTEM_PROMPT.md
#
#   --user-prompt PATH
#       Path to the user prompt markdown file.
#       Default: docs/classification/USER_PROMPT.md
#
#   --model MODEL_NAME
#       LLM model name to use.
#       Default: gpt-4.1
#
#   --credentials-file PATH
#       Path to a "dcredentials"-style file containing OPENAI_API_KEY.
#       Overrides DCREDENTIALS_FILE env var and the default ~/.dcredentials
#       lookup.
#
#   --skip-tags
#       Skip heuristic tag inference. Only tags returned by the LLM are
#       included in the output. By default, heuristic tags are merged with
#       LLM tags automatically.
#
#   --disable-llm
#       Disable LLM calls and return an empty classification.
#       Equivalent to setting DISABLE_LLM=1 (useful for testing).
#
# Examples:
#   # Classify a SPDX JSON file, print to stdout
#   ./classify_license.sh ./data/licenses/MIT.json
#
#   # Classify and update the input file in-place
#   ./classify_license.sh --spdx-json ./data/licenses/MIT.json --output
#
#   # Classify and write results to a separate file
#   ./classify_license.sh ./data/licenses/MIT.json --output results.json
#
#   # Classify a plain license text file with a custom SPDX ID
#   ./classify_license.sh ./my-license.txt --spdx-id MIT
#
#   # Preview classification without writing anything
#   ./classify_license.sh ./data/licenses/MIT.json --dry-run
#
#   # Use a custom model and credentials file
#   ./classify_license.sh ./data/licenses/MIT.json --model gpt-4o --credentials-file ~/creds
#
# Environment Variables:
#   OPENAI_API_KEY    - API key for OpenAI LLM calls.
#                       If not set, the script falls back to a dcredentials
#                       file (see --credentials-file above).
#   DCREDENTIALS_FILE - Optional path to a dcredentials file containing
#                       OPENAI_API_KEY. Defaults to ~/.dcredentials.
#                       File format:
#                         - First non-empty, non-comment line is the API key,
#                           OR a line of the form: OPENAI_API_KEY=sk-...
#   DISABLE_LLM       - Set to 1 to skip LLM calls and return empty
#                       classification. Equivalent to --disable-llm.
#   VENV_DIR          - Override default virtual environment location.
#
# Requirements:
#   - Python 3.11+
#   - requirements.txt in same directory as this script
#   - OPENAI_API_KEY or a valid dcredentials file (for LLM classification)
#
# Exit Codes:
#   0 - Success
#   1 - General error (missing dependencies, invalid arguments)
#   2 - Python execution error
#
# Notes:
#   - Virtual environment is created only once and reused.
#   - Dependencies are installed/upgraded on each run.
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
