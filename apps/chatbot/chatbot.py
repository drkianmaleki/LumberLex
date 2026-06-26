"""
LumberLex Chatbot Module
========================
Wraps an LLM provider to return grounded natural-language explanations
of NormalizationResult objects produced by the lumberlex library.

The provider abstraction (LLMProvider) decouples the chatbot logic from
any specific LLM backend, making it straightforward to swap between Groq
(the default), Claude, or any future provider without changing calling code.

Usage
-----
    from apps.chatbot import explain

    # Minimal — normalises internally, uses GroqProvider()
    response = explain("Whitewood Stud 2x4")
    print(response)

    # With a pre-computed result (avoids double-normalisation)
    from lumberlex import normalize
    result = normalize("PT Southern Yellow Pine 2x6")
    response = explain("PT Southern Yellow Pine 2x6", result=result)

    # With a specific user question
    response = explain(
        "Douglas Fir-Larch 2x8",
        question="Is this suitable for outdoor framing?",
    )

    # Multi-turn — caller manages history across turns
    history: list[dict] = []
    r1 = explain("Whitewood Stud 2x4", history=history)
    history.append({"role": "user",      "content": "Whitewood Stud 2x4"})
    history.append({"role": "assistant", "content": r1})
    r2 = explain(
        "Whitewood Stud 2x4",
        question="Can I use this outdoors?",
        history=history,
    )

Environment
-----------
    GROQ_API_KEY   Required when using GroqProvider (the default).
                   Create a free account at https://console.groq.com,
                   generate a key, then: export GROQ_API_KEY=gsk_...
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from lumberlex import NormalizationResult, normalize

# ── Default user message when no question is provided ─────────────────────────

DEFAULT_QUESTION = (
    "Explain this lumber product normalisation result in plain, practical terms."
)


# ── Provider abstraction ──────────────────────────────────────────────────────


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All providers implement a single method: chat().
    The rest of the module interacts exclusively through this interface,
    keeping provider-specific SDK details fully contained in each subclass.
    """

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """Send a message list to the LLM and return the reply as a string.

        Args:
            messages: OpenAI-format message list, e.g.:
                [
                    {"role": "system",    "content": "..."},
                    {"role": "user",      "content": "..."},
                    {"role": "assistant", "content": "..."},
                ]

        Returns:
            The model's reply as a plain string.

        Raises:
            Any provider-specific exception on API or network error.
        """


class GroqProvider(LLMProvider):
    """LLM provider backed by the Groq API (https://console.groq.com).

    Uses the official ``groq`` Python client and the OpenAI-compatible chat
    completions endpoint. Reads GROQ_API_KEY from the environment unless an
    explicit api_key is passed.

    Default model: ``llama-3.1-8b-instant``
        Fast, instruction-following, well within the Groq free tier limits
        (14,400 requests/day). Suitable for structured explanation tasks.

    Setup (one time per collaborator):
        1. Create a free account at https://console.groq.com
        2. API Keys → Create API Key
        3. export GROQ_API_KEY=gsk_your_key_here
        4. pip install -r apps/chatbot/requirements.txt
    """

    DEFAULT_MODEL = "llama-3.1-8b-instant"
    DEFAULT_TEMPERATURE = 0.2   # Low: consistent, grounded output
    DEFAULT_MAX_TOKENS = 512    # Sufficient for a 2–4 sentence explanation

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        """Initialise the Groq provider.

        Args:
            model:       Groq model ID. Default: ``llama-3.1-8b-instant``.
            api_key:     Groq API key. If None, reads GROQ_API_KEY from env.
            temperature: Sampling temperature (0.0–1.0). Default 0.2 keeps
                         responses consistent and close to the provided data.
            max_tokens:  Maximum reply length in tokens. Default 512.

        Raises:
            EnvironmentError: if api_key is None and GROQ_API_KEY is not set.
            ImportError:      if the ``groq`` package is not installed.
        """
        resolved_key = api_key or os.environ.get("GROQ_API_KEY")
        if not resolved_key:
            raise EnvironmentError(
                "GROQ_API_KEY is not set.\n"
                "Create a free account at https://console.groq.com, generate\n"
                "an API key, then run:\n"
                "    export GROQ_API_KEY=gsk_your_key_here"
            )

        # Deferred import: allows the module to be imported (e.g. for mocked
        # tests) without requiring the groq package to be installed.
        try:
            from groq import Groq  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "The 'groq' package is required for GroqProvider.\n"
                "Run: pip install groq   (or: pip install -r apps/chatbot/requirements.txt)"
            ) from exc

        self._client = Groq(api_key=resolved_key)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def chat(self, messages: list[dict]) -> str:
        """Call Groq chat completions and return the assistant reply as a string."""
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        return completion.choices[0].message.content or ""


