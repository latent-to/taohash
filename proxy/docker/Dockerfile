FROM python:3.11-slim AS build
WORKDIR /app

COPY docker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

# Install curl for ClickHouse health check and required network tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl iputils-ping iproute2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 3331 5000 5001
CMD ["python", "-m", "src"]