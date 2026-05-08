FROM python:3.11-slim-bookworm

WORKDIR /app

# Install dependencies sistem untuk psycopg2
RUN apt-get update -o APT::Update::Post-Invoke-Success="true" && \
    apt-get install -y --no-install-recommends libpq-dev gcc && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]