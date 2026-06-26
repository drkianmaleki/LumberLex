# LumberLex — Chatbot Module

Natural-language explanations of LumberLex normalisation results, powered
by the Groq API (Llama 3.1 8B Instant — free tier).

---

## Setup (one time per collaborator)

**1. Create a free Groq account**
Go to https://console.groq.com and sign up. No credit card required.

**2. Generate an API key**
Console → API Keys → Create API Key.

**3. Set the environment variable**

macOS / Linux:
```bash
export GROQ_API_KEY=gsk_your_key_here
```

Windows (PowerShell):
```powershell
$env:GROQ_API_KEY = "gsk_your_key_here"
```

To persist across sessions on Windows:
```powershell
[System.Environment]::SetEnvironmentVariable("GROQ_API_KEY", "gsk_your_key_here", "User")
```

**4. Install dependencies**
From the project root:
```bash
pip install -r apps/chatbot/requirements.txt
```

---

## Interactive chatbot

The fastest way to explore the chatbot. Enter any product string, ask
follow-up questions, and switch to a new product at any time.

```bash
python apps/chatbot/chat.py
```

**Session example:**

```
Product: Whitewood Stud 2x4
  Canonical:  SPF
  Confidence: 0.95
  Treatment:  —
  Size:       2x4
  Review:     ✓  Not required

Question (or Enter for explanation, 'new' to switch product):
Chatbot:
This is SPF (Spruce-Pine-Fir), a common framing lumber group...

Question: Can I use this outside?
Chatbot:
This product has no treatment applied, so it is not rated for...

Question: new

Product: PT Southern Yellow Pine 2x6
...
```

**Commands inside the session:**

| Input | Action |
|---|---|
| *(Enter)* | Standard explanation of the current product |
| Any question | Answered in context of the current product |
| `new` | Start a fresh product (clears conversation history) |
| `quit` | Exit |

Follow-up questions remember what was said earlier in the same product
session. Typing `new` resets the history.

---

## Fixed demo (4 samples)

Runs 4 pre-set inputs covering all code paths and prints the results.
Useful for a quick sanity check after setup.

```bash
python apps/chatbot/demo.py
```

Samples covered:
1. Standard explanation — SPF, high confidence, no question
2. Treatment present — Pressure Treated Southern Yellow Pine
3. User question — Douglas Fir-Larch with a specific question
4. UNKNOWN outcome — unrecognised input, graceful uncertainty

---

## Python API

Use `explain()` directly in your own code:

```python
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
```

---

## Run the tests

Mocked tests (no API key needed, always fast):
```bash
pytest tests/test_chatbot.py -m "not llm" -v
```

Live integration tests (requires `GROQ_API_KEY`):
```bash
pytest tests/test_chatbot.py -m llm -v
```

---

## Swapping in a different provider

The `LLMProvider` abstraction makes provider swap-in a one-liner:

```python
from apps.chatbot import explain, ClaudeProvider

# Once ClaudeProvider is implemented (see chatbot.py class docstring):
response = explain("Whitewood Stud 2x4", provider=ClaudeProvider())
```

See `ClaudeProvider` in `chatbot.py` for activation steps.

---

## Architecture

```
explain(raw, *, result, question, history, provider)
    │
    ├── normalize(raw)               ← lumberlex library (skipped if result= provided)
    │
    ├── _build_system_prompt(result) ← injects full NormalizationResult as JSON
    │
    ├── _build_messages(system, user, history)
    │       [system, ...history_turns, new_user_message]
    │
    └── provider.chat(messages)      ← LLMProvider (GroqProvider by default)
```

## Files

| File | Purpose |
|---|---|
| `chatbot.py` | Core module: `LLMProvider` ABC, `GroqProvider`, `ClaudeProvider` stub, `explain()` |
| `chat.py` | Interactive CLI — enter products and ask questions live |
| `demo.py` | Fixed demo — runs 4 pre-set samples |
| `requirements.txt` | Dependencies: `groq` + editable lumberlex install |
| `__init__.py` | Package exports: `explain`, `LLMProvider`, `GroqProvider`, `ClaudeProvider` |
