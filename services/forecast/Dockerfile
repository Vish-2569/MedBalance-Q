FROM medbal-py-base
WORKDIR /app
COPY services/forecast/ .
COPY contracts/fixtures/ /app/contracts/fixtures/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
