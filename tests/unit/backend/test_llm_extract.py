"""Schema §6, xác minh quote (nguyên văn + chuẩn hóa dấu cách), chấm điểm tin cậy,
client Ollama mock và hàng rào chống bịa số (spec §7, §9 Sprint 5)."""

from __future__ import annotations

import json

import pytest
import requests
from pydantic import ValidationError

from knowledge import llm_extract
from knowledge.units import UnitDef

STEM = "QTKD_1.061_2021_ND_V2"

UNIT_DEFS = [
    UnitDef("bar", 100_000.0, 0.0, ("bar",)),
    UnitDef("kPa", 1000.0, 0.0, ("kpa",)),
    UnitDef("%RH", 1.0, 0.0, ("%rh",)),
]


@pytest.fixture(scope="module")
def corpus_text(repo_root) -> str:
    return (repo_root / "build" / "spike_a" / f"{STEM}.md").read_text(encoding="utf-8")


def _max_error_fact(**overrides) -> llm_extract.Section6Fact:
    payload = {
        "fact_kind": "max_permissible_error",
        "label": "Sai số áp suất chỉnh đặt",
        "rel_op": "±",
        "limit": {"value": 3.0, "unit": "%", "quote": "± 3% áp suất chỉnh đặt của van"},
        "floor": {"value": 0.15, "unit": "bar", "quote": "không nhỏ hơn ± 0,15 bar"},
        "quote": (
            "Giá trị cho phép của sai số áp suất chỉnh đặt bằng ± 3% áp suất chỉnh đặt "
            "của van nhưng không nhỏ hơn ± 0,15 bar."
        ),
    }
    payload.update(overrides)
    return llm_extract.Section6Fact.model_validate(payload)


class _ScriptedClient:
    model_name = "scripted"

    def __init__(self, payload):
        self.payload = payload

    def chat(self, prompt, system=None):
        return json.dumps(self.payload, ensure_ascii=False)


# ── Schema pydantic: mọi trường số phải kèm quote ─────────────────────────────


def test_numeric_claim_requires_quote():
    with pytest.raises(ValidationError):
        llm_extract.NumericClaim(value=3.0, unit="%")


def test_numeric_claim_rejects_empty_quote():
    with pytest.raises(ValidationError):
        llm_extract.NumericClaim(value=3.0, quote="")


def test_max_error_fact_requires_limit():
    with pytest.raises(ValidationError):
        llm_extract.Section6Fact(fact_kind="max_permissible_error", quote="câu nào đó")


def test_formula_fact_requires_formula():
    with pytest.raises(ValidationError):
        llm_extract.Section6Fact(fact_kind="formula", quote="$x$")


def test_valid_fact_roundtrips():
    fact = _max_error_fact()
    assert fact.limit.value == 3.0
    assert fact.floor.value == 0.15
    assert llm_extract.numeric_claims(fact)[0][0] == "limit"


# ── Xác minh quote: nguyên văn + chuẩn hóa dấu cách ──────────────────────────


def test_quote_exact_match_returns_offsets(corpus_text):
    fact = _max_error_fact()
    verdict = llm_extract.verify_fact(fact, corpus_text)
    assert verdict.ok, verdict.reasons
    assert verdict.quote_match.exact
    assert corpus_text[verdict.quote_match.start : verdict.quote_match.end] == fact.quote


def test_quote_matches_after_whitespace_normalization():
    text = "Sai số cho phép là ±\u00a03%\u202fáp suất chỉnh đặt của van."
    match = llm_extract.locate_quote("± 3% áp suất chỉnh đặt của van", text)
    assert match.found
    assert not match.exact
    assert text[match.start : match.end] == "±\u00a03%\u202fáp suất chỉnh đặt của van"


def test_quote_normalization_matches_word_joiner_and_bom():
    # U+2060/U+FEFF không phải ``str.isspace()`` nhưng vnnum vẫn coi là dấu cách.
    text = "±\u20603%\ufeffáp suất chỉnh đặt của van"
    match = llm_extract.locate_quote("± 3% áp suất chỉnh đặt của van", text)
    assert match.found
    assert not match.exact


def test_hallucinated_fact_quote_rejected():
    fact = _max_error_fact(quote="Câu bịa hoàn toàn không có trong tài liệu.")
    verdict = llm_extract.verify_fact(fact, "Văn bản nguồn ngắn gọn.")
    assert not verdict.ok
    assert "fact_quote_not_found" in verdict.reasons


