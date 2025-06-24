FROM python:3.11-slim AS build
WORKDIR /app

COPY docker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/local/bin /usr/local/bin

COPY . /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 3333 8100 5010
CMD ["python", "-m", "src.main"]