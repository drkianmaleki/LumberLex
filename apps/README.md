# LumberLex — Apps

This directory contains application-layer consumers of the `lumberlex` library.
Each app is independent and must be set up separately after the library is installed.

## Setup

Install the lumberlex library in editable mode from the project root first:

```bash
pip install -e .
```

Then install the specific app's dependencies:

```bash
# Chatbot module (Phase 8)
pip install -r apps/chatbot/requirements.txt

# Streamlit UI (Phase 9)
pip install -r apps/streamlit/requirements.txt
```

## Apps

| Directory | Phase | Description |
|-----------|-------|-------------|
| `chatbot/` | Phase 8 | Groq-powered explanation layer: `explain()` wraps `NormalizationResult` → plain-language answer |
| `streamlit/` | Phase 9 | Two-tab Streamlit UI wired to the lumberlex library and chatbot |
