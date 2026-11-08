FROM medbal-py-base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 libffi-dev shared-mime-info fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*
RUN uv pip install --system jinja2 pyyaml "google-genai>=1.0.0" redis weasyprint qrcode httpx
COPY services/genai/ .
COPY contracts/fixtures/ /app/contracts/fixtures/
COPY prompts/ /app/prompts/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
