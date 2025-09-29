#!/usr/bin/env bash
set -euo pipefail
# Local build (CSV primary, for environments without pyarrow/pandas)
python scripts/build_report_json.py
python scripts/package_deploy_bundle.py
echo "Bundle ready: deploy_bundle.zip (CSV primary)"
