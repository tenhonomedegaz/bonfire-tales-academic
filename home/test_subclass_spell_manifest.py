"""Pure reference-data checks; no Django setup, catalog, API, or database access."""

import json
from collections import Counter
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "docs/vtt/references/subclass-spells-user-20261104.txt"
MANIFEST = ROOT / "home/content_packages/subclass_spells_20261104.json"
CLASS_LABELS = {
    "Artificer": "Art\u00edfice",
    "Ca\u00e7ador": "Ca\u00e7ador",
    "Cl\u00e9rigo": "Cl\u00e9rigo",
    "Druida": "Druida",
    "Feiticeiro": "Feiticeiro",
    "Mistico": "M\u00edstico",
    "Paladino": "Paladino",
}
ELEMENTS = ("\u00c1gua", "Ar", "Fogo", "Terra")
GENIES = ("Dao", "Djinni", "Efreeti", "Marid")
ROW = re.compile(
    r"^(?P<class_level>\d+)\u00ba\s+"
    r"(?:(?P<spell_level>Truque|\d+\u00ba)\s+)?(?P<cells>.+)$"
)
SPELL = re.compile(
    r"(?P<pt>[^\[\],]+?)\s*\[(?P<en>[^\]]+)\]"
    r"(?:\s+(?P<source>TCM|Homebrew)\b)?"
)


