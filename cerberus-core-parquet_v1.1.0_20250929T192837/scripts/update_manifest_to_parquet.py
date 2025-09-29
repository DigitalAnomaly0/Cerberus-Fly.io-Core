
#!/usr/bin/env python3
import json, pathlib
root = pathlib.Path(__file__).resolve().parents[1]
mf = root/'gold'/'manifest.json'
d = json.loads(mf.read_text(encoding='utf-8'))
d['artifact'] = 'gold/dai_v1.parquet'
mf.write_text(json.dumps(d, indent=2), encoding='utf-8')
print('updated manifest to', d['artifact'])
