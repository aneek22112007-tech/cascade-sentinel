FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LLM_PROVIDER=none

COPY pyproject.toml README.md ./
COPY sentinel ./sentinel
COPY static ./static
COPY tests ./tests

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "sentinel.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
