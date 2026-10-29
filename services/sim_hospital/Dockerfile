FROM medbal-py-base
WORKDIR /app
COPY services/sim_hospital/ .
COPY contracts/fixtures/ /app/contracts/fixtures/
COPY data/seed/ /app/data/seed/
RUN uv pip install --system numpy
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8101"]