def reference_entries():
    """Decode only the supplied layout, rejecting unaccounted-for source text."""
    entries = []
    class_label = subclass = None
    universal = False

    def add_row(text, line_number, variants=()):
        row = ROW.fullmatch(text)
        if row is None:
            raise AssertionError((line_number, text))
        explicit_level = row["spell_level"]
        cells = re.split(r"\s{2,}", row["cells"]) if variants else [row["cells"]]
        if variants and len(cells) != len(variants):
            raise AssertionError((line_number, cells))
        for index, cell in enumerate(cells):
            position = 0
            while position < len(cell):
                match = SPELL.match(cell, position)
                if match is None:
                    raise AssertionError((line_number, cell[position:]))
                entry = {
                    "class": class_label,
                    "subclass": subclass,
                    "class_level": int(row["class_level"]),
                    "english_name": match["en"],
                    "supplied_portuguese_name": match["pt"].strip(),
                    "universal": universal,
                    "source_line": line_number,
                }
                if explicit_level is not None:
                    entry["spell_level"] = (
                        0 if explicit_level == "Truque" else int(explicit_level[:-1])
                    )
                if variants:
                    entry["variant"] = variants[index]
                if match["source"] is not None:
                    entry["supplied_source"] = match["source"]
                entries.append(entry)
                position = match.end()
                while position < len(cell) and cell[position] in " ,\t":
                    position += 1

    for line_number, raw in enumerate(REFERENCE.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line in CLASS_LABELS:
            class_label = CLASS_LABELS[line]
            subclass = None
            universal = False
        elif line.startswith("N\u00edvel"):
            continue
        elif line.startswith("Druida da terra tem"):
            continue
        elif line.startswith("Universal ("):
            if (class_label, subclass) != ("Druida", "Pastoreio Elemental"):
                raise AssertionError((line_number, line))
            universal = True
        elif line.startswith("Nos n\u00edveis "):
            if (class_label, subclass) != ("M\u00edstico", "Genio"):
                raise AssertionError((line_number, line))
            universal = True
            for item in line.split(":", 1)[1].rstrip(".").split(";"):
                add_row(item.strip(), line_number)
        elif ROW.fullmatch(line):
            if class_label is None or subclass is None:
                raise AssertionError((line_number, line))
            variants = ()
            if not universal:
                if (class_label, subclass) == ("Druida", "Pastoreio Elemental"):
                    variants = ELEMENTS
                elif (class_label, subclass) == ("M\u00edstico", "Genio"):
                    variants = GENIES
            add_row(line, line_number, variants)
        else:
            if class_label is None or "[" in line or any(c.isdigit() for c in line):
                raise AssertionError((line_number, line))
            subclass = line
            universal = False
    return entries


class SubclassSpellManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.entries = cls.manifest["entries"]

    def select(self, class_label, subclass):
        return [e for e in self.entries if (e["class"], e["subclass"]) == (class_label, subclass)]

    def test_exact_reference_transcription_including_order_and_provenance(self):
        self.assertEqual(self.entries, reference_entries())
        # Independent coverage check, including every bracketed name in prose/tables.
        names = re.findall(r"\[([^\]]+)\]", REFERENCE.read_text(encoding="utf-8"))
        self.assertEqual([e["english_name"] for e in self.entries], names)

    def test_schema_has_no_guessed_identity_or_grant_semantics(self):
        self.assertEqual(self.manifest["schema_version"], 1)
        self.assertEqual(self.manifest["status"], "unresolved_reference_only")
        self.assertEqual(self.manifest["reference"], REFERENCE.relative_to(ROOT).as_posix())
        self.assertEqual(self.manifest["class_labels"], CLASS_LABELS)
        required = {
            "class", "subclass", "class_level", "english_name",
            "supplied_portuguese_name", "universal", "source_line",
        }
        optional = {"spell_level", "variant", "supplied_source"}
        for entry in self.entries:
            with self.subTest(entry=entry):
                self.assertTrue(required <= entry.keys())
                self.assertTrue(entry.keys() <= required | optional)
                self.assertIn(entry["class"], CLASS_LABELS.values())
                self.assertIs(type(entry["class_level"]), int)
                self.assertGreater(entry["class_level"], 0)
                self.assertIs(type(entry["universal"]), bool)
                self.assertIs(type(entry["source_line"]), int)
                for key in ("subclass", "english_name", "supplied_portuguese_name"):
                    self.assertTrue(entry[key])
                    self.assertEqual(entry[key], entry[key].strip())
                if "spell_level" in entry:
                    self.assertIs(type(entry["spell_level"]), int)
                    self.assertIn(entry["spell_level"], range(10))
                if "variant" in entry:
                    self.assertFalse(entry["universal"])

    def test_exhaustive_counts_and_deferred_earth_druid(self):
        self.assertEqual(Counter(e["class"] for e in self.entries), {
            "Art\u00edfice": 60, "Ca\u00e7ador": 80, "Cl\u00e9rigo": 120,
            "Druida": 84, "Feiticeiro": 71, "M\u00edstico": 90, "Paladino": 90,
        })
        self.assertEqual(len(self.entries), 595)
        self.assertEqual(len({(e["class"], e["subclass"]) for e in self.entries}), 56)
        self.assertFalse(self.select("Druida", "Terra"))
        self.assertEqual(self.manifest["exclusions"], [{
            "class": "Druida", "subclass": "Terra", "reason": "explicitly_deferred",
            "source_line": 240,
        }])

    def test_spell_levels_only_when_explicit_and_unusual_levels_preserved(self):
        explicit = [e for e in self.entries if "spell_level" in e]
        self.assertEqual(len(explicit), 74)
        self.assertTrue(all(e["class"] == "Druida" and e["subclass"] != "Esporos" for e in explicit))
        self.assertEqual(sum(e["spell_level"] == 0 for e in explicit), 8)
        spores = self.select("Druida", "Esporos")
        self.assertEqual(sum(e["class_level"] == 3 for e in spores), 4)
        dreams = self.select("Druida", "Sonhos")
        self.assertEqual([(e["class_level"], e["spell_level"]) for e in dreams],
                         [(3, 1)] * 2 + [(3, 2)] * 2 + [(7, 3)] * 2 + [(9, 4)] * 2 + [(13, 5)] * 2)
        crown = [e for e in self.select("Druida", "Estrelas") if e["english_name"] == "Crown of Stars"]
        self.assertEqual([(e["class_level"], e["spell_level"]) for e in crown], [(13, 7)])

    def test_variants_and_universal_supplements_are_not_flattened(self):
        for class_label, subclass, variants, universal_count in (
            ("Druida", "Pastoreio Elemental", ELEMENTS, 5),
            ("M\u00edstico", "Genio", GENIES, 3),
        ):
            entries = self.select(class_label, subclass)
            self.assertEqual(Counter(e["variant"] for e in entries if "variant" in e),
                             dict.fromkeys(variants, 6))
            universal = [e for e in entries if e["universal"]]
            self.assertEqual(len(universal), universal_count)
            self.assertTrue(all("variant" not in e for e in universal))
        self.assertEqual(sum(e["universal"] for e in self.entries), 8)
        self.assertEqual(sum("variant" in e for e in self.entries), 48)

    def test_supplied_sources_and_ambiguous_names_are_not_corrected(self):
        sourced = [e for e in self.entries if "supplied_source" in e]
        self.assertEqual(len(sourced), 7)
        self.assertEqual({e["supplied_source"] for e in sourced}, {"TCM"})
        self.assertEqual(Counter(e["english_name"] for e in sourced), {
            "Devil's Due": 1, "Sacrificial Siphon": 1, "Summer Winds": 1,
            "Harvest Moonglow": 2, "Hungering Blade": 1, "Call of the Wild": 1,
        })
        names = {e["english_name"] for e in self.select("Art\u00edfice", "Engenheiro de Construto")}
        self.assertIn("leomond's tiny hut", names)
        self.assertIn("Wall of Wind", {e["english_name"] for e in self.select("Druida", "Pastoreio Elemental")})
        self.assertIn("Wind Wall", {e["english_name"] for e in self.select("M\u00edstico", "Genio")})
        death = self.select("Paladino", "Morte")
        self.assertTrue(any(e["english_name"] == "Inflict Wounds" and
                            e["supplied_portuguese_name"] == "Repres\u00e1lia Infernal" for e in death))
        self.assertEqual(len(self.select("Ca\u00e7ador", "Exterminadoress")), 10)


if __name__ == "__main__":
    unittest.main()
