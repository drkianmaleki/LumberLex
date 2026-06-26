"""LumberLex — Streamlit UI (Phase 9).

Two-tab interface:
  Tab 1 — Normalize: enter a raw product string; see a structured results card.
  Tab 2 — Chatbot: conversational Q&A grounded in the normalised result.

Run from the project root:
    streamlit run apps/streamlit/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add apps/chatbot/ to sys.path so 'chatbot' is importable as a top-level
# module — same pattern as apps/chatbot/demo.py and apps/chatbot/chat.py.
sys.path.insert(0, str(Path(__file__).parent.parent / "chatbot"))

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402
from lumberlex import normalize, NormalizationResult  # noqa: E402
from chatbot import explain  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Page configuration
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="LumberLex",
    page_icon="🪵",
    layout="centered",
)

# ─────────────────────────────────────────────────────────────────────────────
# Session-state initialisation
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULTS: dict = {
    "result": None,       # NormalizationResult | None
    "raw_input": None,    # str | None — string that produced the result
    "chat_history": [],   # list[dict] — OpenAI-format history passed to explain()
    "chat_messages": [],  # list[dict] — display log: [{role, content}, ...]
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _confidence_color(c: float) -> str:
    """Return a CSS hex color for a confidence value (green / amber / red)."""
    if c >= 0.80:
        return "#3B6D11"
    if c >= 0.60:
        return "#854F0B"
    return "#A32D2D"


def _ambiguity_badge_html(level: str | None) -> str:
    """Return an inline HTML pill for an ambiguity level, or empty string."""
    if level is None:
        return ""
    palette = {
        "Low":    ("#EAF3DE", "#3B6D11"),
        "Medium": ("#FAEEDA", "#854F0B"),
        "High":   ("#FCEBEB", "#A32D2D"),
    }
    bg, fg = palette.get(level, ("#F1EFE8", "#5F5E5A"))
    return (
        f'<span style="background:{bg};color:{fg};font-size:12px;font-weight:500;'
        f'padding:4px 12px;border-radius:20px;white-space:nowrap;">'
        f"{level} ambiguity</span>"
    )


def _normalize_and_reset(raw: str) -> None:
    """Run normalization, store result, and wipe chat state for the new product."""
    result = normalize(raw)
    st.session_state["result"] = result
    st.session_state["raw_input"] = raw
    st.session_state["chat_history"] = []
    st.session_state["chat_messages"] = []


def _clear_chat() -> None:
    """on_click callback for the Clear button.

    Runs before the next re-run, so session state is already clean when
    the page re-renders. No explicit st.rerun() required.
    """
    st.session_state["chat_history"] = []
    st.session_state["chat_messages"] = []


def _call_explain(
    *,
    raw: str,
    result: NormalizationResult,
    question: str | None = None,
    history: list[dict] | None = None,
) -> str | None:
    """Call explain() and return the answer, or render an error and return None."""
    try:
        return explain(raw, result=result, question=question, history=history)
    except EnvironmentError as exc:
        st.error(
            f"{exc}\n\n"
            "Set the `GROQ_API_KEY` environment variable to enable the chatbot.",
            icon="🔑",
        )
        return None
    except Exception as exc:
        st.error(f"An error occurred: {exc}", icon="⚠️")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Results card
# ─────────────────────────────────────────────────────────────────────────────


def render_result_card(result: NormalizationResult) -> None:
    """Render all NormalizationResult fields as a structured card."""
    is_unknown = result.normalized_name == "UNKNOWN"

    with st.container(border=True):

        # ── Header: canonical name + ambiguity badge ──────────────────────────
        col_name, col_badge = st.columns([3, 1])
        with col_name:
            st.caption("canonical name")
            name_color = "#A32D2D" if is_unknown else "inherit"
            st.markdown(
                f'<p style="font-size:24px;font-weight:500;margin:0;color:{name_color};">'
                f"{result.normalized_name}</p>",
                unsafe_allow_html=True,
            )
        with col_badge:
            badge = _ambiguity_badge_html(result.ambiguity_level)
            if badge:
                st.markdown(
                    f'<div style="padding-top:18px;">{badge}</div>',
                    unsafe_allow_html=True,
                )

        st.divider()

        # ── Metadata: species group / category / treatment ────────────────────
        if not is_unknown:
            m1, m2, m3 = st.columns(3)
            with m1:
                st.caption("Species group")
                st.write(result.species_group or "—")
            with m2:
                st.caption("Category")
                st.write(result.category or "—")
            with m3:
                st.caption("Treatment")
                if result.treatment:
                    st.markdown(
                        '<span style="background:#E1F5EE;color:#0F6E56;font-size:13px;'
                        'font-weight:500;padding:3px 10px;border-radius:20px;">'
                        f"{result.treatment}</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.write("—")

            # ── Size + seller ─────────────────────────────────────────────────
            s1, s2 = st.columns(2)
            with s1:
                st.caption("Detected size")
                if result.detected_size:
                    label = f" *{result.size_label}*" if result.size_label else ""
                    st.write(f"`{result.detected_size}`{label}")
                else:
                    st.write("—")
            with s2:
                st.caption("Detected seller")
                st.write(result.detected_seller or "—")

        # ── Confidence bar ────────────────────────────────────────────────────
        pct = int(result.confidence * 100)
        c1, c2 = st.columns([5, 1])
        with c1:
            st.caption("Confidence")
            st.progress(result.confidence)
        with c2:
            st.markdown(
                f'<p style="font-size:18px;font-weight:500;margin-top:18px;'
                f'color:{_confidence_color(result.confidence)};">{pct}%</p>',
                unsafe_allow_html=True,
            )

        if result.best_alias_match:
            st.caption(f"Best alias: `{result.best_alias_match}`")

        # ── Warnings and review flag ──────────────────────────────────────────
        if result.warning:
            st.warning(result.warning, icon="⚠️")

        if result.manual_review_required:
            if is_unknown:
                st.error(
                    "This product could not be matched. Manual review recommended.",
                    icon="🔴",
                )
            else:
                st.warning(
                    "Confidence is below the threshold. Manual review recommended.",
                    icon="🟡",
                )

        # ── Explanation ───────────────────────────────────────────────────────
        if result.explanation:
            st.divider()
            st.caption("Explanation")
            st.write(result.explanation)

        # ── Alternative matches (collapsible) ─────────────────────────────────
        if result.alternative_matches:
            with st.expander(
                f"Alternative matches ({len(result.alternative_matches)})"
            ):
                for alt in result.alternative_matches:
                    st.write(
                        f"**{alt.canonical_name}** via `{alt.alias}` "
                        f"— score {int(alt.score)}"
                    )


# ─────────────────────────────────────────────────────────────────────────────
# Tab 1 — Normalizer
# ─────────────────────────────────────────────────────────────────────────────


def render_normalizer_tab() -> None:
    # st.form collects the input value at submit time, so paste-then-click
    # works correctly without requiring a prior Enter keypress.
    with st.form("normalize_form"):
        raw = st.text_input(
            "Product name",
            placeholder="e.g. Lowes Whitewood Stud 2x4",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Normalize", type="primary")

    if submitted and raw.strip():
        with st.spinner("Normalizing…"):
            _normalize_and_reset(raw.strip())

    result: NormalizationResult | None = st.session_state["result"]
    if result is not None:
        render_result_card(result)
    else:
        st.caption("Enter a product name above to see the normalised result.")


# ─────────────────────────────────────────────────────────────────────────────
# Tab 2 — Chatbot
# ─────────────────────────────────────────────────────────────────────────────


def render_chatbot_tab() -> None:
    result: NormalizationResult | None = st.session_state["result"]

    # ── No result yet ─────────────────────────────────────────────────────────
    if result is None:
        st.info(
            "Normalize a product in the **Normalize** tab first "
            "to give the chatbot context.",
            icon="ℹ️",
        )
        # Attempt a JS-driven tab switch. Streamlit renders tab buttons with
        # data-testid="stTab" in the parent document. A 100ms delay lets the
        # DOM settle after the re-run before the click fires.
        if st.button("← Go to Normalize tab", type="primary", key="go_to_norm"):
            components.html(
                """
                <script>
                setTimeout(function () {
                    var tabs = window.parent.document
                        .querySelectorAll('[data-testid="stTab"]');
                    if (tabs.length > 0) { tabs[0].click(); }
                }, 100);
                </script>
                """,
                height=0,
            )
        return

    # ── Context banner ────────────────────────────────────────────────────────
    size_part = f" · {result.detected_size}" if result.detected_size else ""
    col_ctx, col_clear = st.columns([5, 1])
    with col_ctx:
        st.markdown(f"**Context:** {result.normalized_name}{size_part}")
    with col_clear:
        # on_click callback clears session state before the next re-run;
        # no explicit st.rerun() required.
        st.button("Clear", key="clear_chat", on_click=_clear_chat)

    # ── Uninitialised: show "Get an explanation" button ───────────────────────
    if not st.session_state["chat_messages"]:
        if st.button("Get an explanation", type="primary", key="init_chat"):
            with st.spinner("Thinking…"):
                initial = _call_explain(
                    raw=st.session_state["raw_input"],
                    result=result,
                )
            if initial is None:
                return
            # Seed chat_history with the full exchange so the LLM has context
            # for follow-up questions. Only the assistant message goes into
            # chat_messages — the user never typed the default question.
            st.session_state["chat_history"].extend([
                {"role": "user",      "content": "Explain this lumber product in plain language."},
                {"role": "assistant", "content": initial},
            ])
            st.session_state["chat_messages"].append(
                {"role": "assistant", "content": initial}
            )
            st.rerun()
        return  # hide chat input until the first explanation is seeded

    # ── Fixed-height scrollable messages area ─────────────────────────────────
    # st.container(height=N) gives the messages region a stable size so the
    # chat input always appears directly below it at the same position,
    # regardless of how many messages have accumulated.
    with st.container(height=400):
        for msg in st.session_state["chat_messages"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    # ── Chat input — always directly below the messages container ─────────────
    question = st.chat_input("Ask a question about this product…")
    if not question:
        return

    # Call explain() before re-rendering; spinner appears below the container.
    with st.spinner("Thinking…"):
        answer = _call_explain(
            raw=st.session_state["raw_input"],
            result=result,
            question=question,
            history=st.session_state["chat_history"] or None,
        )

    if answer is None:
        return  # error already rendered by _call_explain

    # Persist the exchange then re-render so both messages appear inside the
    # scrollable container on the next run rather than below it.
    st.session_state["chat_history"].extend([
        {"role": "user",      "content": question},
        {"role": "assistant", "content": answer},
    ])
    st.session_state["chat_messages"].extend([
        {"role": "user",      "content": question},
        {"role": "assistant", "content": answer},
    ])
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    st.title("LumberLex")
    st.caption("Lumber product normalizer")

    tab_norm, tab_chat = st.tabs(["🔍  Normalize", "💬  Chatbot"])
    with tab_norm:
        render_normalizer_tab()
    with tab_chat:
        render_chatbot_tab()


if __name__ == "__main__":
    main()
