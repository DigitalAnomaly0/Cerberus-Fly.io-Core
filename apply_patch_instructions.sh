#!/usr/bin/env bash
set -euo pipefail
PATCH_ZIP="$(basename "$0")"
# If script is extracted, user should run commands below manually.
# Instructions:
# 1) unzip -o repo_full_sync_patch_20250929T005624.zip -d ./
# 2) If you want to remove files that no longer exist in consolidated:
#    while IFS= read -r f; do [ -n "$f" ] && rm -f -- "$f"; done < DELETE_LIST.txt
# 3) Review, test, commit:
#    git status && git diff
#    make ci
#    git add -A && git commit -m "Full sync with consolidated (20250929T005624)"
#    git push
