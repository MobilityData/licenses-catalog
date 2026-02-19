"""Licenses Catalog (licenses_catalog)

Core library for inspecting, merging and classifying licenses.

Public entrypoints:
- classify_license: high-level helpers and CLI entrypoint
"""

from . import classify_license  # re-export module for convenience

__all__ = ["classify_license"]
