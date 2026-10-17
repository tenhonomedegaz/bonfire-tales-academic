"""Inventory the pinned redesign against the isolated Bonfire integration tree."""

import argparse
import ast
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path


SHARED = ("base", "header", "footer", "brand", "navigation", "responsive", "quick_access", "library_nav", "sidebar_support", "horizontal_support")
ACCOUNT = ("auth", "login", "register", "password", "perfil", "profile", "ficha", "character", "criador", "criacao", "editar", "levelup", "subir_nivel", "pathbuilder", "personagens", "slot", "opcoes", "options", "point_buy", "verificar_email", "hunter_")
MARKET = ("market", "mercado", "master", "mestre", "mission", "misso", "cronica", "chronicle", "jornal", "journal", "commerce", "cosmetic", "tema", "theme", "subscription", "colaborador", "conquista", "lenda", "negotiation", "oficina")
ADMIN = ("admin", "editor", "console", "db_access", "spell_import", "tag_library")


def tracked(root):
  raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
  return {item.decode("utf-8") for item in raw.split(b"\0") if item}


def digest(path):
  return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(path):
  lower = path.lower()
  name = Path(path).name.lower()
  if lower.startswith(("tests/", "home/js_tests/")) or name.startswith("test_"):
    return "S10", "validation", "none"
  if lower.startswith(("docs/", "design-review/", "ref/", ".github/")):
    return "S11", "documentation_or_reference", "none"
  if lower.startswith("home/migrations/") or lower.endswith(".py") or lower.startswith(("bonfire/", "scripts/")):
    return "S02", "backend_or_structure", "G01"
  if lower.startswith("home/data/") or lower.startswith("home/content_packages/") or lower.endswith((".json", ".csv", ".txt")):
    return "S02", "content_or_mechanics", "G01"
  if lower.startswith("home/templates/admin/") or "/admin/" in lower or any(key in name for key in ADMIN):
    return "S07", "admin_visual", "none"
  if lower.startswith("home/static/brand/") or lower.startswith("home/static/icons/") or lower.startswith("home/static/assets/"):
    return "S03", "shared_asset", "none"
  if lower.startswith("home/static/vendor/"):
    return "S03", "shared_vendor", "none"
  if lower.startswith("home/static/img/"):
    return "S04", "public_asset", "none"
  if any(key in name for key in SHARED) or lower.startswith("home/templates/home/components/"):
    return "S03", "shared_visual", "none"
  if any(key in name for key in ACCOUNT):
    return "S05", "account_visual", "none"
  if any(key in name for key in MARKET):
    return "S06", "commerce_community_visual", "none"
  if lower.startswith(("home/static/", "home/templates/")):
    return "S04", "public_visual", "none"
  return "S02", "other_review", "G01"


def routes(root, paths):
  result = []
  for filename in sorted(path for path in paths if path in {"home/urls.py", "bonfire/urls.py"}):
    tree = ast.parse((root / filename).read_text(encoding="utf-8-sig"), filename=filename)
    for node in ast.walk(tree):
      if not isinstance(node, ast.Call) or not isinstance(node.func, (ast.Name, ast.Attribute)):
        continue
      func = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
      if func not in {"path", "re_path"} or not node.args:
        continue
      pattern = ast.literal_eval(node.args[0]) if isinstance(node.args[0], ast.Constant) else ast.unparse(node.args[0])
      name = next((ast.literal_eval(k.value) for k in node.keywords if k.arg == "name" and isinstance(k.value, ast.Constant)), None)
      result.append({"file": filename, "pattern": pattern, "name": name, "view": ast.unparse(node.args[1]) if len(node.args) > 1 else None})
  return result


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--source", type=Path, required=True)
  parser.add_argument("--target", type=Path, default=Path(__file__).resolve().parents[1])
  parser.add_argument("--output", type=Path, default=Path("docs/integracao/redesign-s01-inventory.json"))
  args = parser.parse_args()
  source, target = args.source.resolve(), args.target.resolve()
  source_files, target_files = tracked(source), tracked(target)
  excluded = ("design-review/", "ref/", "tests/reference/", "docs/integracao/")
  rows = []
  for path in sorted(source_files):
    owner, category, gate = stage(path)
    source_hash = digest(source / path)
    target_hash = digest(target / path) if path in target_files else None
    rows.append({"source": path, "destination": None if path.startswith(excluded) else path,
                 "stage": owner, "category": category, "gate": gate,
                 "status": "same" if source_hash == target_hash else "different" if target_hash else "source_only",
                 "source_sha256": source_hash, "target_sha256": target_hash,
                 "disposition": "exclude_reference" if path.startswith(excluded) else "review_before_apply"})
  source_routes, target_routes = routes(source, source_files), routes(target, target_files)
  target_keys = {(r["file"], r["pattern"], r["name"]) for r in target_routes}
  for route in source_routes:
    route["status"] = "present" if (route["file"], route["pattern"], route["name"]) in target_keys else "source_only"
    route["stage"] = "S02" if route["status"] == "source_only" else "S09"
    route["gate"] = "G01" if route["status"] == "source_only" else "none"
  output = {"schema": 1, "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip(),
            "target_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=target, text=True).strip(),
            "exclusion_prefixes": list(excluded), "files": rows, "routes": source_routes,
            "target_only_files": sorted(target_files - source_files),
            "target_only_routes": [r for r in target_routes if (r["file"], r["pattern"], r["name"]) not in {(s["file"], s["pattern"], s["name"]) for s in source_routes}],
            "counts": {"source_files": len(source_files), "target_files": len(target_files),
                       "by_stage": dict(Counter(r["stage"] for r in rows)),
                       "by_status": dict(Counter(r["status"] for r in rows)),
                       "by_gate": dict(Counter(r["gate"] for r in rows)),
                       "source_routes": len(source_routes), "target_routes": len(target_routes)}}
  output_path = args.output if args.output.is_absolute() else target / args.output
  output_path.parent.mkdir(parents=True, exist_ok=True)
  output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  print(json.dumps(output["counts"], ensure_ascii=False))


if __name__ == "__main__":
  main()
