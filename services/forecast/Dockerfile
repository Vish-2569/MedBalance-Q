FROM medbal-py-base
WORKDIR /app
RUN uv pip install --system statsmodels "numpy>=1.26" httpx
COPY services/forecast/ .
COPY contracts/fixtures/ /app/contracts/fixtures/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
