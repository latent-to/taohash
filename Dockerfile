FROM debian:12-slim AS build
ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends -y \
      curl \
      python3-dev \
      pkg-config \
      libssl-dev \
      libffi-dev \
      ca-certificates \
      build-essential \
      gcc \
      g++ && \
    update-ca-certificates
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    /root/.local/bin/uv venv --seed /venv
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
ENV PATH="/root/.local/bin:/root/.cargo/bin:${PATH}"
COPY pyproject.toml .
COPY README.md .
COPY taohash/ ./taohash/
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv pip install . --link-mode=copy --python /venv/bin/python

FROM gcr.io/distroless/python3-debian12
COPY --from=build /venv /venv
COPY --from=build /taohash /app/taohash
WORKDIR /app
ENV PYTHONPATH=/app

ENTRYPOINT ["/venv/bin/python3", "-m", "taohash.validator.validator"]
