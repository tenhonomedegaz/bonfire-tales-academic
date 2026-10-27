from html.parser import HTMLParser

from django.template import Context
from django.template.loader import get_template, render_to_string
from django.template.loader_tags import BlockNode
from django.test import SimpleTestCase


class Scripts(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.scripts = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.scripts.append(dict(attrs))


class ProfileAssetLoadingTests(SimpleTestCase):
    def test_profile_parser_is_deferred_in_dependency_order(self):
        for path in ('home/pages/perfil.html', 'home/pages/perfil_publico.html'):
            template = get_template(path).template
            block = next(node for node in template.nodelist.get_nodes_by_type(BlockNode)
                         if node.name == 'content_libraries')
            context = Context()
            with context.bind_template(template):
                scripts = Scripts(block.render(context)).scripts
            self.assertEqual(len(scripts), 3)
            self.assertTrue(all('defer' in script for script in scripts))
            self.assertEqual([script['src'] for script in scripts], [
                'https://cdn.jsdelivr.net/npm/marked/marked.min.js',
                '/static/js/markdown.js?v=14', '/static/js/options-widget.js?v=5'])

    def test_other_pages_keep_their_existing_execution_contract(self):
        scripts = Scripts(render_to_string('home/includes/content_libraries.html')).scripts
        self.assertEqual(len(scripts), 3)
        self.assertTrue(all('defer' not in script for script in scripts))
