"""Unit tests for licensing.classify.license_tags."""

import json
import pytest
from pathlib import Path

from licensing.classify.license_tags import TagRegistry, build_tags, apply_tags_to_file


# ---------------------------------------------------------------------------
# Minimal tags.json fixture — covers every group used by build_tags
# ---------------------------------------------------------------------------

MINIMAL_TAGS = {
    "license": {
        "_group": {"short": "License type", "description": ""},
        "open-source": {"description": ""},
        "creative-commons": {"description": ""},
        "public-domain": {"description": ""},
        "government-open-license": {"description": ""},
        "open-data-commons": {"description": ""},
    },
    "domain": {
        "_group": {"short": "Domain", "description": ""},
        "software": {"description": ""},
        "content": {"description": ""},
        "data": {"description": ""},
        "documentation": {"description": ""},
    },
    "copyleft": {
        "_group": {"short": "Copyleft", "description": ""},
        "none": {"description": ""},
        "weak": {"description": ""},
        "strong": {"description": ""},
        "network": {"description": ""},
        "permissive": {"description": ""},
    },
    "family": {
        "_group": {"short": "Family", "description": ""},
        "CC": {"description": ""},
        "GPL": {"description": ""},
        "AGPL": {"description": ""},
        "LGPL": {"description": ""},
        "ODC": {"description": ""},
    },
    "notes": {
        "_group": {"short": "Notes", "description": ""},
        "attribution-required": {"description": ""},
        "share-alike": {"description": ""},
        "government-open-license": {"description": ""},
    },
    "spdx": {
        "_group": {"short": "SPDX", "description": ""},
        "osi-approved": {"description": ""},
        "fsf-free": {"description": ""},
        "deprecated": {"description": ""},
    },
}


@pytest.fixture
def tags_file(tmp_path):
    path = tmp_path / "tags.json"
    path.write_text(json.dumps(MINIMAL_TAGS), encoding="utf-8")
    return path


@pytest.fixture
def registry(tags_file):
    return TagRegistry(tags_file)


# ---------------------------------------------------------------------------
# TagRegistry
# ---------------------------------------------------------------------------

class TestTagRegistry:
    def test_valid_known_tag(self, registry):
        assert registry.is_valid("license:open-source")

    def test_valid_spdx_tag(self, registry):
        assert registry.is_valid("spdx:osi-approved")

    def test_invalid_unknown_group(self, registry):
        assert not registry.is_valid("unknown:tag")

    def test_invalid_unknown_key(self, registry):
        assert not registry.is_valid("license:nonexistent")

    def test_invalid_group_meta_key(self, registry):
        assert not registry.is_valid("license:_group")

    def test_invalid_no_colon(self, registry):
        assert not registry.is_valid("opensourcelicense")

    def test_invalid_empty_group(self, registry):
        assert not registry.is_valid(":open-source")

    def test_invalid_empty_key(self, registry):
        assert not registry.is_valid("license:")

    def test_get_group_meta_existing(self, registry):
        meta = registry.get_group_meta("license")
        assert meta is not None
        assert "short" in meta

    def test_get_group_meta_missing(self, registry):
        assert registry.get_group_meta("nonexistent") is None

    def test_get_tag_info_existing(self, registry):
        info = registry.get_tag_info("license:open-source")
        assert info is not None
        assert "description" in info

    def test_get_tag_info_missing_key(self, registry):
        assert registry.get_tag_info("license:nonexistent") is None

    def test_get_tag_info_missing_group(self, registry):
        assert registry.get_tag_info("ghost:tag") is None


# ---------------------------------------------------------------------------
# build_tags
# ---------------------------------------------------------------------------

SPDX_BASE = {"isOsiApproved": False, "isFsfLibre": False, "isDeprecatedLicenseId": False}


