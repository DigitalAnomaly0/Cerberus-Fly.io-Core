Cerberus Repo Full Sync Patch — 20250929T005624

This patch aligns your GitHub repository with the consolidated project at /mnt/data/cerberus_current.

WHAT'S INCLUDED
- All files that differ or are missing in your repo are included at their relative paths.
- DELETE_LIST.txt enumerates files present in your repo but absent from the consolidated tree.
  (Zip cannot delete files; remove them using the command below if you want a perfect mirror.)

HOW TO APPLY (from your repo root)
1) Ensure a clean working tree:
   git status
2) Unpack patch:
   unzip -o repo_full_sync_patch_20250929T005624.zip -d ./
3) (Optional) Remove files not present in consolidated:
   while IFS= read -r f; do [ -n "$f" ] && rm -f -- "$f"; done < DELETE_LIST.txt
4) Review & test:
   git status && git diff
   make ci
5) Commit & push:
   git add -A && git commit -m "Full sync with consolidated (20250929T005624)" && git push
