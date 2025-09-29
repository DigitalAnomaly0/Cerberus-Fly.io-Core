
# Multi-stage optional; start simple
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PORT=8080     SEARCH_PROVIDER=dummy

WORKDIR /app

# System deps (add if we later need curl, build tools, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends     ca-certificates     && rm -rf /var/lib/apt/lists/*

# Copy code
COPY . /app

# Install server deps (tests do not rely on these)
RUN pip install --no-cache-dir -r requirements.txt

# Healthcheck (basic TCP)
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s CMD python -c "import socket,os; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', int(os.getenv('PORT','8080')))); print('OK')"

EXPOSE 8080

# Run the API
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080"]
