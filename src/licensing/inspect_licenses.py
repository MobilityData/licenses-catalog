"""Utilities to inspect merged license JSON files.

Exposes a CLI compatible with scripts/inspect_licenses.py.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
LICENSES_DIR = BASE_DIR / "data" / "licenses"


def load_licenses(directory: Path) -> pd.DataFrame:
	records = []
	for file in directory.glob("*.json"):
		with file.open("r", encoding="utf-8") as f:
			data = json.load(f)
			records.append(
				{
					"spdx_id": file.stem,
					"categorized": data.get("categorized", False),
					"permissions": data.get("permissions", []),
					"conditions": data.get("conditions", []),
					"limitations": data.get("limitations", []),
				}
			)
	return pd.DataFrame(records)


def handle_count(df: pd.DataFrame) -> None:
	total = len(df)
	categorized = df["categorized"].sum()
	uncategorized = total - categorized
	print(f"Total licenses: {total}")
	print(f"Categorized: {categorized}")
	print(f"Uncategorized: {uncategorized}")


def handle_list(df: pd.DataFrame, only_categorized: bool) -> None:
	filtered = df[df["categorized"]] if only_categorized else df
	for spdx_id in filtered["spdx_id"]:
		print(spdx_id)


def handle_summary(df: pd.DataFrame) -> None:
	print(df.groupby("categorized").agg(count=("spdx_id", "count")))


def handle_get(df: pd.DataFrame, license_id: str) -> None:
	license_id_lower = license_id.lower()
	df["spdx_id_lower"] = df["spdx_id"].str.lower()
	match = df[df["spdx_id_lower"] == license_id_lower]
	if match.empty:
		print(f"License with SPDX ID '{license_id}' not found.")
		return
	row = match.iloc[0]
	print(f"SPDX ID: {row['spdx_id']}")
	print(f"Permissions: {row['permissions']}")
	print(f"Conditions: {row['conditions']}")
	print(f"Limitations: {row['limitations']}")
	print(f"Categorized: {row['categorized']}")


def main() -> None:
	parser = argparse.ArgumentParser(description="Inspect categorized SPDX licenses.")
	subparsers = parser.add_subparsers(dest="command")

	subparsers.add_parser("count", help="Show total/categorized/uncategorized license count")

	list_parser = subparsers.add_parser("list", help="List license SPDX IDs")
	list_parser.add_argument("--only-categorized", action="store_true", help="List only categorized licenses")

	subparsers.add_parser("summary", help="Print summary by categorized state")

	get_parser = subparsers.add_parser("get", help="Show details for a specific license")
	get_parser.add_argument("license_id", help="SPDX ID of the license to display")

	args = parser.parse_args()
	df = load_licenses(LICENSES_DIR)

	if args.command == "count":
		handle_count(df)
	elif args.command == "list":
		handle_list(df, args.only_categorized)
	elif args.command == "summary":
		handle_summary(df)
	elif args.command == "get":
		handle_get(df, args.license_id)
	else:
		parser.print_help()


if __name__ == "__main__":
	main()
