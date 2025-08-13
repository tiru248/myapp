FROM python:3.10-slim

RUN apt-get update && \
    apt-get install -y libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
COPY packages /packages
RUN pip install --no-index --find-links=/packages -r requirements.txt


CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
