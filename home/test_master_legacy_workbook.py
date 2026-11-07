"""Pure unittest tests, using disposable XLSX streams and no Django settings."""
import hashlib
import json
import unittest
from datetime import datetime
from io import BytesIO
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook

from home.master_legacy_workbook import parse_workbook
from home import master_legacy_workbook as parser


class LegacyWorkbookTests(unittest.TestCase):
    def workbook(self, *, adventure_date=datetime(2026, 7, 4), amount=10,
                 label='Fogueira 01 - Nick', purchase_amount=3):
        book = Workbook()
        book.remove(book.active)
        rewards = book.create_sheet('LISTA DE RECOMPENSAS')
        rewards.append(['Recompensas', 'Descricao', 'Preco'])
        for row in (['Fixed', 'Description', 90], ['Rebuild', 'By level', '635 + 35 por nivel'],
                    ['Uso do Cofre de Personagens', 'Historical only', 945],
                    ['Mestre Ouro', 'Monthly', '5000 + 500 / mes']):
            rewards.append(row)
        bau = book.create_sheet('BAU DOS MESTRES')
        bau.append([None, 'Moedas', 'Mesas', 'Eventos'])
        bau.append([label, 20, 1, None])
        bau.append([None, 0, 0, 0])
        bau.append([0, 0, 0, 0])
        history = book.create_sheet('AVENTURAS  MERCADO')
        history.append([None, 'Aventura', None, None, None, None, 'Mercado'])
        history.append([None, 'Mestre', 'Missao', 'Data', 'Recompensa', None, 'Mestre', 'Item', 'Data', 'Preco'])
        history.append([None, label, 'Adventure', adventure_date, amount,
                        None, label, 'Purchase', None, purchase_amount])
        calcs = book.create_sheet('CALCs')
        calcs.append(['MESTRES', 'ENTRADA', 'SAIDA'])
        calcs.append([label, 10, 3])
        calcs.append([0, 0, 0])
        stream = BytesIO()
        book.save(stream)
        book.close()
        stream.seek(0)
        return stream

    def test_snapshot_identity_signs_hash_raw_and_deltas(self):
        stream = self.workbook()
        digest = hashlib.sha256(stream.getvalue()).hexdigest()
        stream.seek(5)
        result = parse_workbook(stream)
        self.assertEqual(stream.tell(), 5)
        self.assertEqual((result['schema'], result['source_sha256']), (1, digest))
        self.assertEqual(len(result['masters']), 1)
        master = result['masters'][0]
        self.assertEqual((master['number'], master['name'], master['balance_mm'], master['event_coins']),
                         (1, 'Nick', 20, 0))
        self.assertEqual(master['calculations']['balance_delta'], 13)
        self.assertEqual(master['calculations']['income_delta'], 0)
        self.assertEqual(master['calculations']['expense_delta'], 0)
        self.assertEqual([row['amount_mm'] for row in result['entries']], [10, -3])
        self.assertEqual([row['date'] for row in result['entries']], ['2026-07-04', None])
        self.assertEqual(result['entries'][0]['key'], 'AVENTURAS  MERCADO:3:adventure')
        self.assertEqual(result['entries'][0]['raw']['C3']['value'], 'Adventure')
        self.assertEqual(result, json.loads(json.dumps(result, allow_nan=False)))
        self.assertEqual(parse_workbook(stream), result)

    def test_only_explicit_legacy_number_prefixes_are_accepted(self):
        for prefix, number in (('Fogueira', 1), ('Fogueiira', 20), ('Fogueire', 36)):
            with self.subTest(prefix=prefix):
                result = parse_workbook(self.workbook(label=f'{prefix} {number:02d} - Nick 99'))
                self.assertEqual(result['masters'][0]['number'], number)
                self.assertEqual(len(result['entries']), 2)
        for label in ('Nick 20', 'Fogueira - Nick 36', 'Another 01 - Nick', 'Fogueira 2'):
            with self.subTest(label=label):
                result = parse_workbook(self.workbook(label=label))
                self.assertEqual(result['masters'], [])
                self.assertEqual(result['entries'], [])
                self.assertTrue(any(w['code'] == 'invalid_master' for w in result['warnings']))

    def test_invalid_dates_quarantine_without_repair_or_losing_raw(self):
        for invalid in ('04/072026', '25/092026', '30/60/2026', '05/09/0206', 46207, True):
            with self.subTest(invalid=invalid):
                result = parse_workbook(self.workbook(adventure_date=invalid))
                self.assertEqual([e['kind'] for e in result['entries']], ['purchase'])
                warning = next(w for w in result['warnings'] if w['code'] == 'quarantined_entry')
                self.assertIn('invalid_date', warning['issues'])
                self.assertIsNone(warning['quarantine']['date'])
                self.assertEqual(warning['quarantine']['raw']['D3']['value'], invalid)

    def test_explicit_date_strings_are_accepted_without_year_inference(self):
        for value in ('04/07/2026', '2026-07-04'):
            self.assertEqual(parse_workbook(self.workbook(adventure_date=value))['entries'][0]['date'], '2026-07-04')

    def test_invalid_amounts_are_not_rounded_or_parsed_as_text(self):
        for invalid in ('10', 'ten', None, True, 2.5):
            with self.subTest(invalid=invalid):
                result = parse_workbook(self.workbook(amount=invalid))
                warning = next(w for w in result['warnings'] if w['code'] == 'quarantined_entry')
                self.assertIn('invalid_amount', warning['issues'])
                self.assertIsNone(warning['quarantine']['amount_mm'])
                self.assertEqual(warning['quarantine']['raw']['E3']['value'], invalid)
                self.assertEqual(result['masters'][0]['balance_mm'], 20)
        result = parse_workbook(self.workbook(purchase_amount=None))
        self.assertEqual([row['kind'] for row in result['entries']], ['adventure'])
        self.assertEqual(result['masters'][0]['calculations']['quarantined_entries'], 1)

    def test_rewards_keep_prices_and_never_activate_retired_features(self):
        rewards = parse_workbook(self.workbook())['rewards']
        self.assertEqual([r['classification'] for r in rewards],
                         ['adapted', 'needs_review_fixed_price', 'retired', 'retired'])
        self.assertEqual(rewards[1]['price'], '635 + 35 por nivel')
        self.assertEqual(rewards[3]['price'], '5000 + 500 / mes')
        self.assertTrue(all(r['active'] is False for r in rewards))

    def test_uncached_formula_is_preserved_and_quarantined_not_evaluated(self):
        result = parse_workbook(self.workbook(amount='=5+5'))
        warning = next(w for w in result['warnings'] if w['code'] == 'quarantined_entry')
        self.assertEqual(warning['quarantine']['raw']['E3']['value'], '=5+5')
        self.assertIsNone(warning['quarantine']['raw']['E3']['cached'])
        self.assertEqual(result['masters'][0]['balance_mm'], 20)

    def test_default_upload_limits_and_bounded_stream_read(self):
        self.assertEqual((parser._MAX_COMPRESSED, parser._MAX_UNCOMPRESSED,
                          parser._MAX_MEMBERS, parser._MAX_ROWS),
                         (8 * 1024 * 1024, 64 * 1024 * 1024, 200, 30000))
        stream = BytesIO(b'x' * (parser._MAX_COMPRESSED + 1))
        stream.seek(7)
        with patch.object(parser, 'load_workbook') as load:
            with self.assertRaisesRegex(ValueError, 'compressed limit'):
                parse_workbook(stream)
            load.assert_not_called()
        self.assertEqual(stream.tell(), 7)

    def test_zip_limits_reject_before_openpyxl(self):
        stream = BytesIO()
        with ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
            for index in range(3):
                archive.writestr(f'member-{index}', b'x' * 100)
        for constant, limit, message in (('_MAX_MEMBERS', 2, 'ZIP-member'),
                                         ('_MAX_UNCOMPRESSED', 299, 'uncompressed')):
            with self.subTest(limit=constant), patch.object(parser, constant, limit), \
                    patch.object(parser, 'load_workbook') as load:
                with self.assertRaisesRegex(ValueError, message):
                    parse_workbook(stream)
                load.assert_not_called()

    def test_row_iteration_is_bounded_including_blank_template_rows(self):
        with patch.object(parser, '_MAX_ROWS', 3):
            with self.assertRaisesRegex(ValueError, 'row limit'):
                parse_workbook(self.workbook())
        # Row 4 is blank template state, but must still count against the bound.
        with patch.object(parser, '_MAX_ROWS', 4):
            rows = parser._rows
            seen = []
            def record(*args):
                for row in rows(*args):
                    seen.append(row[0])
                    yield row
            with patch.object(parser, '_rows', record):
                with self.assertRaisesRegex(ValueError, 'row limit'):
                    parse_workbook(self.workbook())
            self.assertIn(4, seen)


if __name__ == '__main__':
    unittest.main()
