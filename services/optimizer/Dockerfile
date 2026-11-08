FROM medbal-py-base
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN uv pip install --system "ortools>=9.9" "networkx>=3.2" "qpiai-opt>=0.0.9" "qpiai-quantum>=0.7.5" "dwave-neal>=0.6" httpx
COPY services/optimizer/ .
COPY contracts/fixtures/ /app/contracts/fixtures/
RUN mkdir -p /app/evidence/qpiai_runs
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
