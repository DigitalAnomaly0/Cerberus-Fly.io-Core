# Cerberus — Fly.io via GitHub Actions (ChatGPT + Gemini Ready)

Stateless Cerberus runner (in-memory ZIP → base64) with optional **Gemini API** integration. Deploys from **GitHub Actions**—no local CLI needed.

## What you get
- `/run` — build ZIP in memory, return as base64 (no storage)
- `/llm/gemini-test` — quick check that your **GEMINI_API_KEY** works
- `/run/gemini` — call Gemini to synthesize a payload, include response in the ZIP
- `actions/openapi.yaml` — for Custom GPT Actions
- `fly.toml` — preset **app = "cerberus"** (rename if taken)
- `.github/workflows/deploy.yml` — CI that deploys on push to `main`

## One-time GitHub setup
1) Create a new repo and upload these files.

2) Repo **Variables** (Settings → Secrets and variables → Variables):
   - `FLY_APP_NAME` = `cerberus`  (rename if unavailable globally)
   - `FLY_PRIMARY_REGION` = `ord` or `dfw`

3) Repo **Actions Secrets** (Settings → Secrets and variables → Actions):
   - `FLY_API_TOKEN` = Fly Personal Access Token
   - `CERBERUS_API_KEY` = your runner API key
   - *(optional)* `REQUIRE_TIMESTAMP` = `false` (to skip X-Timestamp)
   - *(optional)* `GEMINI_API_KEY` = your Gemini API key (enables Gemini endpoints)

4) Push to `main` (or run the workflow manually). The Action will patch `fly.toml`, create the app (if needed), set secrets, and deploy.

## Endpoints
- `GET /health` → { "status": "ok" }
- `POST /run` → returns `artifact.base64` (ZIP bytes)
- `GET /llm/gemini-test` → quick “ping” to Gemini (requires `GEMINI_API_KEY` secret)
- `POST /run/gemini` → body: `{ "prompt": "…", "model": "gemini-2.5-flash" }`

## Curl test (Linux/macOS)
```bash
now=$(date -u +"%s")
curl -sS https://<FLY_APP_NAME>.fly.dev/run   -H "Content-Type: application/json"   -H "X-API-Key: <CERBERUS_API_KEY>"   -H "X-Timestamp: $now"   -d '{"payload":{"message":"hello from Cerberus!"}}' | jq -r '.artifact.base64' | base64 -d > artifact.zip
unzip -l artifact.zip
```

> If `REQUIRE_TIMESTAMP=false`, omit `X-Timestamp`.

## Gemini usage
- Add `GEMINI_API_KEY` to **Actions Secrets** to enable.
- Quick check:
  ```bash
  curl -s https://<FLY_APP_NAME>.fly.dev/llm/gemini-test -H "X-API-Key: <CERBERUS_API_KEY>"
  ```
- Generate with Gemini then ZIP:
  ```bash
  curl -sS https://<FLY_APP_NAME>.fly.dev/run/gemini     -H "Content-Type: application/json"     -H "X-API-Key: <CERBERUS_API_KEY>"     -d '{"prompt":"Summarize Cerberus in one paragraph."}'   | jq -r '.artifact.base64' | base64 -d > gemini_artifact.zip
  unzip -l gemini_artifact.zip
  ```

---
Generated: 20250928T133857Z
