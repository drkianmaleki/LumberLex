"""
Phase 8 — Chatbot Module Tests
==============================
11 mocked tests (always run) + 3 live tests (@pytest.mark.llm).

Mocked tests use CapturingProvider to inspect the messages list passed to
chat() without making any network calls. They verify:
  - explain() returns the provider's response
  - normalisation is called / skipped correctly depending on result= kwarg
  - system prompt contains the right NormalizationResult fields
  - user message uses question= or DEFAULT_QUESTION as expected
  - history messages are assembled in the correct order
  - system messages in history are stripped (no duplication)
  - GroqProvider raises clearly when GROQ_API_KEY is missing

Live tests (@pytest.mark.llm) make real Groq API calls.
Run with: pytest -m llm
They assert structural minimums only (non-empty string).
Quality is verified visually via: python apps/chatbot/demo.py
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from apps.chatbot.chatbot import (
    DEFAULT_QUESTION,
    ClaudeProvider,
    GroqProvider,
    LLMProvider,
    explain,
)
from lumberlex import NormalizationResult


# ── CapturingProvider ─────────────────────────────────────────────────────────


class CapturingProvider(LLMProvider):
    """Test double that records the messages list passed to chat().

    Returns a fixed response string so tests can assert on explain()'s
    return value independently of any real model output.
    """

    def __init__(self, response: str = "test response") -> None:
        self.captured: list[dict] | None = None
        self._response = response

    def chat(self, messages: list[dict]) -> str:
        self.captured = messages
        return self._response


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def spf_result() -> NormalizationResult:
    """High-confidence SPF match with no treatment."""
    return NormalizationResult(
        original_input="Whitewood Stud 2x4",
        cleaned_input="whitewood stud 2x4",
        normalized_name="SPF",
        species_group="Spruce-Pine-Fir",
        category="Dimensional framing lumber",
        ambiguity_level="High",
        treatment=None,
        detected_size="2x4",
        size_label="Thickness × Width",
        detected_seller=None,
        confidence=0.96,
        best_alias_match="whitewood stud",
        alternative_matches=[],
        manual_review_required=False,
        warning=None,
        explanation="Matched via alias 'whitewood stud' → SPF with high confidence.",
    )


@pytest.fixture
def treated_result() -> NormalizationResult:
    """High-confidence pressure-treated Southern Yellow Pine match."""
    return NormalizationResult(
        original_input="PT Southern Yellow Pine 2x6",
        cleaned_input="southern yellow pine 2x6",
        normalized_name="Pressure Treated Southern Yellow Pine",
        species_group="Southern Pine",
        category="Outdoor/ground-contact lumber",
        ambiguity_level="Medium",
        treatment="Pressure Treated",
        detected_size="2x6",
        size_label="Thickness × Width",
        detected_seller=None,
        confidence=0.91,
        best_alias_match="pt southern yellow pine",
        alternative_matches=[],
        manual_review_required=False,
        warning=None,
        explanation="Matched as pressure-treated Southern Yellow Pine.",
    )


@pytest.fixture
def unknown_result() -> NormalizationResult:
    """UNKNOWN outcome — no reliable match found."""
    return NormalizationResult(
        original_input="random board xyz qrs",
        cleaned_input="random board xyz qrs",
        normalized_name="UNKNOWN",
        species_group=None,
        category=None,
        ambiguity_level=None,
        treatment=None,
        detected_size=None,
        size_label=None,
        detected_seller=None,
        confidence=0.20,
        best_alias_match=None,
        alternative_matches=[],
        manual_review_required=True,
        warning=None,
        explanation=None,
    )


# ── Mocked tests ──────────────────────────────────────────────────────────────


class TestExplainReturnValue:
    def test_explain_returns_provider_response(self, spf_result):
        """explain() returns exactly what the provider's chat() returned."""
        provider = CapturingProvider(response="This is SPF lumber.")
        result = explain("Whitewood Stud 2x4", result=spf_result, provider=provider)
        assert result == "This is SPF lumber."


class TestNormalisationBehaviour:
    def test_explain_normalises_internally_when_result_is_none(self, spf_result):
        """normalize() is called once with raw when result=None."""
        provider = CapturingProvider()
        with patch("apps.chatbot.chatbot.normalize", return_value=spf_result) as mock_norm:
            explain("Whitewood Stud 2x4", provider=provider)
        mock_norm.assert_called_once_with("Whitewood Stud 2x4")

    def test_explain_skips_normalisation_when_result_provided(self, spf_result):
        """normalize() is not called when a result is passed in."""
        provider = CapturingProvider()
        with patch("apps.chatbot.chatbot.normalize") as mock_norm:
            explain("Whitewood Stud 2x4", result=spf_result, provider=provider)
        mock_norm.assert_not_called()


