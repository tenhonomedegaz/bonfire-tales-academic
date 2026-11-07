"""Verify the original redesign routes against the current URL configuration."""

import json
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import get_resolver


INVENTORY = Path(__file__).resolve().parent.parent / 'docs/integracao/redesign-s01-inventory.json'


def active_routes(patterns, prefix=''):
    for entry in patterns:
        path = prefix + str(entry.pattern)
        if hasattr(entry, 'url_patterns'):
            yield from active_routes(entry.url_patterns, path)
        else:
            yield path, entry.name


class PresentRedesignRoutesTests(SimpleTestCase):
    def test_original_routes_remain_available(self):
        inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
        self.assertEqual(inventory['source_commit'], '7289711136e340afe5a13ba397ecce978071896d')
        rows = [row for row in inventory['routes'] if row['status'] == 'present']
        self.assertEqual(len(rows), 226)
        root_patterns = get_resolver().url_patterns
        active = set(active_routes(root_patterns))

        for row in rows:
            with self.subTest(path=row['pattern'], name=row['name']):
                if row['file'] == 'bonfire/urls.py' and row['pattern'] in ('admin/', '') and row['name'] is None:
                    # These entries are URL includes, not terminal views.
                    self.assertTrue(any(
                        str(entry.pattern) == row['pattern'] and hasattr(entry, 'url_patterns')
                        for entry in root_patterns
                    ))
                else:
                    self.assertIn((row['pattern'], row['name']), active)