def test_numeric_quote_not_in_source_rejected(corpus_text):
    fact = _max_error_fact(
        limit={"value": 3.0, "unit": "%", "quote": "không được vượt quá 3 % bịa đặt"}
    )
    verdict = llm_extract.verify_fact(fact, corpus_text)
    assert not verdict.ok
    assert "limit_quote_not_found" in verdict.reasons


def test_numeric_value_not_in_quote_rejected(corpus_text):
    fact = _max_error_fact(
        limit={"value": 99.0, "unit": "%", "quote": "± 3% áp suất chỉnh đặt của van"}
    )
    verdict = llm_extract.verify_fact(fact, corpus_text)
    assert not verdict.ok
    assert "limit_value_not_in_quote" in verdict.reasons


def test_quote_contains_value_parses_vietnamese_numbers():
    assert llm_extract.quote_contains_value("không nhỏ hơn ± 0,15 bar", 0.15)
    assert not llm_extract.quote_contains_value("không nhỏ hơn ± 0,15 bar", 0.16)


# ── Chấm điểm tin cậy: quote + đơn vị + khoảng hợp lý ────────────────────────


def test_confidence_full_when_quote_unit_range_all_ok(corpus_text):
    fact = llm_extract.Section6Fact.model_validate(
        {
            "fact_kind": "max_permissible_error",
            "label": "Giá trị sàn",
            "rel_op": "±",
            "limit": {"value": 0.15, "unit": "bar", "quote": "không nhỏ hơn ± 0,15 bar"},
            "quote": (
                "Giá trị cho phép của sai số áp suất chỉnh đặt bằng ± 3% áp suất chỉnh đặt "
                "của van nhưng không nhỏ hơn ± 0,15 bar."
            ),
        }
    )
    confidence = llm_extract.score_confidence(
        fact,
        corpus_text,
        unit_defs=UNIT_DEFS,
        working_range_si=(0.0, 140_000_000.0),
    )
    assert confidence == 1.0


def test_confidence_lowered_by_unresolved_unit(corpus_text):
    fact = _max_error_fact()  # limit dùng "%" — không có trong UNIT_DEFS
    confidence = llm_extract.score_confidence(
        fact, corpus_text, unit_defs=UNIT_DEFS, working_range_si=(0.0, 140_000_000.0)
    )
    assert confidence == pytest.approx(0.85)


def test_confidence_lowered_by_out_of_range_value(corpus_text):
    fact = llm_extract.Section6Fact.model_validate(
        {
            "fact_kind": "max_permissible_error",
            "rel_op": "=",
            "limit": {"value": 1400.0, "unit": "bar", "quote": "đến 1 400 bar"},
            "quote": "đến 1 400 bar",
        }
    )
    # Phạm vi đo giả định 0..10 bar → 1400 bar nằm ngoài, mất phần "khoảng hợp lý".
    confidence = llm_extract.score_confidence(
        fact, corpus_text, unit_defs=UNIT_DEFS, working_range_si=(0.0, 1_000_000.0)
    )
    assert confidence == pytest.approx(0.80)


def test_confidence_zero_when_quote_invalid(corpus_text):
    fact = _max_error_fact(quote="Câu bịa.")
    assert llm_extract.score_confidence(fact, corpus_text, unit_defs=UNIT_DEFS) == 0.0


# ── Trích xuất với client kịch bản + bịa số ───────────────────────────────────


def _valid_payload() -> dict:
    return {
        "facts": [
            {
                "fact_kind": "max_permissible_error",
                "label": "Sai số áp suất chỉnh đặt",
                "rel_op": "±",
                "limit": {"value": 3.0, "unit": "%", "quote": "± 3% áp suất chỉnh đặt của van"},
                "floor": {"value": 0.15, "unit": "bar", "quote": "không nhỏ hơn ± 0,15 bar"},
                "quote": (
                    "Giá trị cho phép của sai số áp suất chỉnh đặt bằng ± 3% áp suất "
                    "chỉnh đặt của van nhưng không nhỏ hơn ± 0,15 bar."
                ),
            },
            {
                "fact_kind": "formula",
                "label": "Sai số",
                "formula": "\\DeltaP_{cd} = P_{m} - P_{cd}",
                "quote": "$\\DeltaP_{cd} = P_{m} - P_{cd}$",
            },
        ]
    }


