import ast, sys, collections
with open('skills/flutter_tester.py', encoding='utf-8') as f:
    src = f.read()
lines = src.splitlines()
print(f"{len(lines)} lines total")
try:
    ast.parse(src)
    print("SYNTAX OK")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
    sys.exit(1)

old = [i+1 for i,l in enumerate(lines)
       if 'sync_playwright' in l or '_ensure_playwright' in l or 'import base64' in l]
print("Old remnants at lines:", old if old else "none")

defs = [l.strip() for l in lines if l.strip().startswith("def ")]
dupes = {k:v for k,v in collections.Counter(defs).items() if v > 1}
print("Duplicate defs:", dupes if dupes else "none")

for fn in ["_cli_bin","_ensure_cli","_run_cmd","_open_browser",
           "_find_flutter_url","_run_agent","_run","SKILL_MANIFEST"]:
    found = any(fn in l for l in lines)
    status = "OK" if found else "MISSING"
    print(f"  {fn}: {status}")