class TestSystemPromptConstruction:
    def test_system_prompt_contains_canonical_name(self, spf_result):
        """The canonical name from the result appears in the system message."""
        provider = CapturingProvider()
        explain("Whitewood Stud 2x4", result=spf_result, provider=provider)
        system_content = provider.captured[0]["content"]
        assert "SPF" in system_content

    def test_system_prompt_contains_treatment_when_set(self, treated_result):
        """Treatment field appears in system message when result.treatment is set."""
        provider = CapturingProvider()
        explain("PT Southern Yellow Pine 2x6", result=treated_result, provider=provider)
        system_content = provider.captured[0]["content"]
        assert "Pressure Treated" in system_content

    def test_system_prompt_contains_unknown_sentinel(self, unknown_result):
        """UNKNOWN appears in the system message for unmatched products."""
        provider = CapturingProvider()
        explain("random board xyz qrs", result=unknown_result, provider=provider)
        system_content = provider.captured[0]["content"]
        assert "UNKNOWN" in system_content

    def test_system_message_is_first_in_messages(self, spf_result):
        """The system message is always the first entry in the messages list."""
        provider = CapturingProvider()
        explain("Whitewood Stud 2x4", result=spf_result, provider=provider)
        assert provider.captured[0]["role"] == "system"


class TestUserMessage:
    def test_user_message_is_default_when_no_question(self, spf_result):
        """Last message uses DEFAULT_QUESTION when no question= is provided."""
        provider = CapturingProvider()
        explain("Whitewood Stud 2x4", result=spf_result, provider=provider)
        last_msg = provider.captured[-1]
        assert last_msg["role"] == "user"
        assert last_msg["content"] == DEFAULT_QUESTION

    def test_user_message_uses_provided_question(self, spf_result):
        """Last message content equals the question= string passed in."""
        provider = CapturingProvider()
        question = "Is this suitable for outdoor framing?"
        explain(
            "Whitewood Stud 2x4",
            result=spf_result,
            question=question,
            provider=provider,
        )
        last_msg = provider.captured[-1]
        assert last_msg["role"] == "user"
        assert last_msg["content"] == question


class TestHistoryHandling:
    def test_history_messages_appear_between_system_and_user(self, spf_result):
        """A 2-turn history produces [system, user1, assistant1, new_user] in order."""
        history = [
            {"role": "user",      "content": "First question"},
            {"role": "assistant", "content": "First answer"},
        ]
        provider = CapturingProvider()
        explain(
            "Whitewood Stud 2x4",
            result=spf_result,
            history=history,
            provider=provider,
        )
        msgs = provider.captured
        assert msgs[0]["role"] == "system"
        assert msgs[1] == {"role": "user",      "content": "First question"}
        assert msgs[2] == {"role": "assistant", "content": "First answer"}
        assert msgs[3]["role"] == "user"

    def test_system_messages_stripped_from_history(self, spf_result):
        """A history containing a system message does not produce a duplicate."""
        history = [
            {"role": "system",    "content": "Old system message — should be stripped"},
            {"role": "user",      "content": "A question"},
            {"role": "assistant", "content": "An answer"},
        ]
        provider = CapturingProvider()
        explain(
            "Whitewood Stud 2x4",
            result=spf_result,
            history=history,
            provider=provider,
        )
        msgs = provider.captured
        system_messages = [m for m in msgs if m["role"] == "system"]
        assert len(system_messages) == 1


class TestGroqProviderInit:
    def test_groq_provider_raises_on_missing_api_key(self, monkeypatch):
        """GroqProvider() raises EnvironmentError when GROQ_API_KEY is not set."""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="GROQ_API_KEY"):
            GroqProvider()


# ── Live tests ────────────────────────────────────────────────────────────────


@pytest.mark.llm
class TestLiveGroq:
    """Live integration tests against the real Groq API.

    Skipped by default. Run with:
        pytest -m llm -v

    Requires GROQ_API_KEY to be set in the environment. Tests that run
    without the key set are skipped with a clear message (not errored).

    These tests assert structural minimums only (non-empty string).
    Output quality is verified visually: python apps/chatbot/demo.py
    """

    @pytest.fixture(autouse=True)
    def require_groq_key(self):
        if not os.environ.get("GROQ_API_KEY"):
            pytest.skip("GROQ_API_KEY not set — skipping live Groq tests")

    def test_live_explain_returns_nonempty_string(self):
        """explain() returns a non-empty string for a high-confidence match."""
        response = explain("Whitewood Stud 2x4")
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_live_explain_unknown_returns_nonempty_string(self, unknown_result):
        """explain() returns a non-empty string when the result is UNKNOWN."""
        response = explain("random board xyz qrs", result=unknown_result)
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_live_explain_with_question_returns_nonempty_string(self):
        """explain() returns a non-empty string when a question= is provided."""
        response = explain(
            "PT Southern Yellow Pine 2x6",
            question="Is this safe for outdoor use?",
        )
        assert isinstance(response, str)
        assert len(response.strip()) > 0
