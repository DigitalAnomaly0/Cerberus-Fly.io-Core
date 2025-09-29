
#!/usr/bin/env python3
import json, pathlib, zipfile, sys
root = pathlib.Path(__file__).resolve().parents[1]
bundle = root/'deploy_bundle.zip'
need = [root/'gold'/'manifest.json', root/'config'/'run_status.json', root/'config'/'schema_versions.json', root/'reports'/'ui'/'report.json', root/'reports'/'ui'/'index.html']
missing = [str(p) for p in need if not p.exists()]
if missing: print("Missing:", missing, file=sys.stderr); sys.exit(2)
with zipfile.ZipFile(bundle, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for p in (root/'config').rglob('*'): z.write(p, p.relative_to(root))
    for p in (root/'gold').rglob('*'): z.write(p, p.relative_to(root))
    for p in (root/'reports'/'ui').rglob('*'): z.write(p, p.relative_to(root))
    if (root/'data_docs').exists():
        for p in (root/'data_docs').rglob('*'): z.write(p, p.relative_to(root))
print("Wrote", bundle)
