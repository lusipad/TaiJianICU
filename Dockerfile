FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . /app

RUN python -m pip install --upgrade pip \
    && python -m pip install -e .

EXPOSE 7860

CMD ["sh", "-c", "python -m uvicorn webapp.app:create_app --factory --host 0.0.0.0 --port ${PORT:-7860}"]
