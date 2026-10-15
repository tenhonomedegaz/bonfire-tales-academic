"""Link every baseline choice alert to its page source and a review case.

This is a QA index, not an application database or a parity verdict. Rebuild it
after the baseline is regenerated; previous role triage is reused only for the
same source PK, tag, and version.
"""

import collections
import gzip
import hashlib
import json
import re
import sqlite3
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "docs/qa/builder-page-parity-baseline-2026-10-13.jsonl.gz"
OLD_TRIAGE = ROOT / "scratch/builder-choice-role-triage-765-current.json"
OUTPUT = ROOT / "docs/qa/builder-release-triage-2026-10-13.sqlite3"


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def normalized(value):
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(char)
    ).strip()


def source_conflicts(db):
    fixture_path = ROOT / "home/fixtures/conteudo.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    features = {
        item["pk"]: item["fields"] for item in fixture
        if item["model"] == "home.tbclassehabilidade"
    }
    spells = {
        normalized(item["fields"]["nome_ingles"]): item for item in fixture
        if item["model"] == "home.tbmagia" and item["fields"].get("nome_ingles")
    }
    prose = features[1200]["descricao"]
    terrain_names = []
    mismatches = []
    for line in prose.splitlines():
        if line.startswith("##### Terrenos:"):
            terrain_names = [name.strip() for name in line.split(":", 1)[1].split(",")]
        if not (line.startswith("|") and re.match(r"\| (3|5|7|9)", line)):
            continue
        columns = [cell.strip() for cell in line.strip("|").split("|")]
        circle_match = re.match(r"\d+", columns[1])
        circle = int(circle_match.group()) if circle_match else 0
        for terrain, cell in zip(terrain_names, columns[2:]):
            english = re.findall(r"\[([^]]+)\](?!\()", cell)[-1]
            catalog = spells[normalized(english)]
            catalog_circle = catalog["fields"]["nivel"]
            if circle == catalog_circle:
                continue
            mismatches.append((terrain, circle, english, catalog_circle))
            db.execute(
                "INSERT INTO source_conflict VALUES (?,?,?,?,?,?,?,?)",
                (
                    f"terrain-{normalized(terrain)}-{normalized(english).replace(' ', '-')}",
                    "spell_circle_conflict", 1200, "live",
                    compact({"terrain": terrain, "circle": circle, "page_cell": cell}),
                    compact({"spell_pk": catalog["pk"], "catalog_name": catalog["fields"]["nome"],
                             "english_name": english, "catalog_circle": catalog_circle}),
                    "home/fixtures/conteudo.json: Magias do Terreno table and tbmagia catalog",
                    "PO must confirm which circle or spell is canonical; then correct source and retest.",
                ),
            )
    if len(mismatches) != 3:
        raise ValueError(f"Expected three unresolved terrain conflicts, found {mismatches!r}")
    totem = features[1024]["descricao"]
    if "Maiores" not in totem or re.search(r"^#{3,6} .*Maiores", totem, re.M):
        raise ValueError("Totemic editorial gap changed; inspect source before rebuilding")
    db.execute(
        "INSERT INTO source_conflict VALUES (?,?,?,?,?,?,?,?)",
        (
            "totemic-major-features", "missing_promised_option_list", 1024,
            "live and sealed:1,2,3,4,6,7",
            "Page prose promises a choice between Minor and Major features from Hunter level 6.",
            "Only the Minor list and its option tag are present; approved Major list was not found.",
            "home/fixtures/conteudo.json PK 1024; docs/hunter-release/inventory.json",
            "PO must provide approved Major features or approve a specific correction to the promise.",
        ),
    )


