FROM medbal-py-base
WORKDIR /app
COPY services/sensors/ .
RUN uv pip install --system paho-mqtt redis
CMD ["python", "-m", "app.main"]
