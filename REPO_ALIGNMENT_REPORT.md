# Cerberus Repo Alignment Report
- Generated: 20250929T005321
- GitHub snapshot: `/mnt/data/github_repo_20250929T005321/Fly.io_Integration-main`
- Consolidated reference: `/mnt/data/cerberus_consolidated_20250929T003511`

## Summary
- Same files: **0**
- Different files: **3**
- Only in GitHub: **5**
- Only in Consolidated: **37**

## High-priority differences (important files)

### requirements.txt

```diff
--- github/requirements.txt

+++ consolidated/requirements.txt

@@ -1,5 +1,6 @@

-fastapi==0.115.0
-uvicorn[standard]==0.30.6
-pydantic==2.9.2
-starlette==0.38.5
-python-multipart==0.0.9
+
+fastapi>=0.112.0,<1.0.0
+uvicorn[standard]>=0.30.0,<1.0.0
+# Optional: enable real search providers in production by adding their SDKs here
+# azure-cognitiveservices-search-websearch
+# serpapi
```

### fly.toml

```diff
--- github/fly.toml

+++ consolidated/fly.toml

@@ -1,16 +1,20 @@

-app = "fly-io-integration"
-primary_region = "ord"
+
+# Fly.io config — update `app` to your unique app name before deploy
+app = "cerberus-skn-z9t6k1m2q7vp"
+primary_region = "dfw"
 
 [build]
   dockerfile = "Dockerfile"
 
 [env]
   PORT = "8080"
+  # SEARCH_PROVIDER can be 'dummy', 'serpapi', or 'bing'
+  SEARCH_PROVIDER = "dummy"
 
 [[services]]
-  protocol = "tcp"
   internal_port = 8080
   processes = ["app"]
+  protocol = "tcp"
 
   [[services.ports]]
     handlers = ["http"]
@@ -20,17 +24,7 @@

     handlers = ["tls", "http"]
     port = 443
 
-  [services.concurrency]
-    hard_limit = 50
-    soft_limit = 25
-
-  [[services.http_checks]]
-    interval = "10s"
-    timeout = "5s"
+  [[services.tcp_checks]]
+    interval = "30s"
+    timeout = "3s"
     grace_period = "30s"
-    method = "GET"
-    path = "/health"
-
-[[vm]]
-  size = "shared-cpu-1x"
-  memory = "512mb"
```

### Dockerfile

```diff
--- github/Dockerfile

+++ consolidated/Dockerfile

@@ -1,9 +1,24 @@

+
+# Multi-stage optional; start simple
 FROM python:3.11-slim
-ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
+
+ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PORT=8080     SEARCH_PROVIDER=dummy
+
 WORKDIR /app
-RUN apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates && rm -rf /var/lib/apt/lists/*
-COPY requirements.txt /app/
+
+# System deps (add if we later need curl, build tools, etc.)
+RUN apt-get update && apt-get install -y --no-install-recommends     ca-certificates     && rm -rf /var/lib/apt/lists/*
+
+# Copy code
+COPY . /app
+
+# Install server deps (tests do not rely on these)
 RUN pip install --no-cache-dir -r requirements.txt
-COPY app /app/app
+
+# Healthcheck (basic TCP)
+HEALTHCHECK --interval=30s --timeout=3s --start-period=20s CMD python -c "import socket,os; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', int(os.getenv('PORT','8080')))); print('OK')"
+
 EXPOSE 8080
-CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
+
+# Run the API
+CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080"]
```