def test_extract_section6_accepts_valid_and_resolves_section_path(corpus_text):
    result = llm_extract.extract_section6(corpus_text, _ScriptedClient(_valid_payload()))
    assert result.error is None
    assert len(result.facts) == 2
    assert result.rejected == []
    assert all(f.section_path.startswith("6") for f in result.facts)
    assert result.facts[0].char_start is not None
    assert corpus_text[result.facts[0].char_start : result.facts[0].char_end] == (
        result.facts[0].fact.quote
    )


def test_extract_section6_rejects_hallucinations_zero_leak(corpus_text):
    payload = _valid_payload()
    payload["facts"].append(
        {
            "fact_kind": "max_permissible_error",
            "rel_op": "<=",
            "limit": {"value": 42.0, "unit": "%", "quote": "không được vượt quá 42 %"},
            "quote": "Dòng bịa hoàn toàn.",
        }
    )
    payload["facts"].append(
        {
            "fact_kind": "max_permissible_error",
            "rel_op": "±",
            "limit": {"value": 999.0, "unit": "%", "quote": "± 3% áp suất chỉnh đặt của van"},
            "quote": (
                "Giá trị cho phép của sai số áp suất chỉnh đặt bằng ± 3% áp suất "
                "chỉnh đặt của van nhưng không nhỏ hơn ± 0,15 bar."
            ),
        }
    )
    result = llm_extract.extract_section6(corpus_text, _ScriptedClient(payload))
    assert len(result.facts) == 2
    assert len(result.rejected) == 2
    assert llm_extract.numeric_hallucinations(result, corpus_text) == 0


def test_extract_section6_safe_failure_when_llm_unavailable(corpus_text):
    class _Down:
        model_name = "down"

        def chat(self, prompt, system=None):
            return None

    result = llm_extract.extract_section6(corpus_text, _Down())
    assert result.facts == []
    assert result.error == "llm_unavailable"


def test_extract_section6_invalid_json(corpus_text):
    class _Bad:
        model_name = "bad"

        def chat(self, prompt, system=None):
            return "xin chào, không phải JSON"

    result = llm_extract.extract_section6(corpus_text, _Bad())
    assert result.facts == []
    assert result.error == "invalid_json"


def test_parse_json_payload_strips_code_fence():
    payload = llm_extract.parse_json_payload('```json\n{"facts": []}\n```')
    assert payload == {"facts": []}


# ── Client Ollama: mock HTTP + thất bại an toàn ──────────────────────────────


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_ollama_client_posts_native_api_with_options(monkeypatch):
    captured = {}

    def _post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")
        return _FakeResp({"message": {"content": '{"facts": []}'}})

    monkeypatch.setattr(requests, "post", _post)
    client = llm_extract.OllamaClient(
        llm_extract.OllamaConfig(url="http://ollama:11434/v1/chat/completions", model="qwen2.5:7b")
    )
    out = client.chat("xin chào", system="hệ thống")

    assert out == '{"facts": []}'
    assert captured["url"] == "http://ollama:11434/api/chat"
    assert captured["json"]["model"] == "qwen2.5:7b"
    assert captured["json"]["stream"] is False
    assert captured["json"]["messages"][0]["role"] == "system"
    assert captured["json"]["options"]["temperature"] == 0.0


def test_ollama_client_safe_failure(monkeypatch):
    def _post(*args, **kwargs):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(requests, "post", _post)
    assert llm_extract.OllamaClient().chat("hi") is None


def test_ollama_config_from_env_prefers_section6_keys():
    config = llm_extract.OllamaConfig.from_env(
        {
            "OLLAMA_URL": "http://x:11434/v1/chat/completions",
            "OLLAMA_MODEL": "small",
            "SECTION6_OLLAMA_URL": "http://y:11434/api/chat",
            "SECTION6_LLM_MODEL": "big",
            "SECTION6_LLM_TIMEOUT": "7",
        }
    )
    assert config.url == "http://y:11434/api/chat"
    assert config.model == "big"
    assert config.timeout == 7


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", True), ("true", True), ("on", True), ("0", False), ("", False)],
)
def test_llm_extraction_enabled(value, expected):
    assert llm_extract.llm_extraction_enabled({"SECTION6_LLM_ENABLED": value}) is expected
