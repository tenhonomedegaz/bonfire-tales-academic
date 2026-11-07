"""Imagens de perfil antigas e candidatas não devem alterar o CSS público."""

from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import UserProfile


class _ImageElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def matching(self, css_class):
        return [attrs for _, attrs in self.elements if css_class in attrs.get('class', '').split()]


class ProfileImageUrlTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('image-qa', password='test-only')
        self.profile = UserProfile.objects.get_or_create(user=self.user)[0]

    def _elements(self, response):
        self.assertEqual(response.status_code, 200)
        elements = _ImageElements()
        elements.feed(response.content.decode())
        return elements

    def test_legacy_urls_cannot_break_profile_css_or_render_executable_avatar(self):
        self.profile.banner_url = "https://cdn.example/banner.png');color:red;--evil:'"
        self.profile.background_url = "https://cdn.example/bg.png');color:red;--evil:'"
        self.profile.avatar_url = 'javascript:alert(1)'
        self.profile.save()

        players = self._elements(self.client.get(reverse('jogadores')))
        player_styles = [attrs.get('style', '') for _, attrs in players.elements]
        self.assertTrue(any('%27%29' in style for style in player_styles))
        self.assertFalse(any("');color:" in style for style in player_styles))
        self.assertEqual(len(players.matching('player-card-avatar')), 1)
        self.assertFalse(any(attrs.get('src', '').startswith('javascript:')
                             for tag, attrs in players.elements if tag == 'img'))

        public = self._elements(self.client.get(reverse('public_profile', args=[self.user.username])))
        for css_class in ('profile-bg-media', 'public-profile-banner-media'):
            style = public.matching(css_class)[0]['style']
            self.assertIn('%27%29', style)
            self.assertNotIn("');color:", style)
        self.assertFalse(any(attrs.get('src', '').startswith('javascript:')
                             for tag, attrs in public.elements if tag == 'img'))

        self.client.force_login(self.user)
        own = self._elements(self.client.get(reverse('profile')))
        for css_class in ('profile-bg-media', 'profile-banner-media', 'banner-preview-box'):
            self.assertNotIn("');color:", own.matching(css_class)[0].get('style', ''))
        preview = self.client.post(reverse('perfil_preview'), {
            'banner_url': self.profile.banner_url,
            'background_url': self.profile.background_url,
            'avatar_url': self.profile.avatar_url,
        })
        self.assertEqual(preview.status_code, 200)
        candidate = _ImageElements()
        candidate.feed(preview.json()['html'])
        self.assertNotIn("');color:", candidate.matching('public-profile-banner-media')[0]['style'])
        self.assertNotIn("');color:", candidate.matching('perfil-preview-bg')[0]['style'])
        self.assertFalse(any(attrs.get('src', '').startswith('javascript:')
                             for tag, attrs in candidate.elements if tag == 'img'))

    def test_https_and_media_images_remain_visible_in_public_and_preview(self):
        self.profile.banner_url = 'https://cdn.example/banner.gif'
        self.profile.avatar_url = '/media/profiles/avatar.png'
        self.profile.background_url = '/media/profiles/bg.webp'
        self.profile.save()
        public = self._elements(self.client.get(reverse('public_profile', args=[self.user.username])))
        self.assertIn('https://cdn.example/banner.gif', public.matching('public-profile-banner-media')[0]['style'])
        self.assertIn('/media/profiles/bg.webp', public.matching('profile-bg-media')[0]['style'])

        self.client.force_login(self.user)
        preview = self.client.post(reverse('perfil_preview'), {
            'banner_url': 'https://cdn.example/banner.gif',
            'avatar_url': '/media/profiles/avatar.png',
            'background_url': '/media/profiles/bg.webp',
        })
        self.assertEqual(preview.status_code, 200)
        elements = _ImageElements()
        elements.feed(preview.json()['html'])
        self.assertIn('https://cdn.example/banner.gif', elements.matching('public-profile-banner-media')[0]['style'])
        self.assertIn('/media/profiles/bg.webp', elements.matching('perfil-preview-bg')[0]['style'])
