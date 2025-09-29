
import json, subprocess, sys, os, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

def run_cmd(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr

def main():
    # 1) Interface + reports + normalization tests
    rc, out, err = run_cmd([sys.executable, str(ROOT/'tests'/'contract_tests.py')])
    if rc != 0:
        print("contract_tests.py exited non-zero", file=sys.stderr)
    try:
        report = json.loads(out)
    except Exception:
        print("Failed to parse contract test JSON. Stdout snippet:", out[:500], file=sys.stderr)
        print("Stderr snippet:", err[:500], file=sys.stderr)
        sys.exit(1)

    failed = report.get("summary",{}).get("failed", 0)
    for t in report.get("tests", []):
        print(f"[{'PASS' if t['ok'] else 'FAIL'}] {t['name']}")
    if failed:
        print(f"Contract tests FAILED: {failed} failing subtests.", file=sys.stderr)
        sys.exit(2)

    # 2) Quick smoke to ensure we can produce an artifact end-to-end
    env = dict(os.environ)
    env.setdefault("SEARCH_PROVIDER", "dummy")
    p = subprocess.run([sys.executable, str(ROOT/'tests'/'quick_contract.py')], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        smoke = json.loads(p.stdout)
    except Exception:
        print("Smoke failed: could not parse quick_contract output", file=sys.stderr)
        print("Stdout:", p.stdout[:500], file=sys.stderr)
        print("Stderr:", p.stderr[:500], file=sys.stderr)
        sys.exit(3)
    if not smoke.get("passed"):
        print("Smoke FAILED", json.dumps(smoke, indent=2), file=sys.stderr)
        sys.exit(4)
    print("Smoke OK — artifact:", smoke.get("artifact_path"))
    sys.exit(0)

if __name__ == "__main__":
    main()
