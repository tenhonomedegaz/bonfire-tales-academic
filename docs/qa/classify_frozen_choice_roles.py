"""Classify sealed-source choice alerts against actual frozen page prose.

Reads PostgreSQL revisions without changing them. Only the local QA index is
updated; classification is not builder parity or an in-play mechanics verdict.
"""

import hashlib
import collections
import os
import sqlite3
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bonfire.settings")
import django  # noqa: E402

django.setup()

from home.models import TbClasse, TbClassehabilidade, TbRuleset  # noqa: E402
from home.versioned_classes import VersionedClassCatalog  # noqa: E402


QA_DB = Path(__file__).with_name("builder-release-triage-2026-10-13.sqlite3")

# Every phrase is checked in every frozen revision before assigning its role.
ROLES = {
    884: ("persistent_level_choice", "escolha de inimigo"),
    934: ("persistent_work_reconfiguration", "pode escolher **dois nucleos**"),
    1024: ("persistent_choice_editorial_gap", "caracteristicas maiores"),
    1072: ("persistent_rest_preparation", "pode preparar ate **2 magias**"),
    1200: ("persistent_rest_attunement", "escolha um tipo de terreno"),
    1236: ("persistent_dual_attunement", "dois terrenos"),
    1512: ("persistent_level_choice", "escolha um elemento inicial"),
    1529: ("persistent_rest_attunement", "sintoniza sua alma ao aspecto"),
    1530: ("persistent_rest_attunement", "pode meditar e escolher um novo pilar"),
    1582: ("activation_tag_prose_gap", "ao dar o salto, escolha qualquer numero de criaturas"),
    1974: ("persistent_rest_reconfiguration", "pode alterar ao final de um descanso longo"),
    1977: ("persistent_rest_reconfiguration", "pode trocar a arma escolhida por outra"),
}


def plain(text):
    return "".join(
        char for char in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(char)
    )


def main():
    with sqlite3.connect(QA_DB) as db:
        cases = db.execute(
            """SELECT c.case_id, c.source_pk, c.version, c.source_tag,
                      MIN(m.class_slug)
               FROM review_case c
               JOIN case_row cr ON cr.case_id=c.case_id
               JOIN matrix_row m ON m.row_id=cr.row_id
               WHERE c.version LIKE 'sealed:%'
                 AND c.source_pk IN (884,934,1024,1072,1200,1236,
                                     1512,1529,1530,1582,1974,1977)
               GROUP BY c.case_id, c.source_pk, c.version, c.source_tag
               ORDER BY c.source_pk, c.version"""
        ).fetchall()
        if {row[1] for row in cases} != set(ROLES):
            raise ValueError("Frozen source list changed; inspect before classifying")
        classes = {row.slug: row.pk for row in TbClasse.objects.all()}
        catalogs = {}
        digests = {}
        versions_by_source = collections.defaultdict(set)
        for case_id, source_pk, version, tag, class_slug in cases:
            ruleset_id = int(version.removeprefix("sealed:"))
            key = (ruleset_id, classes[class_slug])
            if key not in catalogs:
                catalogs[key] = VersionedClassCatalog(
                    TbRuleset.objects.get(pk=ruleset_id), classes[class_slug]
                )
            features = [
                feature for feature in catalogs[key].collections[TbClassehabilidade]
                if feature.pk == source_pk
            ]
            if len(features) != 1:
                raise ValueError(f"Missing frozen source {source_pk} in {version}")
            feature = features[0]
            if tag not in feature.tags_json:
                raise ValueError(f"Frozen tag changed: {source_pk} in {version}")
            role, phrase = ROLES[source_pk]
            prose = feature.descricao or ""
            if phrase not in plain(prose.replace("\n", " ")):
                raise ValueError(f"Frozen page wording changed: {source_pk} in {version}")
            if source_pk == 1582 and "escolha um aspecto" in plain(prose):
                raise ValueError("Aspect choice is explicit in ShenLong prose; revisit classification")
            digest = hashlib.sha256(prose.encode("utf-8")).hexdigest()
            digests.setdefault(source_pk, set()).add(digest)
            versions_by_source[source_pk].add(version)
            state = (
                "sealed_legacy_builder_verified" if source_pk == 1582
                else "frozen_role_classified_qa_pending"
            )
            action = (
                "Frozen activation tag is historical; verify any separate in-play consumer before closing source discrepancy."
                if source_pk == 1582 else
                "Compare this frozen page role with current builder UI and persisted choices; retest affected levels."
            )
            db.execute(
                """UPDATE review_case SET source_role=?, state=?, evidence=?, next_action=?
                   WHERE case_id=?""",
                (role, state,
                 f"PostgreSQL TbRuleset {ruleset_id}, class-catalog:{classes[class_slug]}, "
                 f"feature PK {source_pk}, prose SHA256 {digest}; exact tag and wording verified.",
                 action, case_id),
            )
        if any(len(values) != 1 for values in digests.values()):
            raise ValueError("Frozen prose differs across revisions; inspect individually")
        db.execute(
            """INSERT OR REPLACE INTO source_conflict VALUES (?,?,?,?,?,?,?,?)""",
            (
                "shenlong-activation-aspect-tag", "tag_prose_gap", 1582,
                "sealed:4,6,7,11",
                "Frozen tag picks dragao_aspecto during ShenLong bonus-action activation; "
                "current fixture removed the redundant activation choice.",
                "Frozen prose describes an aspect attuned at rest in feature 1529, "
                "and choosing affected creatures during ShenLong activation, but no new aspect choice.",
                "PostgreSQL frozen class catalog feature PK 1582 across four revisions; "
                "home/fixtures/conteudo.json PKs 1529/1582; "
                "home.test_pathbuilder.PathbuilderTests: live and sealed aspect tests 1/1 each OK.",
                "Builder creates one persistent aspect at levels 3 and 17 in live/sealed rules. "
                "Check any in-play consumer of the frozen activation tag; preserve sealed snapshots.",
            ),
        )
        if db.execute("SELECT COUNT(*) FROM review_case WHERE state='source_review_pending'").fetchone()[0]:
            raise ValueError("Frozen source alerts still unclassified")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("QA index integrity check failed")
        print({"classified_cases": len(cases), "sources": len(digests),
               "revision_counts": {pk: len(values) for pk, values in versions_by_source.items()},
               "prose_variants": {pk: len(values) for pk, values in digests.items()},
               "states": dict(db.execute("SELECT state,COUNT(*) FROM review_case GROUP BY state"))})


if __name__ == "__main__":
    main()
