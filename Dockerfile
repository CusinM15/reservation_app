FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001
EXPOSE 8443

COPY scripts/generate_certs.sh /app/scripts/generate_certs.sh
RUN chmod +x /app/scripts/generate_certs.sh

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
