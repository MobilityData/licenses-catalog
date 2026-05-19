"""Unit tests for licensing.classify.classify_license."""

import contextlib
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from licensing.classify.classify_license import (
    _extract_json_obj,
    _select_diverse_examples,
    format_few_shot_block,
    load_classified_examples,
    load_non_spdx_from_file,
    load_rules,
    load_spdx_license,
    load_system_prompt,
    load_tags,
    normalize_classification,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_SPDX_JSON = {
    "spdx": {
        "licenseId": "MIT",
        "licenseText": "Permission is hereby granted, free of charge...",
        "isOsiApproved": True,
        "isFsfLibre": True,
        "isDeprecatedLicenseId": False,
    },
    "categorized": True,
    "permissions": ["commercial-use"],
    "conditions": ["include-copyright"],
    "limitations": ["liability"],
    "tags": ["license:open-source"],
}

SAMPLE_LLM_RESPONSE = {
    "permissions": ["commercial-use", "modifications"],
    "conditions": ["include-copyright"],
    "limitations": ["liability"],
    "tags": ["license:open-source", "domain:software"],
    "reasons": {
        "permissions": {"commercial-use": ["Section 1: allows commercial use"]},
        "conditions": {"include-copyright": ["Section 2: must include copyright"]},
        "limitations": {},
    },
}


@pytest.fixture
def spdx_json_file(tmp_path):
    path = tmp_path / "MIT.json"
    path.write_text(json.dumps(SAMPLE_SPDX_JSON), encoding="utf-8")
    return path


@pytest.fixture
def plain_text_file(tmp_path):
    path = tmp_path / "my-license.txt"
    path.write_text("Permission is hereby granted, free of charge...", encoding="utf-8")
    return path


def run_main(args, llm_response=None):
    """Run main() with mocked call_llm; return captured stdout."""
    if llm_response is None:
        llm_response = SAMPLE_LLM_RESPONSE
    out = io.StringIO()
    with patch("licensing.classify.classify_license.call_llm", return_value=llm_response):
        import licensing.classify.classify_license as cl
        with contextlib.redirect_stdout(out):
            cl.main(args)
    return out.getvalue()


# ---------------------------------------------------------------------------
# _extract_json_obj
# ---------------------------------------------------------------------------

class TestExtractJsonObj:
    def test_plain_json_object(self):
        raw = '{"permissions": ["use"], "conditions": []}'
        assert _extract_json_obj(raw) == {"permissions": ["use"], "conditions": []}

    def test_json_in_markdown_code_block(self):
        raw = '```json\n{"key": "value"}\n```'
        result = _extract_json_obj(raw)
        assert result is not None
        assert result["key"] == "value"

    def test_json_embedded_in_prose(self):
        raw = 'Here is the result: {"permissions": ["x"]} — done.'
        assert _extract_json_obj(raw) == {"permissions": ["x"]}

    def test_nested_json(self):
        raw = '{"outer": {"inner": 1}}'
        assert _extract_json_obj(raw) == {"outer": {"inner": 1}}

    def test_invalid_returns_none(self):
        assert _extract_json_obj("no json here") is None

    def test_empty_string_returns_none(self):
        assert _extract_json_obj("") is None


# ---------------------------------------------------------------------------
# normalize_classification
# ---------------------------------------------------------------------------

class TestNormalizeClassification:
    def test_normalizes_plain_lists(self):
        result = normalize_classification({
            "permissions": ["a", "b"],
            "conditions": ["c"],
            "limitations": [],
            "tags": ["t"],
        })
        assert result["permissions"] == ["a", "b"]
        assert result["tags"] == ["t"]

    def test_none_values_become_empty_lists(self):
        result = normalize_classification({
            "permissions": None,
            "conditions": None,
            "limitations": None,
            "tags": None,
        })
        assert result["permissions"] == []
        assert result["tags"] == []

    def test_scalar_wrapped_in_list(self):
        result = normalize_classification({
            "permissions": "single",
            "conditions": [],
            "limitations": [],
            "tags": [],
        })
        assert result["permissions"] == ["single"]

    def test_missing_keys_default_to_empty_list(self):
        result = normalize_classification({})
        assert result["permissions"] == []
        assert result["conditions"] == []
        assert result["limitations"] == []
        assert result["tags"] == []

    def test_non_string_values_coerced(self):
        result = normalize_classification({"permissions": [1, True], "conditions": [], "limitations": [], "tags": []})
        assert result["permissions"] == ["1", "True"]


# ---------------------------------------------------------------------------
# load_rules
# ---------------------------------------------------------------------------

class TestLoadRules:
    def test_returns_permissions_conditions_limitations(self, tmp_path):
        data = {
            "permissions": [{"name": "commercial-use"}, {"name": "modifications"}],
            "conditions": [{"name": "include-copyright"}],
            "limitations": [{"name": "liability"}],
        }
        path = tmp_path / "rules.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = load_rules(path)
        assert result["permissions"] == ["commercial-use", "modifications"]
        assert result["conditions"] == ["include-copyright"]
        assert result["limitations"] == ["liability"]

    def test_raises_if_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_rules(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# load_tags
# ---------------------------------------------------------------------------

class TestLoadTags:
    def test_tags_have_group_prefix(self, tmp_path):
        data = {
            "license": {"_group": {}, "open-source": {}, "creative-commons": {}},
            "domain": {"_group": {}, "software": {}},
        }
        path = tmp_path / "tags.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        tags = load_tags(path)
        assert "license:open-source" in tags
        assert "license:creative-commons" in tags
        assert "domain:software" in tags

    def test_bare_keys_not_present(self, tmp_path):
        data = {"license": {"_group": {}, "open-source": {}}}
        path = tmp_path / "tags.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        tags = load_tags(path)
        assert "open-source" not in tags

    def test_skips_group_meta_key(self, tmp_path):
        data = {"license": {"_group": {"short": "x"}, "open-source": {}}}
        path = tmp_path / "tags.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        tags = load_tags(path)
        assert "license:_group" not in tags

    def test_result_is_sorted(self, tmp_path):
        data = {"b": {"_group": {}, "z": {}}, "a": {"_group": {}, "a": {}}}
        path = tmp_path / "tags.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        tags = load_tags(path)
        assert tags == sorted(tags)


# ---------------------------------------------------------------------------
# load_spdx_license
# ---------------------------------------------------------------------------

class TestLoadSpdxLicense:
    def test_extracts_license_text(self, spdx_json_file):
        text, _, _, _ = load_spdx_license(spdx_json_file)
        assert "Permission is hereby granted" in text

    def test_extracts_metadata(self, spdx_json_file):
        _, metadata, _, _ = load_spdx_license(spdx_json_file)
        assert metadata["spdx"]["licenseId"] == "MIT"

    def test_license_text_stripped_from_metadata_spdx_block(self, spdx_json_file):
        _, metadata, _, _ = load_spdx_license(spdx_json_file)
        assert "licenseText" not in metadata["spdx"]

    def test_extracts_existing_classification(self, spdx_json_file):
        _, _, existing, _ = load_spdx_license(spdx_json_file)
        assert existing["permissions"] == ["commercial-use"]
        assert existing["conditions"] == ["include-copyright"]

    def test_returns_raw_json(self, spdx_json_file):
        _, _, _, raw = load_spdx_license(spdx_json_file)
        assert raw["categorized"] is True
        assert raw["spdx"]["licenseId"] == "MIT"

    def test_raises_if_no_license_text(self, tmp_path):
        path = tmp_path / "no_text.json"
        path.write_text(json.dumps({"spdx": {"licenseId": "X"}}), encoding="utf-8")
        with pytest.raises(ValueError, match="Could not find license text"):
            load_spdx_license(path)


# ---------------------------------------------------------------------------
# load_non_spdx_from_file
# ---------------------------------------------------------------------------

class TestLoadNonSpdxFromFile:
    def test_returns_text(self, plain_text_file):
        text, _ = load_non_spdx_from_file(plain_text_file)
        assert "Permission is hereby granted" in text

    def test_metadata_source_is_file(self, plain_text_file):
        _, meta = load_non_spdx_from_file(plain_text_file)
        assert meta["source"] == "file"

    def test_metadata_includes_path(self, plain_text_file):
        _, meta = load_non_spdx_from_file(plain_text_file)
        assert str(plain_text_file) in meta["path"]


# ---------------------------------------------------------------------------
# call_llm (mocked)
# ---------------------------------------------------------------------------

class TestCallLlm:
    def test_disable_llm_env_returns_empty(self, monkeypatch):
        monkeypatch.setenv("DISABLE_LLM", "1")
        import licensing.classify.classify_license as cl
        result = cl.call_llm("sys", "usr", "text")
        assert result["permissions"] == []
        assert result["tags"] == []

    def test_modern_openai_client_used(self, monkeypatch):
        monkeypatch.delenv("DISABLE_LLM", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(SAMPLE_LLM_RESPONSE)
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai_cls = MagicMock(return_value=mock_client_instance)

        mock_openai = MagicMock()
        mock_openai.OpenAI = mock_openai_cls
        mock_openai.ChatCompletion = None

        with patch.dict(sys.modules, {"openai": mock_openai}):
            import licensing.classify.classify_license as cl
            result = cl.call_llm("sys", "usr", "text")

        assert result["permissions"] == SAMPLE_LLM_RESPONSE["permissions"]

    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("DISABLE_LLM", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("licensing.classify.classify_license.load_api_key_from_dcredentials", return_value=None):
            import licensing.classify.classify_license as cl
            with pytest.raises(RuntimeError, match="No OpenAI API key"):
                cl.call_llm("sys", "usr", "text")


# ---------------------------------------------------------------------------
# main() — integration
# ---------------------------------------------------------------------------

class TestMain:
    def test_stdout_contains_all_fields(self, spdx_json_file):
        output = run_main([str(spdx_json_file)])
        data = json.loads(output)
        for field in ("permissions", "conditions", "limitations", "tags", "reasons"):
            assert field in data, f"missing field: {field}"

    def test_heuristic_tags_merged_by_default(self, spdx_json_file):
        llm_resp = {**SAMPLE_LLM_RESPONSE, "tags": []}
        output = run_main([str(spdx_json_file)], llm_response=llm_resp)
        data = json.loads(output)
        # MIT is OSI-approved + permissive; heuristic tagger should add these
        assert "spdx:osi-approved" in data["tags"]
        assert "copyleft:permissive" in data["tags"]

    def test_skip_tags_omits_heuristic_tags(self, spdx_json_file):
        llm_resp = {**SAMPLE_LLM_RESPONSE, "tags": ["domain:software"]}
        output = run_main([str(spdx_json_file), "--skip-tags"], llm_response=llm_resp)
        data = json.loads(output)
        assert data["tags"] == ["domain:software"]
        assert "copyleft:permissive" not in data["tags"]

    def test_reasons_included_in_stdout(self, spdx_json_file):
        output = run_main([str(spdx_json_file)])
        data = json.loads(output)
        assert isinstance(data["reasons"], dict)

    def test_dry_run_prints_stdout_suppresses_output_file(self, spdx_json_file, tmp_path):
        out_path = tmp_path / "result.json"
        output = run_main([str(spdx_json_file), "--output", str(out_path), "--dry-run"])
        assert output.strip()
        assert not out_path.exists()

    def test_output_path_writes_file(self, spdx_json_file, tmp_path):
        out_path = tmp_path / "result.json"
        with patch("licensing.classify.classify_license.call_llm", return_value=SAMPLE_LLM_RESPONSE):
            import licensing.classify.classify_license as cl
            cl.main([str(spdx_json_file), "--output", str(out_path)])
        result = json.loads(out_path.read_text())
        assert "permissions" in result
        assert "reasons" in result
        assert result["spdx"]["licenseId"] == "MIT"

    def test_output_inplace_preserves_spdx_block(self, spdx_json_file):
        with patch("licensing.classify.classify_license.call_llm", return_value=SAMPLE_LLM_RESPONSE):
            import licensing.classify.classify_license as cl
            cl.main([str(spdx_json_file), "--output"])
        result = json.loads(spdx_json_file.read_text())
        assert result["spdx"]["licenseId"] == "MIT"
        assert "permissions" in result
        assert "reasons" in result

    def test_output_inplace_includes_reasons(self, spdx_json_file):
        with patch("licensing.classify.classify_license.call_llm", return_value=SAMPLE_LLM_RESPONSE):
            import licensing.classify.classify_license as cl
            cl.main([str(spdx_json_file), "--output"])
        result = json.loads(spdx_json_file.read_text())
        assert isinstance(result["reasons"], dict)

    def test_output_without_path_on_non_spdx_raises(self, plain_text_file):
        with patch("licensing.classify.classify_license.call_llm", return_value=SAMPLE_LLM_RESPONSE):
            import licensing.classify.classify_license as cl
            with pytest.raises(SystemExit, match="requires a SPDX JSON input file"):
                cl.main([str(plain_text_file), "--output"])

    def test_missing_input_raises_system_exit(self):
        import licensing.classify.classify_license as cl
        with pytest.raises(SystemExit):
            cl.main([])

    def test_nonexistent_file_raises(self):
        import licensing.classify.classify_license as cl
        with pytest.raises(FileNotFoundError):
            cl.main(["/nonexistent/path.json"])

    def test_legacy_spdx_json_flag(self, spdx_json_file):
        output = run_main(["--spdx-json", str(spdx_json_file)])
        data = json.loads(output)
        assert data["spdx_id"] == "MIT"

    def test_disable_llm_flag_returns_empty_classification(self, spdx_json_file):
        import licensing.classify.classify_license as cl
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cl.main([str(spdx_json_file), "--disable-llm"])
        data = json.loads(out.getvalue())
        assert data["permissions"] == []
        assert data["conditions"] == []
        assert data["limitations"] == []


# ---------------------------------------------------------------------------
# load_classified_examples
# ---------------------------------------------------------------------------

def _make_license_file(tmp_path, name, permissions, conditions, limitations, reasons=None):
    """Helper to write a minimal license JSON with optional reasons."""
    data = {
        "spdx": {"licenseId": name, "licenseText": f"License text for {name}"},
        "permissions": permissions,
        "conditions": conditions,
        "limitations": limitations,
        "reasons": reasons or {},
    }
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


SAMPLE_REASONS = {
    "permissions": {"commercial-use": ["[verbatim] §1: use for any purpose"]},
    "conditions": {"include-copyright": ["[verbatim] §2: retain copyright notice"]},
    "limitations": {"warranty": ["[verbatim] §3: provided as-is"]},
}


class TestLoadClassifiedExamples:
    def test_returns_examples_with_reasons(self, tmp_path):
        _make_license_file(tmp_path, "MIT", ["commercial-use"], ["include-copyright"], ["warranty"], SAMPLE_REASONS)
        results = load_classified_examples(licenses_dir=tmp_path)
        assert len(results) == 1
        assert results[0]["license_id"] == "MIT"

    def test_skips_files_without_reasons(self, tmp_path):
        _make_license_file(tmp_path, "NO-REASONS", ["commercial-use"], [], [], reasons={})
        results = load_classified_examples(licenses_dir=tmp_path)
        assert results == []

    def test_skips_files_with_empty_reasons_dict(self, tmp_path):
        _make_license_file(tmp_path, "EMPTY", [], [], [], reasons={"permissions": {}, "conditions": {}, "limitations": {}})
        results = load_classified_examples(licenses_dir=tmp_path)
        assert results == []

    def test_excludes_current_license(self, tmp_path):
        _make_license_file(tmp_path, "MIT", ["commercial-use"], [], [], SAMPLE_REASONS)
        _make_license_file(tmp_path, "Apache-2.0", ["commercial-use"], [], [], SAMPLE_REASONS)
        results = load_classified_examples(exclude_id="MIT", licenses_dir=tmp_path)
        ids = [r["license_id"] for r in results]
        assert "MIT" not in ids
        assert "Apache-2.0" in ids

    def test_respects_max_examples(self, tmp_path):
        for name in ["AAA", "BBB", "CCC", "DDD"]:
            _make_license_file(tmp_path, name, ["commercial-use"], [], [], SAMPLE_REASONS)
        results = load_classified_examples(max_examples=2, licenses_dir=tmp_path)
        assert len(results) == 2

    def test_max_examples_zero_returns_empty(self, tmp_path):
        _make_license_file(tmp_path, "MIT", ["commercial-use"], [], [], SAMPLE_REASONS)
        results = load_classified_examples(max_examples=0, licenses_dir=tmp_path)
        assert results == []

    def test_empty_dir_returns_empty(self, tmp_path):
        results = load_classified_examples(licenses_dir=tmp_path)
        assert results == []

    def test_result_contains_expected_fields(self, tmp_path):
        _make_license_file(tmp_path, "MIT", ["commercial-use"], ["include-copyright"], ["warranty"], SAMPLE_REASONS)
        result = load_classified_examples(licenses_dir=tmp_path)[0]
        assert result["license_id"] == "MIT"
        assert result["permissions"] == ["commercial-use"]
        assert result["conditions"] == ["include-copyright"]
        assert result["limitations"] == ["warranty"]
        assert "reasons" in result

    def test_skips_malformed_json(self, tmp_path):
        (tmp_path / "bad.json").write_text("not json", encoding="utf-8")
        _make_license_file(tmp_path, "MIT", ["commercial-use"], [], [], SAMPLE_REASONS)
        results = load_classified_examples(licenses_dir=tmp_path)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# format_few_shot_block
# ---------------------------------------------------------------------------

class TestFormatFewShotBlock:
    def test_empty_returns_placeholder(self):
        result = format_few_shot_block([])
        assert "No worked examples" in result

    def test_renders_license_id(self):
        examples = [{"license_id": "MIT", "permissions": ["commercial-use"], "conditions": [], "limitations": [], "reasons": {}}]
        result = format_few_shot_block(examples)
        assert "### Example: MIT" in result

    def test_renders_permissions_line(self):
        examples = [{"license_id": "X", "permissions": ["commercial-use", "modifications"], "conditions": [], "limitations": [], "reasons": {}}]
        result = format_few_shot_block(examples)
        assert "commercial-use, modifications" in result

    def test_none_permissions_renders_none(self):
        examples = [{"license_id": "X", "permissions": [], "conditions": [], "limitations": [], "reasons": {}}]
        result = format_few_shot_block(examples)
        assert "Permissions: none" in result

    def test_renders_reason_evidence(self):
        reasons = {"permissions": {"commercial-use": ["[verbatim] §1: any use"]}, "conditions": {}, "limitations": {}}
        examples = [{"license_id": "X", "permissions": ["commercial-use"], "conditions": [], "limitations": [], "reasons": reasons}]
        result = format_few_shot_block(examples)
        assert "[permissions] commercial-use" in result
        assert "[verbatim] §1: any use" in result

    def test_evidence_truncated_to_160_chars(self):
        long_ev = "A" * 200
        reasons = {"permissions": {"commercial-use": [long_ev]}, "conditions": {}, "limitations": {}}
        examples = [{"license_id": "X", "permissions": ["commercial-use"], "conditions": [], "limitations": [], "reasons": reasons}]
        result = format_few_shot_block(examples)
        assert "A" * 161 not in result
        assert "A" * 160 in result

    def test_multiple_examples_separated(self):
        ex = {"license_id": "X", "permissions": [], "conditions": [], "limitations": [], "reasons": {}}
        result = format_few_shot_block([ex, {**ex, "license_id": "Y"}])
        assert "### Example: X" in result
        assert "### Example: Y" in result


# ---------------------------------------------------------------------------
# main() — few-shot integration
# ---------------------------------------------------------------------------

class TestMainFewShot:
    def test_max_examples_zero_accepted(self, spdx_json_file):
        output = run_main([str(spdx_json_file), "--max-examples", "0"])
        data = json.loads(output)
        assert "permissions" in data

    def test_max_examples_default_applied(self, spdx_json_file):
        """main() should not raise when --max-examples uses its default."""
        output = run_main([str(spdx_json_file)])
        data = json.loads(output)
        assert "permissions" in data


# ---------------------------------------------------------------------------
# _select_diverse_examples
# ---------------------------------------------------------------------------

class TestSelectDiverseExamples:
    def _make(self, license_id, permissions, conditions=None, limitations=None):
        return {
            "license_id": license_id,
            "permissions": permissions,
            "conditions": conditions or [],
            "limitations": limitations or [],
            "reasons": {},
        }

    def test_returns_all_when_below_limit(self):
        exs = [self._make("A", ["p1"]), self._make("B", ["p2"])]
        assert _select_diverse_examples(exs, 5) == exs

    def test_returns_exact_when_equal(self):
        exs = [self._make("A", ["p1"]), self._make("B", ["p2"])]
        assert len(_select_diverse_examples(exs, 2)) == 2

    def test_selects_n_from_larger_pool(self):
        exs = [self._make(str(i), [f"p{i}"]) for i in range(10)]
        result = _select_diverse_examples(exs, 3)
        assert len(result) == 3

    def test_prefers_complementary_profiles(self):
        # A and C share p1; B adds p2; D adds p3 — best pair is B+D or A+B or A+D
        a = self._make("A", ["p1"])
        b = self._make("B", ["p1", "p2"])
        c = self._make("C", ["p1"])
        d = self._make("D", ["p3"])
        result = _select_diverse_examples([a, b, c, d], 2)
        ids = {r["license_id"] for r in result}
        # B has most rules; D adds the most new coverage after B
        assert "B" in ids
        assert "D" in ids

    def test_no_duplicates_in_result(self):
        exs = [self._make(str(i), ["p1", "p2"]) for i in range(6)]
        result = _select_diverse_examples(exs, 3)
        ids = [r["license_id"] for r in result]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Bundled package data defaults
# ---------------------------------------------------------------------------

class TestBundledDefaults:
    def test_load_rules_no_path_uses_bundled(self):
        rules = load_rules()
        assert "commercial-use" in rules["permissions"]
        assert "include-copyright" in rules["conditions"]
        assert "liability" in rules["limitations"]

    def test_load_tags_no_path_uses_bundled(self):
        tags = load_tags()
        assert any(t.startswith("license:") for t in tags)
        assert any(t.startswith("domain:") for t in tags)

    def test_load_system_prompt_no_path_uses_bundled(self):
        prompt = load_system_prompt()
        assert "permissions" in prompt
        # placeholder exists but is only substituted when main() passes the mapping
        assert "few_shot_examples" in prompt

    def test_load_system_prompt_substitutes_mapping(self):
        prompt = load_system_prompt(mapping={"few_shot_examples": "INJECTED"})
        assert "INJECTED" in prompt
        assert "{few_shot_examples}" not in prompt

    def test_load_classified_examples_no_dir_uses_bundled(self):
        examples = load_classified_examples()
        assert len(examples) > 0
        for ex in examples:
            assert "license_id" in ex
            assert "permissions" in ex
            assert "reasons" in ex

    def test_bundled_examples_are_diverse(self):
        examples = load_classified_examples(max_examples=5)
        # Diversity: at least one without commercial-use (NC licenses)
        has_commercial = [e for e in examples if "commercial-use" in e["permissions"]]
        missing_commercial = [e for e in examples if "commercial-use" not in e["permissions"]]
        assert len(has_commercial) > 0
        assert len(missing_commercial) > 0

    def test_bundled_examples_exclude_current(self):
        examples = load_classified_examples(exclude_id="CC-BY-NC-4.0")
        ids = [e["license_id"] for e in examples]
        assert "CC-BY-NC-4.0" not in ids

