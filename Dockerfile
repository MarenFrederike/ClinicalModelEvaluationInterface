FROM python:3.14-slim

WORKDIR /app

# Install Python dependencies first (layer is cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY data/ ./data/   

# data/ is mounted as a volume at runtime — just ensure the directory exists
RUN mkdir -p data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