class ClaudeProvider(LLMProvider):
    """Stub for future Claude (Anthropic) integration.

    The LLMProvider abstraction means swapping in Claude requires only:
        1. Implementing chat() below using the anthropic SDK
        2. Setting ANTHROPIC_API_KEY in the environment
        3. Passing provider=ClaudeProvider() to explain()

    To activate after implementing:
        pip install anthropic
        export ANTHROPIC_API_KEY=sk-ant-...
        from apps.chatbot import explain, ClaudeProvider
        response = explain("Whitewood Stud 2x4", provider=ClaudeProvider())

    Implementation target: post-MVP.
    """

    def chat(self, messages: list[dict]) -> str:
        raise NotImplementedError(
            "ClaudeProvider is not yet implemented.\n"
            "See the class docstring for activation steps."
        )


# ── Prompt builders ───────────────────────────────────────────────────────────


def _build_system_prompt(result: NormalizationResult) -> str:
    """Construct the system prompt by injecting the full NormalizationResult.

    The complete JSON (all fields, including nulls) is injected so the model
    has accurate, unambiguous context. The strict rules block anchors the
    response to that data and prevents hallucination.
    """
    return (
        "You are a lumber product assistant for LumberLex, a product normalisation system.\n"
        "\n"
        "Your role is to explain a normalisation result to someone who may not be\n"
        "familiar with lumber industry terminology.\n"
        "\n"
        "STRICT RULES:\n"
        "1. Only use information contained in the JSON result below. Do not add species\n"
        '   characteristics, structural properties, pricing, regional availability, or\n'
        "   any other information not present in the result.\n"
        '2. If normalized_name is "UNKNOWN", tell the user the product could not be\n'
        "   matched and that manual review is recommended. Do not guess or suggest a\n"
        "   species name.\n"
        "3. If manual_review_required is true, mention it clearly.\n"
        "4. Keep responses concise: 2-4 sentences for a standard explanation; slightly\n"
        "   longer if a specific question is asked.\n"
        "5. Use plain language. Avoid jargon unless you immediately explain it.\n"
        "\n"
        "NORMALISATION RESULT:\n"
        f"{result.model_dump_json(indent=2)}"
    )


def _build_messages(
    system: str,
    user: str,
    history: list[dict] | None,
) -> list[dict]:
    """Assemble the full message list for the provider.

    Layout: [system_message, ...history_without_system_messages, new_user_message]

    Any system-role messages inside history are stripped to prevent the
    system prompt (which includes the NormalizationResult JSON) from appearing
    twice. The fresh system prompt is always injected at position 0.

    Args:
        system:  The system prompt string (built from the NormalizationResult).
        user:    The user's message for this turn.
        history: Prior conversation turns from the caller. May contain
                 user and assistant messages from previous turns.

    Returns:
        A list of OpenAI-format message dicts ready to pass to a provider.
    """
    messages: list[dict] = [{"role": "system", "content": system}]
    if history:
        messages.extend(m for m in history if m.get("role") != "system")
    messages.append({"role": "user", "content": user})
    return messages


# ── Public entry point ────────────────────────────────────────────────────────


def explain(
    raw: str,
    *,
    result: NormalizationResult | None = None,
    question: str | None = None,
    history: list[dict] | None = None,
    provider: LLMProvider | None = None,
) -> str:
    """Return a grounded natural-language explanation of a normalised lumber product.

    Args:
        raw:      Raw product string (e.g. ``"Whitewood Stud 2x4"``). Always
                  required. Used for normalisation if result is not provided.

        result:   Pre-computed NormalizationResult. If provided, normalisation
                  is skipped entirely. Pass this when the caller already has a
                  result (e.g. Streamlit Tab 1 → Tab 2 hand-off) to avoid
                  normalising the same input twice.

        question: Optional specific question from the user
                  (e.g. ``"Is this suitable for outdoor framing?"``).
                  If None, a standard explanation is requested instead.

        history:  Optional list of prior conversation turns in OpenAI format:
                  ``[{"role": "user"|"assistant", "content": str}, ...]``.
                  System messages in history are stripped automatically.
                  The caller is responsible for maintaining this list across
                  turns (e.g. stored in ``st.session_state`` in Streamlit).

        provider: LLMProvider instance to use. If None, a GroqProvider() is
                  instantiated using GROQ_API_KEY from the environment.
                  Override for testing (CapturingProvider) or provider swap-in
                  (ClaudeProvider once implemented).

    Returns:
        The model's reply as a plain string.

    Raises:
        EnvironmentError: if provider is None and GROQ_API_KEY is not set.
        ImportError:      if provider is None and the groq package is not installed.
    """
    if result is None:
        result = normalize(raw)

    if provider is None:
        provider = GroqProvider()

    system = _build_system_prompt(result)
    user = question if question is not None else DEFAULT_QUESTION
    messages = _build_messages(system, user, history)

    return provider.chat(messages)
