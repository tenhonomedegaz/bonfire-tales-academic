"""Editorial image URL validation for Jornal create and update flows."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import TbJornal
from .views import _jornal_image_url


class JornalImageUrlTests(TestCase):
    def setUp(self):
        self.editor = get_user_model().objects.create_superuser(
            'jornal-image-editor', 'jornal-image-editor@example.invalid', 'test-pass'
        )
        self.client.force_login(self.editor)

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def test_rejects_unsafe_image_url_without_creating_or_changing_article(self):
        create_url = reverse('jornal_create')
        for image_url in ('javascript:alert(1)', 'data:image/svg+xml,<svg/>', '//evil.example/image.png',
                          'https://example.org/a\n.css'):
            response = self.post_json(create_url, {'titulo': 'Teste de capa', 'imagem_url': image_url})
            self.assertEqual(response.status_code, 400, image_url)
            self.assertIn('URL de imagem', response.json()['error'])
        self.assertFalse(TbJornal.objects.filter(titulo='Teste de capa').exists())

        article = TbJornal.objects.create(titulo='Seguro', slug='seguro', imagem_url='/static/assets/logo.png')
        update_url = reverse('jornal_update', args=[article.slug])
        response = self.post_json(update_url, {'titulo': 'Alterado', 'imagem_url': 'javascript:alert(1)'})
        self.assertEqual(response.status_code, 400)
        article.refresh_from_db()
        self.assertEqual(article.titulo, 'Seguro')
        self.assertEqual(article.imagem_url, '/static/assets/logo.png')

    def test_safe_images_remain_available_and_css_delimiters_are_encoded(self):
        source = "/static/assets/logo.png');color:red;--evil:'"
        self.assertIn('%27%29', _jornal_image_url(source))
        self.assertEqual(_jornal_image_url('https://example.org/cover.webp?x=1&y=2'),
                         'https://example.org/cover.webp?x=1&y=2')
        response = self.post_json(reverse('jornal_create'), {
            'titulo': 'Capa válida', 'imagem_url': '/static/assets/logo.png',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TbJornal.objects.get(slug='capa-valida').imagem_url, '/static/assets/logo.png')
