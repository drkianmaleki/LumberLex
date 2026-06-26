#!/usr/bin/env python3
"""
LumberLex — Interactive Chatbot
================================
Type a lumber product string, ask questions, and keep the conversation
going. Type 'new' to start a fresh product, 'quit' to exit.

Usage:
    python apps/chatbot/chat.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from chatbot import explain
from lumberlex import normalize

_BOLD   = "\033[1m"
_CYAN   = "\033[96m"
_YELLOW = "\033[93m"
_GREEN  = "\033[92m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"
_LINE   = "━" * 58


def _show_result(raw: str) -> object:
    result = normalize(raw)
    print(f"\n{_DIM}{'-' * 58}{_RESET}")
    print(f"  {_BOLD}Canonical:{_RESET}  {result.normalized_name}")
    print(f"  {_BOLD}Confidence:{_RESET} {result.confidence:.2f}")
    print(f"  {_BOLD}Treatment:{_RESET}  {result.treatment or '—'}")
    print(f"  {_BOLD}Size:{_RESET}       {result.detected_size or '—'}")
    print(
        f"  {_BOLD}Review:{_RESET}     "
        f"{'⚠  Manual review recommended' if result.manual_review_required else '✓  Not required'}"
    )
    print(f"{_DIM}{'-' * 58}{_RESET}\n")
    return result


def main() -> None:
    print(f"\n{_BOLD}LumberLex — Interactive Chatbot{_RESET}")
    print(f"{_DIM}Commands: 'new' = new product  |  'quit' = exit{_RESET}")
    print(f"{_DIM}Leave question blank for a standard explanation.{_RESET}\n")

    while True:
        # ── Get product input ─────────────────────────────────────────────────
        print(f"{_BOLD}{_CYAN}{_LINE}{_RESET}")
        raw = input(f"{_BOLD}Product:{_RESET} ").strip()
        if not raw:
            continue
        if raw.lower() == "quit":
            print("\nGoodbye.\n")
            break

        result = _show_result(raw)
        history: list[dict] = []

        # ── Conversation loop for this product ────────────────────────────────
        while True:
            question_input = input(f"{_BOLD}Question{_DIM} (or Enter for explanation, 'new' to switch product){_RESET}: ").strip()

            if question_input.lower() == "quit":
                print("\nGoodbye.\n")
                sys.exit(0)

            if question_input.lower() == "new":
                print()
                break

            question = question_input if question_input else None

            response = explain(
                raw,
                result=result,
                question=question,
                history=history,
            )

            print(f"\n{_BOLD}{_YELLOW}Chatbot:{_RESET}")
            print(response)
            print()

            # Append this turn to history for multi-turn continuity
            user_msg = question if question else "Please explain this result."
            history.append({"role": "user",      "content": user_msg})
            history.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
