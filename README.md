# Cerberus Runner (Fly.io + GitHub Actions)

FastAPI runner that returns a base64 ZIP. Optional Gemini integration.

## Quick start
1) Set GitHub **Actions Secrets**: FLY_API_TOKEN, CERBERUS_API_KEY (and optionally REQUIRE_TIMESTAMP=false, GEMINI_API_KEY)
2) Set GitHub **Variables**: FLY_APP_NAME (e.g., fly-io-integration), FLY_PRIMARY_REGION=ord
3) Paste `actions/openapi.yaml` into your Custom GPT Action. Set `servers[0].url` to your Fly hostname.
4) Push to `main` or run the Deploy workflow.

## Endpoints
- GET /health
- POST /run (requires X-API-Key)
- GET /llm/gemini-test (requires X-API-Key)
- POST /run/gemini (requires X-API-Key)
- POST /debug/echo (no auth; temporary for troubleshooting)
