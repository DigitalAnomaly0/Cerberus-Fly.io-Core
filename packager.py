
import io, json, hashlib, datetime, base64, zipfile, re

def _slugify(s):
    s = s.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s or "job"

def _sha256_bytes(b):
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def _canon_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))

def build_run_id(job_name, args):
    ts = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    basis = (str(job_name) + ':' + _canon_json(args or {})).encode('utf-8')
    short = _sha256_bytes(basis)[:12]
    return 'RID-' + ts + '-' + short

def build_index_html(meta):
    css = "body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.5;margin:2rem;} .card{border:1px solid #e5e7eb;border-radius:12px;padding:1rem;margin:1rem 0;box-shadow:0 1px 3px rgba(0,0,0,0.05);} pre{white-space:pre-wrap}"
    title = "Cerberus Artifact Viewer - " + str(meta.get("run_id"))
    html = (
        "<!doctype html><html><head><meta charset='utf-8'/>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
        "<title>" + title + "</title>"
        "<style>" + css + "</style></head><body>"
        "<h1>Cerberus Artifact Viewer</h1>"
        "<div class='card'><h2>Run</h2><pre>" + json.dumps(meta, indent=2) + "</pre></div>"
        "<div class='card'><h2>Notes</h2><p>This package is produced by Cerberus. Files include sizes and SHA-256 hashes for integrity.</p></div>"
        "</body></html>"
    )
    return html.encode('utf-8')

def pack(job_name, args, extra_files=None, meta_extra=None):
    job_slug = _slugify(job_name)
    run_id = build_run_id(job_name, args or {})
    created_at = datetime.datetime.utcnow().isoformat() + "Z"

    files = {}
    args_bytes = _canon_json(args or {}).encode('utf-8')
    files["data/args.json"] = args_bytes

    meta = {
        "run_id": run_id,
        "job_name": job_name,
        "job_slug": job_slug,
        "created_at": created_at,
        "args_sha256": _sha256_bytes(args_bytes),
        "version": "1.0.0"
    }
    if meta_extra:
        for k, v in meta_extra.items():
            meta[k] = v

    files["index.html"] = build_index_html(meta)

    if extra_files:
        for path, b in extra_files.items():
            files[path] = b

    manifest = {"run_id": run_id, "job_name": job_name, "created_at": created_at, "files": []}
    for path, b in files.items():
        manifest["files"].append({"path": path, "size_bytes": len(b), "sha256": _sha256_bytes(b)})
    manifest_bytes = json.dumps(manifest, indent=2).encode('utf-8')
    files["manifest.json"] = manifest_bytes

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, b in files.items():
            zf.writestr(path, b)
    zip_bytes = zbuf.getvalue()

    short = _sha256_bytes(zip_bytes)[:12]
    filename = "cerberus_" + job_slug + "--" + run_id + "--sha256-" + short + ".zip"

    return {"filename": filename, "zip_bytes": zip_bytes, "manifest": manifest}
