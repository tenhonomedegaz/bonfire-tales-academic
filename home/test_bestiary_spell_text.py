from django.test import SimpleTestCase

from .bestiary_spell_text import decorate_spell_text


class BestiarySpellTextTests(SimpleTestCase):
    def test_explicit_english_and_portuguese_names_both_have_cards(self):
        source = {'spell_refs': [{'slug': 'queda-suave', 'name': 'Queda Suave',
                                 'name_en': 'Feather Fall', 'resolved': True}]}
        output = decorate_spell_text({'texto': 'Queda Suave [Feather Fall].\n\nOutro paragrafo.'}, source)
        self.assertEqual(str(output['spell_text_html']).count('data-args="queda-suave"'), 2)
        self.assertIn('</p><p>Outro paragrafo.', output['spell_text_html'])
        self.assertNotIn('spell_extra_rows', output)

    def test_unmentioned_reference_gets_a_card_without_inventing_a_name_match(self):
        output = decorate_spell_text({'texto': 'Uma traducao antiga.'}, {'spell_refs': [
            {'slug': 'lufada-de-vento', 'name': 'Lufada de Vento', 'resolved': True}]})
        self.assertEqual(output['spell_extra_rows'][0]['spells'][0]['slug'], 'lufada-de-vento')

    def test_source_html_is_escaped_and_untrusted_slug_is_not_a_link(self):
        output = decorate_spell_text({'texto': '<script>Queda Suave</script>'}, {'spell_refs': [
            {'slug': 'queda-suave', 'name': 'Queda Suave'},
            {'slug': 'bad" onclick="x', 'name': 'Outra magia'}]})
        self.assertNotIn('<script>', output['spell_text_html'])
        self.assertIn('&lt;script&gt;', output['spell_text_html'])
        self.assertNotIn('onclick', output['spell_text_html'])

    def test_no_guessing_or_links_for_unresolved_references(self):
        feature = {'texto': 'Feather Fall e outra magia.'}
        self.assertEqual(decorate_spell_text(dict(feature), {}), feature)
        self.assertEqual(decorate_spell_text(dict(feature), {'spell_refs': [
            {'slug': 'feather-fall', 'name': 'Feather Fall', 'resolved': False}]}), feature)
