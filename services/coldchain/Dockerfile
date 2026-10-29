FROM medbal-py-base
WORKDIR /app
COPY services/coldchain/ .
COPY contracts/fixtures/ /app/contracts/fixtures/
RUN uv pip install --system paho-mqtt
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8006"]
