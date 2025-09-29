
# Cerberus — Deploy & CI

This repo is already consolidated (no cross-repo imports). It includes:
- Contract tests + smoke (`tests/`, `Makefile`)
- Minimal FastAPI server exposing `POST /jobs/run`
- Dockerfile & Fly config

## Local
```bash
# Run contract tests + smoke
make ci

# Run API locally
pip install -r requirements.txt
uvicorn server.main:app --host 0.0.0.0 --port 8080
# health
curl http://127.0.0.1:8080/healthz
# run job
curl -sX POST http://127.0.0.1:8080/jobs/run -H 'content-type: application/json' -d '{"job_name":"core","args":{"topic":"Hello","n":5,"enable_research":true,"search_max":6,"fetch_max":0,"n_per_claim":2}}' | jq .
```

## GitHub Actions
On push/PR to `main` the CI runs contract tests and uploads the smoke artifact.
You can change the Python version or add more steps in `.github/workflows/ci.yml`.

## Fly.io
```bash
# One-time
flyctl apps create cerberus-app   # pick a unique name
flyctl launch --no-deploy         # uses fly.toml

# Build & deploy
flyctl deploy --remote-only

# Health
flyctl status
flyctl ips list
curl https://<your-app>.fly.dev/healthz
```
Configure search providers via env:
- `SEARCH_PROVIDER=dummy|serpapi|bing`
- `SERPAPI_KEY=...` (if serpapi)
- `BING_SUBSCRIPTION_KEY=...` and `BING_ENDPOINT=...` (if bing)

## Structure
```
/mnt/data/cerberus_consolidated_20250929T003511/
  core/ tools/ analytics/ jobs/ profiles/ schemas/ tests/
  server/              # FastAPI wrapper
  packager.py
  Dockerfile
  fly.toml
  requirements.txt
  .github/workflows/ci.yml
  Makefile
```


## Auth & request headers
The server checks these (if configured via Fly secrets):
- `X-API-Key`: must match Fly secret `CERBERUS_API_KEY` if set
- `X-Req-Ts`: required when `REQUIRE_TIMESTAMP` secret is truthy (`1/true/yes/on`), otherwise optional

### Example request with headers
```bash
curl -sX POST https://$FLY_APP_NAME.fly.dev/jobs/run       -H "content-type: application/json"       -H "X-API-Key: $CERBERUS_API_KEY"       -H "X-Req-Ts: $(date +%s)"       -d '{"job_name":"core","args":{"topic":"Hello","n":5,"enable_research":true,"search_max":6,"fetch_max":0,"n_per_claim":2}}'
```


### Timestamp freshness
The server enforces a timestamp freshness window when `REQUIRE_TIMESTAMP` is truthy.
- Configure the window via `TIMESTAMP_TTL_SEC` (default **600** seconds).
- A request is accepted only if `|now - X-Req-Ts| <= TIMESTAMP_TTL_SEC`.

**Example (10‑minute window):**
```bash
export TIMESTAMP_TTL_SEC=600
curl -sX POST https://$FLY_APP_NAME.fly.dev/jobs/run   -H "content-type: application/json"   -H "X-API-Key: $CERBERUS_API_KEY"   -H "X-Req-Ts: $(date +%s)"   -d '{"job_name":"core","args":{"topic":"Hello","n":5,"enable_research":true}}'
```
