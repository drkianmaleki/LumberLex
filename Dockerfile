# LumberLex — Streamlit web UI container
#
# Mirrors the tested local install sequence from the README Quick Start:
#   pip install -e .
#   pip install -r requirements.txt
#   pip install -r apps/streamlit/requirements.txt
#   streamlit run apps/streamlit/app.py

FROM python:3.11-slim

WORKDIR /app

# Install the library first (better layer caching — this changes less
# often than app code, so Docker can reuse this layer across rebuilds).
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .

# Dev + Streamlit-specific dependencies
COPY requirements.txt ./
COPY apps/streamlit/requirements.txt ./apps/streamlit/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r apps/streamlit/requirements.txt

# Now bring in everything else (app code, config, data, tests)
COPY . .

EXPOSE 8501

# --server.address=0.0.0.0 : listen on all interfaces (required in a container)
# --server.headless=true   : don't try to open a local browser
CMD ["streamlit", "run", "apps/streamlit/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
