"""P0 evidence collector: stdout JSON, Git reads and anonymous HTTP GET only.

No Django imports, settings/.env loading, database connection, checkout, fetch,
credentials, cookies, purchases, migrations or file writes. Rank media excluded.
"""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


SLUG = re.compile(r"^(tema|moldura|efeito|badge|titulo)-[a-z0-9-]+$")
RANK = re.compile(r"(?:^|[-/])(rank|elo)[-/]")
SAFE_FIELDS = ("slug", "tipo", "nome", "css_class", "origem", "ativo", "escopo",
               "raridade", "preco", "definicao_json")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0",
               GCM_INTERACTIVE="Never")
    try:
        result = subprocess.run(["git", "-c", "core.fsmonitor=false", *args],
                                cwd=repo, env=env, capture_output=True,
                                encoding="utf-8", errors="replace", timeout=25)
        # Do not export arbitrary credential-helper or remote error text.
        return {"ok": result.returncode == 0, "stdout": result.stdout.strip(),
                "exit_code": result.returncode}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": type(exc).__name__}


def literals(file):
    tree = ast.parse(file.read_text(encoding="utf-8-sig"))
    result = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result[target.id] = {"line": node.lineno, "value": value}
    return result


def slug_refs(value):
    found = set()
    if isinstance(value, str) and SLUG.fullmatch(value) and not RANK.search(value):
        found.add(value)
    elif isinstance(value, dict):
        for key, child in value.items():
            found.update(slug_refs(key))
            found.update(slug_refs(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(slug_refs(child))
    return found


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        value = attrs.get("href") if tag == "link" else attrs.get("src") if tag == "script" else None
        if value and urlsplit(value).path.endswith((".css", ".js")):
            self.assets.append(value)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get(url):
    try:
        request = Request(url, method="GET", headers={
            "User-Agent": "Bonfire-P0-readonly-reconciliation/1",
            "Accept-Encoding": "identity"})
        with build_opener(NoRedirect()).open(request, timeout=12) as response:
            body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                return {"url": url, "error": "response_over_4MiB"}, b""
            record = {"url": url, "status": response.status, "bytes": len(body),
                      "sha256": sha(body), "headers": {key: response.headers[key] for key in
                      ("Date", "ETag", "Last-Modified", "Cache-Control", "Age", "Content-Type", "Content-Encoding")
                      if response.headers.get(key)}}
            return record, body
    except HTTPError as exc:
        location = exc.headers.get("Location", "")
        # Login redirects are evidence of a gate, not an authenticated check.
        return {"url": url, "status": exc.code,
                "location": urlsplit(location).path or location[:100]}, b""
    except Exception as exc:
        return {"url": url, "error": type(exc).__name__}, b""


def collect(repo, origin, offline):
    static = repo / "home/static"
    draft_path = repo / "docs/cosmetics/catalog-draft.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    result = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "P0 only; source/files are not database state; hashes are not deployed Git SHA",
        "excluded": ["rank media and animations", "credentials/.env", "database queries/writes",
                     "authenticated flows", "sales activation", "art restoration"],
        "git": {"head": git(repo, "rev-parse", "HEAD"),
                "branch": git(repo, "branch", "--show-current"),
                "cached_origin_refs": git(repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/remotes/origin"),
                "tracked_changes": git(repo, "diff", "--name-only", "HEAD"),
                "origin_live_heads": {"not_checked": "offline"} if offline else
                git(repo, "ls-remote", "origin", "refs/heads/dev", "refs/heads/main", "refs/heads/master")},
        "database_state": {"local": "NOT_QUERIED", "production": "NOT_QUERIED",
                           "applied_migrations": "NOT_QUERIED", "inventory_offers_entitlements": "NOT_QUERIED"},
        "draft": {"source": str(draft_path.relative_to(repo)).replace("\\", "/"),
                  "sha256": sha(draft_path.read_bytes()),
                  "activate_in_production": draft.get("activate_in_production"),
                  "pending": draft.get("pending"),
                  "items": [{key: item[key] for key in SAFE_FIELDS if key in item}
                            for item in draft.get("items", [])]},
        "catalog_sources": [], "fixtures": [], "migrations": [], "manifests": [],
    }
    # Some draft revisions name the collection 'cosmetics'; preserve that shape.
    if not result["draft"]["items"]:
        for value in draft.values():
            if isinstance(value, list) and value and isinstance(value[0], dict) and "slug" in value[0]:
                result["draft"]["items"] = [{key: item[key] for key in SAFE_FIELDS if key in item} for item in value]
                break
    for file in sorted((repo / "home/migrations").glob("*.py")):
        text = file.read_text(encoding="utf-8-sig")
        if not ("TbCosmetico" in text or "tbcosmetico" in text or "Cosmetic" in text
                or "cosmetic" in file.name or "theme_pilot" in file.name):
            continue
        rel = file.relative_to(repo).as_posix()
        result["migrations"].append({"file": rel, "sha256": sha(file.read_bytes()), "applied": "NOT_QUERIED"})
        for name, definition in literals(file).items():
            refs = slug_refs(definition["value"])
            if file.name == "0048_seed_cosmeticos.py" and name == "COSMETICOS":
                refs.update(f"{row[1]}-{row[0]}" for row in definition["value"])
            if refs:
                result["catalog_sources"].append({"file": rel, "line": definition["line"],
                                                  "constant": name, "slug_references": sorted(refs)})
    pilot_file = repo / "home/management/commands/reconcile_redesign_d_pilot.py"
    pilot = literals(pilot_file)["PILOT"]
    result["pilot_source"] = {"file": pilot_file.relative_to(repo).as_posix(), "line": pilot["line"],
                              "slugs": ["tema-" + key for key in pilot["value"]],
                              "state": "source only; seed/archive commands NOT executed"}
    for file in sorted((repo / "home/fixtures").rglob("*.json")):
        try:
            source = file.read_text(encoding="utf-8-sig")
            parsed = json.loads(source)
            rows = parsed if isinstance(parsed, list) else []
            models = {}
            cosmetics = []
            for row in rows:
                if isinstance(row, dict) and "cosmet" in str(row.get("model", "")).lower():
                    model = row["model"]
                    models[model] = models.get(model, 0) + 1
                    if model.lower() == "home.tbcosmetico":
                        fields = row.get("fields", {})
                        item = {key: fields[key] for key in SAFE_FIELDS if key in fields}
                        match = re.search(r'"slug"\s*:\s*' + re.escape(json.dumps(fields.get("slug"))), source)
                        item["line"] = source[:match.start()].count("\n") + 1 if match else None
                        cosmetics.append(item)
            result["fixtures"].append({"file": file.relative_to(repo).as_posix(),
                                       "sha256": sha(file.read_bytes()), "cosmetic_model_row_counts": models,
                                       "cosmetic_catalog_rows": cosmetics,
                                       "slug_references": sorted(slug_refs(parsed))})
        except (ValueError, OSError) as exc:
            result["fixtures"].append({"file": file.relative_to(repo).as_posix(), "error": type(exc).__name__})
    for file in sorted((static / "cosmetics").glob("*.json")):
        if RANK.search(file.name):
            continue
        data = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(data.get("layers"), list) or not data.get("slug"):
            continue
        layers = []
        for layer in data.get("layers", []):
            asset = static / "cosmetics" / layer["file"]
            if RANK.search(asset.name):
                continue
            layers.append({"slot": layer["slot"], "file": layer["file"], "exists": asset.is_file(),
                           "sha256": sha(asset.read_bytes()) if asset.is_file() else None})
        result["manifests"].append({"slug": data.get("slug"), "file": file.relative_to(repo).as_posix(),
                                    "scope": data.get("scope"), "sha256": sha(file.read_bytes()), "layers": layers,
                                    "catalog_or_inventory_state": "NOT_PROVEN_BY_MANIFEST"})
    if offline:
        result["production"] = {"not_checked": "offline"}
        return result
    pages = []
    linked = {}
    for route in ("/perfil/Gaz/", "/perfil/", "/cosmeticos/", "/cosmeticos/eventos/"):
        evidence, body = get(origin + route)
        if route == "/perfil/Gaz/" and evidence.get("status") == 200:
            parser = References()
            parser.feed(body.decode("utf-8", errors="replace"))
            for value in parser.assets:
                url = urljoin(origin, value)
                if urlsplit(url).netloc == urlsplit(origin).netloc:
                    linked[urlsplit(url).path] = url
            evidence["css_js_references"] = sorted(linked.values())
        pages.append(evidence)
    paths = ["css/components/profile-effects.css", "css/components/profile-theme-motifs.css",
             "css/components/cosmetic-presentation.css", "css/components/cosmetic-catalog.css",
             "css/pages/cosmetic-shop.css", "js/profile-effects.js", "js/tema_swatch.js",
             "js/cosmetic-catalog.js", "cosmetics/renderer.js"]
    paths += ["cosmetics/" + Path(item["file"]).name for item in result["manifests"]]

    def compare(relative):
        path = "/static/" + relative
        url = linked.get(path, origin + path)
        evidence, body = get(url)
        file = static / relative
        local = file.read_bytes() if file.is_file() else None
        evidence.update({"local_file": file.relative_to(repo).as_posix(),
                         "local_sha256": sha(local) if local is not None else None,
                         "linked_from_public_sample": path in linked})
        evidence["same_bytes_as_local"] = (evidence.get("sha256") == evidence["local_sha256"]
                                                if evidence.get("status") == 200 else None)
        evidence["representation_relation"] = "NOT_COMPARED"
        if evidence.get("status") == 200 and local is not None:
            evidence["local_lf_sha256"] = sha(local.replace(b"\r\n", b"\n"))
            evidence["remote_lf_sha256"] = sha(body.replace(b"\r\n", b"\n"))
            if body == local:
                evidence["representation_relation"] = "IDENTICAL_BYTES"
            elif evidence["local_lf_sha256"] == evidence["remote_lf_sha256"]:
                evidence["representation_relation"] = "LINE_ENDINGS_ONLY"
            else:
                evidence["representation_relation"] = "DIFFERENT"
                if relative.endswith(".json"):
                    try:
                        if json.loads(body) == json.loads(local):
                            evidence["representation_relation"] = "JSON_EQUIVALENT"
                    except (ValueError, UnicodeError):
                        pass
        return evidence

    with ThreadPoolExecutor(max_workers=3) as executor:
        fingerprints = list(executor.map(compare, paths))
    result["production"] = {"origin": origin, "method": "anonymous GET; no redirects followed; identity encoding",
                            "pages": pages, "static_fingerprints": fingerprints,
                            "deployed_git_sha": "NOT_DETERMINED_BY_ASSET_HASHES"}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--origin", default="https://bonfiretales.com.br")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    parsed = urlsplit(args.origin)
    if (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        parser.error("--origin must be an HTTPS origin without credentials or path")
    print(json.dumps(collect(args.repo.resolve(), args.origin.rstrip("/"), args.offline),
                     indent=2, ensure_ascii=True))