class TestBuildTags:
    def test_osi_approved(self):
        tags = build_tags("MIT", {**SPDX_BASE, "isOsiApproved": True})
        assert "spdx:osi-approved" in tags

    def test_fsf_free(self):
        tags = build_tags("GPL-2.0", {**SPDX_BASE, "isFsfLibre": True})
        assert "spdx:fsf-free" in tags

    def test_deprecated(self):
        tags = build_tags("GPL-1.0", {**SPDX_BASE, "isDeprecatedLicenseId": True})
        assert "spdx:deprecated" in tags

    def test_public_domain_cc0(self):
        tags = build_tags("CC0-1.0", SPDX_BASE)
        assert "license:public-domain" in tags
        assert "copyleft:none" in tags
        assert "domain:data" in tags

    def test_public_domain_unlicense(self):
        tags = build_tags("UNLICENSE", SPDX_BASE)
        assert "license:public-domain" in tags

    def test_creative_commons_by(self):
        tags = build_tags("CC-BY-4.0", SPDX_BASE)
        assert "license:creative-commons" in tags
        assert "family:CC" in tags
        assert "notes:attribution-required" in tags

    def test_creative_commons_share_alike(self):
        tags = build_tags("CC-BY-SA-4.0", SPDX_BASE)
        assert "notes:share-alike" in tags

    def test_creative_commons_data_tag_on_40(self):
        tags = build_tags("CC-BY-4.0", SPDX_BASE)
        assert "domain:data" in tags

    def test_odc_data_license(self):
        tags = build_tags("ODBL-1.0", SPDX_BASE)
        assert "license:open-data-commons" in tags
        assert "family:ODC" in tags
        assert "domain:data" in tags

    def test_odc_attribution(self):
        tags = build_tags("ODBL-1.0", SPDX_BASE)
        assert "notes:attribution-required" in tags

    def test_government_license(self):
        tags = build_tags("OGL-UK-3.0", SPDX_BASE)
        assert "license:government-open-license" in tags
        assert "domain:data" in tags

    def test_gpl_strong_copyleft(self):
        tags = build_tags("GPL-3.0", {**SPDX_BASE, "isOsiApproved": True})
        assert "copyleft:strong" in tags
        assert "family:GPL" in tags
        assert "domain:software" in tags

    def test_agpl_network_copyleft(self):
        tags = build_tags("AGPL-3.0", SPDX_BASE)
        assert "copyleft:network" in tags
        assert "family:AGPL" in tags

    def test_lgpl_weak_copyleft(self):
        tags = build_tags("LGPL-2.1", SPDX_BASE)
        assert "copyleft:weak" in tags
        assert "family:LGPL" in tags

    def test_mit_permissive(self):
        tags = build_tags("MIT", {**SPDX_BASE, "isOsiApproved": True})
        assert "copyleft:permissive" in tags
        assert "domain:software" in tags

    def test_apache_permissive(self):
        tags = build_tags("APACHE-2.0", SPDX_BASE)
        assert "copyleft:permissive" in tags

    def test_unknown_license_fallback(self):
        tags = build_tags("SOME-CUSTOM-1.0", SPDX_BASE)
        assert "license:open-source" in tags
        assert "domain:software" in tags


# ---------------------------------------------------------------------------
# apply_tags_to_file
# ---------------------------------------------------------------------------

class TestApplyTagsToFile:
    def _write_license(self, tmp_path, extra=None):
        data = {
            "spdx": {
                "licenseId": "MIT",
                "isOsiApproved": True,
                "isFsfLibre": False,
                "isDeprecatedLicenseId": False,
            },
            "categorized": True,
            "permissions": [],
            "conditions": [],
            "limitations": [],
        }
        if extra:
            data.update(extra)
        path = tmp_path / "MIT.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_adds_heuristic_tags(self, tmp_path, registry):
        path = self._write_license(tmp_path)
        apply_tags_to_file(path, registry)
        result = json.loads(path.read_text())
        assert "copyleft:permissive" in result["tags"]
        assert "domain:software" in result["tags"]

    def test_merges_with_existing_valid_tags(self, tmp_path, registry):
        path = self._write_license(tmp_path, {"tags": ["license:open-source"]})
        apply_tags_to_file(path, registry)
        result = json.loads(path.read_text())
        assert "license:open-source" in result["tags"]
        assert "copyleft:permissive" in result["tags"]

    def test_drops_invalid_existing_tags(self, tmp_path, registry):
        path = self._write_license(tmp_path, {"tags": ["invalid:ghost-tag", "license:open-source"]})
        apply_tags_to_file(path, registry)
        result = json.loads(path.read_text())
        assert "invalid:ghost-tag" not in result["tags"]
        assert "license:open-source" in result["tags"]

    def test_idempotent(self, tmp_path, registry):
        path = self._write_license(tmp_path)
        apply_tags_to_file(path, registry)
        first = json.loads(path.read_text())["tags"]
        apply_tags_to_file(path, registry)
        second = json.loads(path.read_text())["tags"]
        assert first == second

    def test_result_is_sorted(self, tmp_path, registry):
        path = self._write_license(tmp_path)
        apply_tags_to_file(path, registry)
        tags = json.loads(path.read_text())["tags"]
        assert tags == sorted(tags)

    def test_skips_file_without_spdx_block(self, tmp_path, registry):
        path = tmp_path / "no_spdx.json"
        path.write_text(json.dumps({"categorized": False}), encoding="utf-8")
        apply_tags_to_file(path, registry)
        result = json.loads(path.read_text())
        assert "tags" not in result

    def test_skips_file_without_license_id(self, tmp_path, registry):
        path = tmp_path / "no_id.json"
        path.write_text(json.dumps({"spdx": {"isOsiApproved": True}}), encoding="utf-8")
        apply_tags_to_file(path, registry)
        result = json.loads(path.read_text())
        assert "tags" not in result
