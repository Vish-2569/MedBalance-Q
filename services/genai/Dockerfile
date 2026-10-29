FROM medbal-py-base
WORKDIR /app
COPY services/genai/ .
COPY contracts/fixtures/ /app/contracts/fixtures/
COPY prompts/ /app/prompts/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
