
# Core → Service contracts

This repo emits a **GitHub Release asset** named `deploy_bundle.zip` with:
```
config/
  run_status.json
  schema_versions.json
gold/
  manifest.json
  dai_v1.parquet  # primary in CI
  dai_v1.csv      # optional fallback
reports/ui/
  index.html
  assets/style.css
  assets/app.js
  report.json
data_docs/ (optional)
```
Rules:
- `checks_green` in `config/run_status.json` must be `true` for prod deploys.
- `gold/manifest.json` is the source of truth for Gold artifact & version.
- The UI reads `report.json` (precomputed by `scripts/build_report_json.py`).
