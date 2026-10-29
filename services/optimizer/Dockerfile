FROM medbal-py-base
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN uv pip install --system "ortools>=9.9"
COPY services/optimizer/ .
COPY contracts/fixtures/ /app/contracts/fixtures/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
