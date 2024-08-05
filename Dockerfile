FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY script.py .
COPY config.json .
COPY credentials.json .

EXPOSE 8080

CMD ["python", "script.py"]