def main():
    old = json.loads(OLD_TRIAGE.read_text(encoding="utf-8"))
    roles = {
        (case["source_pk"], case["tag"], version): case["role"]
        for case in old["cases"]
        for version in case["versions"]
    }
    same_tag_roles = collections.defaultdict(set)
    for (source_pk, tag, _version), role in roles.items():
        same_tag_roles[(source_pk, tag)].add(role)
    baseline_hash = hashlib.sha256(BASELINE.read_bytes()).hexdigest()
    if OUTPUT.exists():
        OUTPUT.unlink()
    db = sqlite3.connect(OUTPUT)
    db.executescript(
        """
        PRAGMA foreign_keys=ON;
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE matrix_row (
            row_id INTEGER PRIMARY KEY, version TEXT NOT NULL,
            class_slug TEXT NOT NULL, subclass_slug TEXT, level INTEGER NOT NULL,
            baseline_status TEXT NOT NULL, checks_json TEXT NOT NULL,
            evidence_json TEXT NOT NULL
        );
        CREATE TABLE review_case (
            case_id TEXT PRIMARY KEY, version TEXT NOT NULL,
            source_pk INTEGER NOT NULL, source_title TEXT NOT NULL,
            choice_kind TEXT NOT NULL, source_tag TEXT NOT NULL,
            source_role TEXT NOT NULL, state TEXT NOT NULL,
            expected TEXT NOT NULL, observed TEXT NOT NULL,
            evidence TEXT NOT NULL, next_action TEXT NOT NULL
        );
        CREATE TABLE case_row (
            case_id TEXT NOT NULL REFERENCES review_case(case_id),
            row_id INTEGER NOT NULL REFERENCES matrix_row(row_id),
            observed_json TEXT NOT NULL, PRIMARY KEY (case_id, row_id)
        );
        CREATE TABLE source_conflict (
            conflict_id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_pk INTEGER NOT NULL,
            version TEXT NOT NULL, expected TEXT NOT NULL, observed TEXT NOT NULL,
            evidence TEXT NOT NULL, next_action TEXT NOT NULL
        );
        CREATE INDEX case_row_row ON case_row(row_id);
        CREATE INDEX case_source ON review_case(source_pk, version, choice_kind);
        CREATE VIEW residual_by_source AS
          SELECT source_pk, source_title, version, source_role, state,
                 COUNT(*) AS cases,
                 SUM((SELECT COUNT(*) FROM case_row cr
                      WHERE cr.case_id=review_case.case_id)) AS links
          FROM review_case
          GROUP BY source_pk, source_title, version, source_role, state;
        """
    )
    db.execute("INSERT INTO meta VALUES (?,?)", ("baseline_sha256", baseline_hash))
    db.execute("INSERT INTO meta VALUES (?,?)", ("baseline_path", str(BASELINE.relative_to(ROOT))))
    db.execute("INSERT INTO meta VALUES (?,?)", ("old_triage_path", str(OLD_TRIAGE.relative_to(ROOT))))
    case_ids = {}
    status_counts = collections.Counter()
    flags = 0
    with gzip.open(BASELINE, "rt", encoding="utf-8") as stream:
        for row_id, line in enumerate(stream, 1):
            row = json.loads(line)
            db.execute(
                "INSERT INTO matrix_row VALUES (?,?,?,?,?,?,?,?)",
                (
                    row_id, row["version"], row["class"], row["subclass"],
                    row["level"], row["status"], compact(row["checks"]),
                    compact(row["evidence"]),
                ),
            )
            status_counts[row["status"]] += 1
            if row["status"] != "choice_review":
                continue
            tags = row["expected"]["page_choice_tags"] + row["expected"]["page_entry_choice_tags"]
            for kind in row["choice_review_kinds"]:
                flags += 1
                matches = [tag for tag in tags if kind in tag["kinds"]]
                if not matches:
                    raise ValueError(f"Unlinked alert: row {row_id}, kind {kind}")
                observed = [
                    choice for choice in (
                        row["observed"]["builder_level_choices"]
                        + row["observed"]["builder_entry_choices"]
                    ) if choice["kind"] == kind
                ]
                for tag in matches:
                    identity = (row["version"], tag["source_id"], kind, tag["tag"])
                    if identity not in case_ids:
                        case_id = "src-%s-%s-%s" % (
                            tag["source_id"], row["version"].replace(":", "-"),
                            hashlib.sha256((kind + "\0" + tag["tag"]).encode()).hexdigest()[:12],
                        )
                        role = roles.get((tag["source_id"], tag["tag"], row["version"]))
                        if role:
                            state = "role_classified_qa_pending"
                            action = "Verify page prose, actual choice timing, UI and persistence; resolve any mismatch."
                        elif len(same_tag_roles[(tag["source_id"], tag["tag"])]) == 1:
                            role = "candidate:" + next(iter(same_tag_roles[(tag["source_id"], tag["tag"])]))
                            state = "legacy_prose_qa_pending"
                            action = "Confirm frozen page prose supports this candidate role, then compare builder and persistence."
                        else:
                            role = "unreviewed_source_role"
                            state = "source_review_pending"
                            action = "Classify source role from this version's page prose, then compare builder and persistence."
                        db.execute(
                            "INSERT INTO review_case VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                case_id, row["version"], tag["source_id"], tag["source"],
                                kind, tag["tag"], role, state,
                                "Page tag at level %s: %s" % (tag["level"], tag["tag"]),
                                "See case_row.observed_json for each level and path.",
                                "Baseline row IDs in case_row; old triage if role is classified or candidate.", action,
                            ),
                        )
                        case_ids[identity] = case_id
                    db.execute(
                        "INSERT OR REPLACE INTO case_row VALUES (?,?,?)",
                        (case_ids[identity], row_id, compact(observed)),
                    )
    source_conflicts(db)
    db.commit()
    total_links = db.execute("SELECT COUNT(*) FROM case_row").fetchone()[0]
    covered = db.execute("SELECT COUNT(DISTINCT row_id) FROM case_row").fetchone()[0]
    states = dict(db.execute("SELECT state, COUNT(*) FROM review_case GROUP BY state"))
    assert status_counts == {"matched_by_automated_audits": 7269, "choice_review": 6711}
    assert covered == status_counts["choice_review"]
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert db.execute("SELECT COUNT(*) FROM source_conflict").fetchone()[0] == 4
    print(compact({"rows": sum(status_counts.values()), "alerts": flags,
                   "linked_review_rows": covered, "case_links": total_links,
                   "cases": len(case_ids), "states": states,
                   "source_conflicts": 4, "sqlite": str(OUTPUT)}))
    db.close()


if __name__ == "__main__":
    main()
