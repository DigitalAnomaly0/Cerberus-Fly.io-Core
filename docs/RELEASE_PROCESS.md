
# Release process (core → service)

## CI (Parquet primary)
1. `scripts/convert_to_parquet.py` converts CSV → Parquet (`gold/dai_v1.parquet`).
2. `scripts/update_manifest_to_parquet.py` sets `artifact` to `.parquet`.
3. `scripts/build_report_json.py` (now reads Parquet) writes `reports/ui/report.json`.
4. `scripts/package_deploy_bundle.py` creates `deploy_bundle.zip`.
5. GitHub Action uploads `deploy_bundle.zip` to the Release.

## Local (CSV fallback)
```bash
python scripts/build_report_json.py
python scripts/package_deploy_bundle.py
# outputs deploy_bundle.zip with CSV manifest
```
