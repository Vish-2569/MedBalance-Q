FROM medbal-py-base
WORKDIR /app
RUN uv pip install --system rapidfuzz python-multipart pyyaml httpx
COPY services/ingest_ai/ .
COPY contracts/fixtures/ /app/contracts/fixtures/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
