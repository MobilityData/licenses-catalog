#!/usr/bin/env bash
set -euo pipefail

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
  pip install --upgrade pip >/dev/null
  pip install -r "${SCRIPT_DIR}/requirements.txt"
fi

# 4. Call the Python classifier with all passed arguments
python "${SCRIPT_DIR}/classify_license.py" "$@"
