# Cerberus Runner — Full (Artifacts, Secured Echo)

FastAPI service for ChatGPT Actions. This build includes:
- `/run` returns a base64 ZIP artifact from your payload.
- Header alias fix: reads `X-API-Key` / `X-Timestamp`.
- `/debug/echo` (open) and `/debug/echo-secure` (requires API key) to verify headers from Actions.
- Relaxed Fly HTTP checks to avoid startup flaps.

## Deploy
- Secrets: `CERBERUS_API_KEY`, `REQUIRE_TIMESTAMP=false` (optional)
- Variables: `FLY_APP_NAME`, `FLY_PRIMARY_REGION`
- Action Schema: use `actions/openapi.yaml`, set `servers[0].url` to your Fly hostname.
- Action Auth: API Key = the same value as `CERBERUS_API_KEY`.
