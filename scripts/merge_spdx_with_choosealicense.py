import sys
from pathlib import Path

# Ensure the src/ package root is on sys.path when running this script
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from licensing import merge_spdx_with_choosealicense as _impl


def main() -> None:
    _impl.main()


if __name__ == "__main__":
    main()
