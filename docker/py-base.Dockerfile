FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY libs/medbal_common /tmp/medbal_common
RUN cd /tmp/medbal_common && uv pip install --system . && rm -rf /tmp/medbal_common
