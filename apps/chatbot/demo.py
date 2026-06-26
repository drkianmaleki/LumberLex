#!/usr/bin/env python3
"""
LumberLex Chatbot Demo
======================
Runs 4 sample inputs through the chatbot and prints the normalisation
result alongside the model's explanation.

Requires GROQ_API_KEY to be set in the environment.

Usage:
    python apps/chatbot/demo.py
"""
from __future__ import annotations

# chatbot.py lives in the same directory as this script (apps/chatbot/).
# Python adds the script's directory to sys.path automatically when running
# a script directly, so 'chatbot' is importable without any path manipulation.
from chatbot import explain

from lumberlex import normalize

# ── Terminal formatting ───────────────────────────────────────────────────────

_BOLD   = "\033[1m"
_CYAN   = "\033[96m"
_YELLOW = "\033[93m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"
_LINE   = "━" * 58


def _header(label: str) -> None:
    print(f"\n{_BOLD}{_CYAN}{_LINE}{_RESET}")
    print(f"{_BOLD}{label}{_RESET}")
    print(f"{_BOLD}{_CYAN}{_LINE}{_RESET}")


def _divider() -> None:
    print(f"{_DIM}{'-' * 58}{_RESET}")


def _print_sample(
    label: str,
    raw: str,
    question: str | None = None,
) -> None:
    result = normalize(raw)
    response = explain(raw, result=result, question=question)

    _header(label)
    print(f"  {_BOLD}Input:{_RESET}      {raw}")
    if question:
        print(f"  {_BOLD}Question:{_RESET}   {question}")
    _divider()
    print(f"  {_BOLD}Canonical:{_RESET}  {result.normalized_name}")
    print(f"  {_BOLD}Confidence:{_RESET} {result.confidence:.2f}")
    print(f"  {_BOLD}Treatment:{_RESET}  {result.treatment or '—'}")
    print(
        f"  {_BOLD}Review:{_RESET}     "
        f"{'⚠  Manual review recommended' if result.manual_review_required else '✓  Not required'}"
    )
    _divider()
    print(f"\n{_BOLD}{_YELLOW}Chatbot:{_RESET}")
    print(response)


def main() -> None:
    print(f"\n{_BOLD}LumberLex — Chatbot Demo{_RESET}")
    print(f"{_DIM}Provider: GroqProvider  Model: llama-3.1-8b-instant{_RESET}")

    # ── Sample 1: standard high-confidence match, no question ─────────────────
    _print_sample(
        label="Sample 1 — Standard explanation (SPF, high confidence)",
        raw="Whitewood Stud 2x4",
    )

    # ── Sample 2: pressure-treated product, no question ───────────────────────
    _print_sample(
        label="Sample 2 — Treatment present (Pressure Treated SYP)",
        raw="PT Southern Yellow Pine 2x6x16",
    )

    # ── Sample 3: specific user question ──────────────────────────────────────
    _print_sample(
        label="Sample 3 — User question (Douglas Fir-Larch)",
        raw="Douglas Fir-Larch 2x8",
        question="Is this suitable for outdoor framing?",
    )

    # ── Sample 4: UNKNOWN outcome — graceful uncertainty ──────────────────────
    _print_sample(
        label="Sample 4 — UNKNOWN outcome (unrecognised input)",
        raw="random board xyz qrs",
    )

    print(f"\n{_BOLD}{_CYAN}{_LINE}{_RESET}\n")


if __name__ == "__main__":
    main()
