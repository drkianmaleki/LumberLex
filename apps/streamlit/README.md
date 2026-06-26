# LumberLex — Streamlit UI

Interactive two-tab web interface for the LumberLex normalisation engine.

| Tab | What it does | API key required? |
|-----|-------------|-------------------|
| **🔍 Normalize** | Enter any raw lumber product string; see a structured result card | No |
| **💬 Chatbot** | Conversational Q&A grounded in the normalised result from Tab 1 | Yes — Groq |

---

## Setup

From the project root (one-time):

```bash
pip install -e .
pip install -r apps/streamlit/requirements.txt
```

Set your Groq API key (required for the Chatbot tab only):

```bash
# macOS / Linux
export GROQ_API_KEY=gsk_your_key_here

# Windows PowerShell — current session
$env:GROQ_API_KEY = "gsk_your_key_here"

# Windows PowerShell — permanent (restart terminal after)
[System.Environment]::SetEnvironmentVariable("GROQ_API_KEY", "gsk_...", "User")
```

Get a free key at: https://console.groq.com

---

## Run

```bash
streamlit run apps/streamlit/app.py
```

The app opens at `http://localhost:8501`.

---

## Usage

### Tab 1 — Normalize

1. Type or paste any raw product string into the input field.
2. Click **Normalize** (paste-then-click works; no Enter required first).
3. The result card shows:

| Field | Notes |
|-------|-------|
| Canonical name | Large heading; red if UNKNOWN |
| Ambiguity badge | Green = Low, Amber = Medium, Red = High |
| Species group / Category / Treatment | Teal pill when pressure treated |
| Detected size | With dimension label e.g. *Thickness × Width × Length* |
| Detected seller | Populated when a seller prefix is found |
| Confidence bar | Green ≥ 80%, Amber 60–79%, Red < 60% |
| Best alias | The alias string that drove the match |
| Warning box | Appears for High-ambiguity canonicals only |
| Manual review flag | Red banner for UNKNOWN; yellow banner for low-confidence known matches |
| Explanation | Natural-language trace of the match |
| Alternative matches | Expandable; shows runner-up candidates with scores |

Tab 1 is entirely offline. No API key or network call of any kind.

### Tab 2 — Chatbot

1. Normalize a product in Tab 1 first. The context banner confirms what is loaded.
2. Click **Get an explanation** to seed the chat with an initial summary.
3. Ask follow-up questions in the chat input below the messages container.
4. The conversation is multi-turn — each question is answered in context of all prior exchanges.
5. Click **Clear** to reset the chat for the current product.
6. Normalizing a new product in Tab 1 automatically resets the chat.

If `GROQ_API_KEY` is missing or invalid, an error banner appears in Tab 2 when
**Get an explanation** is clicked. Tab 1 is never affected.

---

## Architecture

```
apps/streamlit/app.py
│
├── _normalize_and_reset()      calls normalize() from the lumberlex library;
│                               wipes chat_history and chat_messages on each new product
├── _clear_chat()               on_click callback for the Clear button
├── _call_explain()             wraps explain(); catches EnvironmentError and Exception;
│                               renders st.error() and returns None on failure
│
├── render_result_card()        renders all 19 NormalizationResult fields in a
│                               bordered container with columns, badges, and progress bar
├── render_normalizer_tab()     Tab 1: st.form + result card
└── render_chatbot_tab()        Tab 2: context banner, "Get an explanation" gate,
                                fixed-height messages container, chat input
```

### Session state

| Key | Type | Purpose |
|-----|------|---------|
| `result` | `NormalizationResult \| None` | Latest normalisation output |
| `raw_input` | `str \| None` | Raw string that produced the result |
| `chat_history` | `list[dict]` | OpenAI-format history passed to `explain()`; includes the DEFAULT_QUESTION exchange as the first turn |
| `chat_messages` | `list[dict]` | Display log rendered by `st.chat_message()`; first entry is always the assistant's initial explanation (user never sees the DEFAULT_QUESTION) |

### Import strategy

The app imports from two places:

- `lumberlex` — pip-installed library (`pip install -e .`)
- `chatbot` — direct top-level import from `apps/chatbot/chatbot.py`, using
  `sys.path.insert(0, str(Path(__file__).parent.parent / "chatbot"))`. This is
  the same pattern used by `apps/chatbot/demo.py` and `apps/chatbot/chat.py`,
  validated in Phase 8.

### Streamlit patterns used

- `st.form()` — collects input value at submit time so paste-then-click works
- `st.button(on_click=callback)` — clears session state before the re-run (reliable alternative to `if button: ... st.rerun()`)
- `st.container(height=400)` — gives the messages area a fixed height so the chat input always appears at the same position directly below it
- `st.components.v1.html()` — injects a JS tab-switch on the "← Go to Normalize tab" button

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | Main Streamlit application — all UI logic |
| `requirements.txt` | `lumberlex` (editable install) + `streamlit` + `groq` |
| `README.md` | This file |
