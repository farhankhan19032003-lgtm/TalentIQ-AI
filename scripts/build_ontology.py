"""Regenerate backend/app/data/skill_ontology.json from the human-editable source table.
Usage (PowerShell):  python scripts/build_ontology.py
You can also edit skill_ontology.json directly; this script is a convenience."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "backend" / "app" / "data"
src, out = DATA / "skill_ontology_source.txt", DATA / "skill_ontology.json"
skills = []
for ln in src.read_text(encoding="utf-8").splitlines():
    if not ln.strip() or ln.startswith("#"):
        continue
    p = ln.split("|")
    p += [""] * (6 - len(p))
    flags = p[4:]
    skills.append({"name": p[0], "category": p[1], "aliases": [a for a in p[2].split(";") if a],
                   "related": [r for r in p[3].split(";") if r],
                   "ambiguous": "ambiguous" in flags, "case_sensitive": "cs" in flags})
names = {s["name"] for s in skills}
for s in skills:
    for r in s["related"]:
        assert r in names, f"{s['name']} -> unknown related skill {r}"
doc = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"version": "1.0.0", "domains": []}
doc["skills"] = skills
out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
print(f"wrote {len(skills)} skills to {out}")
