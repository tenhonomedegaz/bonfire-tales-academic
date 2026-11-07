"""Focused wall tests, including a standalone SQLite-only runner.

Run: py -m home.test_profile_comments --isolated
No production settings, environment secrets, project migrations or URLs are loaded.
"""

import sys

if __name__ == '__main__' and '--isolated' in sys.argv:
    from django.conf import settings
    settings.configure(
        SECRET_KEY='isolated-profile-comments-tests', USE_TZ=True,
        INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes',
                        'django.contrib.sessions', 'django.contrib.messages',
                        'django.contrib.admin.apps.SimpleAdminConfig', 'home'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'], LOGIN_URL='/login/',
        SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
        MIDDLEWARE=['django.contrib.sessions.middleware.SessionMiddleware',
                    'django.contrib.auth.middleware.AuthenticationMiddleware',
                    'django.contrib.messages.middleware.MessageMiddleware'],
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
        TEMPLATES=[{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True}],
        STATIC_URL='/static/',
        CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
    )
    import django
    django.setup()

import importlib
import json
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import IntegrityError, connection, migrations, transaction
from django.db.migrations.state import ProjectState
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.template import Context, Template
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import path, reverse
from django.utils import timezone
from django.utils.safestring import SafeData
from django.views.decorators.csrf import ensure_csrf_cookie

from home import profile_comments as wall
from home.models import TbPerfilComentario, TbPerfilComentarioCurtida, UserProfile


def public_profile(request, username):
    return HttpResponse(username)


@ensure_csrf_cookie
def csrf_token(request):
    return HttpResponse(get_token(request))


urlpatterns = [
    path('perfil/<str:username>/', public_profile, name='public_profile'),
    path('wall/<str:username>/create/', wall.comment_create, name='perfil_comentar'),
    path('wall/<int:comment_id>/like/', wall.comment_like, name='perfil_comentario_curtir'),
    path('wall/<int:comment_id>/remove/', wall.comment_remove, name='perfil_comentario_remover'),
    path('csrf/', csrf_token),
]


@override_settings(ROOT_URLCONF=__name__, ALLOWED_HOSTS=['testserver'])
class ProfileWallTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user('wall-owner')
        cls.author = User.objects.create_user('wall-author')
        cls.viewer = User.objects.create_user('wall-viewer')
        cls.staff = User.objects.create_user('wall-staff', is_staff=True)
        cls.inactive = User.objects.create_user('wall-inactive', is_active=False)

    def setUp(self):
        self.catalog = self.enterContext(patch.object(wall.cosmetics, 'get_catalog', return_value={}))
        self.load = self.enterContext(patch.object(wall, 'load_package', return_value=None))
        self.sync = self.enterContext(patch.object(
            wall.cosmetics, '_sync_rank_once', side_effect=AssertionError('Read must not grant cosmetics')))
        self.client.force_login(self.author)

    def create(self, *, target=None, text='Hello **wall**', key=None, client=None):
        return (client or self.client).post(reverse('perfil_comentar', args=[(target or self.owner).username]),
                                           {'texto': text, 'chave_operacao': str(key or uuid4())})

    def comment(self, *, author=None, target=None, text='Public comment', **extra):
        return TbPerfilComentario.objects.create(autor=author or self.author, perfil=target or self.owner,
                                                 texto=text, chave_operacao=uuid4(), **extra)

    def context(self, viewer=None, page=1, target=None, request=None):
        return wall.wall_context(target or self.owner, viewer or AnonymousUser(), page,
                                 request=request)['profile_wall']

    def like(self, comment, desired=True, *, json_request=True, client=None):
        data = {'curtido': desired} if json_request else {'curtido': 'true' if desired else 'false'}
        return (client or self.client).post(
            reverse('perfil_comentario_curtir', args=[comment.pk]),
            data=json.dumps(data) if json_request else data,
            content_type='application/json' if json_request else 'application/x-www-form-urlencoded')

    def test_create_prg_plain_markdown_and_no_automatic_like(self):
        text = '<img src=x onerror=alert(1)> **markdown**'
        response = self.create(text='  ' + text + '  ')
        self.assertRedirects(response, '/perfil/wall-owner/#comentarios', fetch_redirect_response=False)
        comment = TbPerfilComentario.objects.get()
        self.assertEqual(comment.texto, text)
        self.assertEqual(comment.autor_id, self.author.pk)
        self.assertEqual(comment.perfil_id, self.owner.pk)
        self.assertEqual(TbPerfilComentarioCurtida.objects.count(), 0)
        row = self.context()['comments_page'][0]
        self.assertEqual(row['texto'], text)
        self.assertNotIsInstance(row['texto'], SafeData)
        html = Template('<div data-markdown-source>{{ texto|escape }}</div>').render(Context(row))
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)

    def test_nested_context_form_and_exact_row_contract(self):
        comment = self.comment()
        context = wall.wall_context(self.owner, self.viewer, 1)
        self.assertEqual(set(context), {'profile_wall'})
        panel = context['profile_wall']
        self.assertTrue(panel['can_comment'])
        self.assertEqual(set(panel['comment_form'].fields), {'texto', 'chave_operacao'})
        self.assertTrue(panel['comment_form'].fields['chave_operacao'].widget.is_hidden)
        row = panel['comments_page'][0]
        self.assertTrue({'obj', 'pk', 'texto', 'autor', 'criado_em', 'like_count', 'liked_by_viewer',
                         'can_remove', 'can_like', 'avatar_url', 'frame_key', 'frame_class',
                         'frame_package', 'appearance'} <= set(row))
        self.assertEqual(row['obj'].pk, comment.pk)
        self.assertEqual(row['autor'].pk, self.author.pk)
        self.assertTrue(row['can_like'])
        self.assertFalse(row['can_remove'])
        self.assertFalse(row['liked_by_viewer'])
        self.assertEqual(row['like_count'], 0)

    def test_owner_can_comment_on_own_wall(self):
        self.client.force_login(self.owner)
        self.assertTrue(self.context(viewer=self.owner)['can_comment'])
        self.create()
        self.assertEqual(TbPerfilComentario.objects.get().autor_id, self.owner.pk)

    def test_login_and_post_are_required_for_all_handlers(self):
        comment = self.comment()
        urls = [reverse('perfil_comentar', args=[self.owner.username]),
                reverse('perfil_comentario_curtir', args=[comment.pk]),
                reverse('perfil_comentario_remover', args=[comment.pk])]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
                self.assertEqual(Client().post(url).status_code, 302)

    def test_explicit_csrf_protection_even_without_global_csrf_middleware(self):
        comment = self.comment()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.viewer)
        urls = [reverse('perfil_comentar', args=[self.owner.username]),
                reverse('perfil_comentario_curtir', args=[comment.pk]),
                reverse('perfil_comentario_remover', args=[comment.pk])]
        for url in urls:
            self.assertEqual(client.post(url).status_code, 403)
        token = client.get('/csrf/').content.decode()
        self.assertEqual(client.post(urls[1], {'curtido': 'true'}, HTTP_X_CSRFTOKEN=token).status_code, 302)
        self.assertEqual(TbPerfilComentarioCurtida.objects.count(), 1)

    def test_inactive_wall_is_suppressed_without_queries_or_form(self):
        self.comment(target=self.inactive)
        with self.assertNumQueries(0):
            panel = self.context(viewer=self.viewer, target=self.inactive)
        self.assertEqual(list(panel['comments_page']), [])
        self.assertFalse(panel['can_comment'])
        self.assertIsNone(panel['comment_form'])
        self.assertEqual(self.create(target=self.inactive).status_code, 404)

    def test_inactive_author_removed_comments_and_inactive_likes_are_not_public(self):
        visible = self.comment()
        self.comment(author=self.inactive)
        self.comment(removido_em=timezone.now(), removido_por=self.owner)
        TbPerfilComentarioCurtida.objects.create(comentario=visible, quem=self.inactive)
        TbPerfilComentarioCurtida.objects.create(comentario=visible, quem=self.viewer)
        rows = list(self.context(viewer=self.viewer)['comments_page'])
        self.assertEqual([row['pk'] for row in rows], [visible.pk])
        self.assertEqual(rows[0]['like_count'], 1)
        self.assertTrue(rows[0]['liked_by_viewer'])
        self.assertFalse(self.context(viewer=self.inactive)['can_comment'])

    def test_inactive_actor_cannot_write_using_stale_request(self):
        comment = self.comment()
        factory = RequestFactory()
        for handler, args in [(wall.comment_create, [self.owner.username]),
                              (wall.comment_like, [comment.pk]), (wall.comment_remove, [comment.pk])]:
            request = factory.post('/wall/')
            request._dont_enforce_csrf_checks = True
            request.user = self.inactive
            self.assertEqual(handler(request, *args).status_code, 403)

    def test_create_replay_uuid_matches_payload_and_never_revives_deleted_comment(self):
        key = uuid4()
        self.create(key=key)
        self.create(key=key)
        self.assertEqual(TbPerfilComentario.objects.count(), 1)
        comment = TbPerfilComentario.objects.get()
        self.client.post(reverse('perfil_comentario_remover', args=[comment.pk]))
        self.create(key=key)
        comment.refresh_from_db()
        self.assertIsNotNone(comment.removido_em)
        self.assertEqual(TbPerfilComentario.objects.count(), 1)

    def test_uuid_conflicts_across_payload_profile_and_account_do_not_create(self):
        key = uuid4()
        self.create(key=key)
        for target, actor, text in [(self.owner, self.author, 'Changed'),
                                    (self.viewer, self.author, 'Hello **wall**'),
                                    (self.owner, self.viewer, 'Hello **wall**')]:
            self.client.force_login(actor)
            response = self.create(key=key, target=target, text=text)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(list(get_messages(response.wsgi_request)))
        self.assertEqual(TbPerfilComentario.objects.count(), 1)

    def test_invalid_text_uuid_and_bounded_prg_draft(self):
        for text, key in [('', str(uuid4())), (' \n\t ', str(uuid4())), ('x' * 4001, str(uuid4())),
                          ('Valid draft', 'invalid-uuid')]:
            with self.subTest(length=len(text), key=key):
                response = self.client.post(reverse('perfil_comentar', args=[self.owner.username]),
                                            {'texto': text, 'chave_operacao': key})
                self.assertRedirects(response, '/perfil/wall-owner/#comentarios', fetch_redirect_response=False)
                self.assertLessEqual(len(self.client.session[wall._DRAFT_KEY]['texto']), 4000)
                self.assertTrue(list(get_messages(response.wsgi_request)))
        self.assertEqual(TbPerfilComentario.objects.count(), 0)
        request = SimpleNamespace(session=self.client.session)
        panel = self.context(viewer=self.author, request=request)
        form = panel['comment_form']
        self.assertEqual(form['texto'].value(), 'Valid draft')
        UUID(form['chave_operacao'].value())
        self.assertTrue(form.non_field_errors())
        self.assertNotIn(wall._DRAFT_KEY, request.session)

    def test_draft_is_only_consumed_for_same_actor_and_wall(self):
        self.create(text='x' * 4001)
        request = SimpleNamespace(session=self.client.session)
        self.context(viewer=self.viewer, request=request)
        self.assertIn(wall._DRAFT_KEY, request.session)
        self.context(viewer=self.author, target=self.viewer, request=request)
        self.assertIn(wall._DRAFT_KEY, request.session)
        self.context(viewer=self.author, request=request)
        self.assertNotIn(wall._DRAFT_KEY, request.session)

    def test_maximum_unicode_text_is_accepted(self):
        self.create(text='\u00e1' * 4000)
        self.assertEqual(len(TbPerfilComentario.objects.get().texto), 4000)

    def test_rate_limit_is_global_per_actor_includes_deleted_and_replay_is_allowed(self):
        comments = [self.comment(target=self.viewer) for _ in range(5)]
        TbPerfilComentario.objects.filter(pk=comments[0].pk).update(removido_em=timezone.now())
        self.create()
        self.assertEqual(TbPerfilComentario.objects.count(), 5)
        self.assertIn('Limite', self.client.session[wall._DRAFT_KEY]['error'])
        response = self.create(target=self.viewer, key=comments[1].chave_operacao, text=comments[1].texto)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TbPerfilComentario.objects.count(), 5)
        TbPerfilComentario.objects.update(criado_em=timezone.now() - wall.COMMENT_WINDOW - timedelta(seconds=1))
        self.create()
        self.assertEqual(TbPerfilComentario.objects.count(), 6)

    def test_create_locks_actor_before_rate_limit_query(self):
        manager = get_user_model().objects
        with patch.object(manager, 'select_for_update', wraps=manager.select_for_update) as lock:
            self.create()
        lock.assert_called_once_with(no_key=True)

    def test_likes_desired_state_is_idempotent_and_json_contract_exact(self):
        comment = self.comment()
        self.client.force_login(self.viewer)
        for desired, count in [(True, 1), (True, 1), (False, 0), (False, 0), (True, 1)]:
            response = self.like(comment, desired)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'ok': True, 'curtido': desired, 'curtidas': count})
            self.assertEqual(TbPerfilComentarioCurtida.objects.count(), count)
            self.assertIn('private', response['Cache-Control'])
        self.assertTrue(self.context(viewer=self.viewer)['comments_page'][0]['liked_by_viewer'])

    def test_form_likes_prg_and_missing_or_invalid_desired_state_does_not_toggle(self):
        comment = self.comment()
        self.client.force_login(self.viewer)
        url = reverse('perfil_comentario_curtir', args=[comment.pk])
        for state in ('true', 'true', 'false', 'false'):
            response = self.client.post(url, {'curtido': state})
            self.assertRedirects(response, '/perfil/wall-owner/#comentarios', fetch_redirect_response=False)
            self.assertEqual(TbPerfilComentarioCurtida.objects.count(), int(state == 'true'))
        for value in ({}, {'curtido': 'yes'}, {'curtido': 1}, {'curtido': 'true'}, []):
            response = self.client.post(url, json.dumps(value), content_type='application/json')
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post(url, '{', content_type='application/json').status_code, 400)
        self.assertEqual(TbPerfilComentarioCurtida.objects.count(), 0)

    def test_self_likes_and_likes_on_hidden_or_inactive_comments_are_rejected(self):
        comment = self.comment()
        self.assertEqual(self.like(comment).status_code, 400)
        self.assertFalse(self.context(viewer=self.author)['comments_page'][0]['can_like'])
        self.client.force_login(self.viewer)
        hidden = self.comment(removido_em=timezone.now())
        inactive = self.comment(author=self.inactive)
        inactive_wall = self.comment(target=self.inactive)
        for item in (hidden, inactive, inactive_wall):
            self.assertEqual(self.like(item).status_code, 404)
        self.assertEqual(TbPerfilComentarioCurtida.objects.count(), 0)

    def test_remove_permissions_and_soft_delete_preserves_likes_and_first_actor(self):
        for actor in (self.author, self.owner, self.staff):
            comment = self.comment()
            TbPerfilComentarioCurtida.objects.create(comentario=comment, quem=self.viewer)
            self.client.force_login(actor)
            url = reverse('perfil_comentario_remover', args=[comment.pk])
            response = self.client.post(url)
            self.assertRedirects(response, '/perfil/wall-owner/#comentarios', fetch_redirect_response=False)
            comment.refresh_from_db()
            removed_at = comment.removido_em
            self.assertIsNotNone(removed_at)
            self.assertEqual(comment.removido_por_id, actor.pk)
            self.client.force_login(self.staff)
            self.client.post(url)
            comment.refresh_from_db()
            self.assertEqual(comment.removido_em, removed_at)
            self.assertEqual(comment.removido_por_id, actor.pk)
            self.assertTrue(TbPerfilComentarioCurtida.objects.filter(comentario=comment).exists())
        self.assertEqual(len(self.context()['comments_page']), 0)

    def test_unauthorized_remove_does_not_mutate(self):
        comment = self.comment()
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(reverse('perfil_comentario_remover', args=[comment.pk])).status_code, 403)
        comment.refresh_from_db()
        self.assertIsNone(comment.removido_em)
        for viewer, expected in [(self.author, True), (self.owner, True), (self.staff, True),
                                 (self.viewer, False), (AnonymousUser(), False)]:
            self.assertEqual(self.context(viewer=viewer)['comments_page'][0]['can_remove'], expected)

    def test_pagination_ten_and_newest_first_with_stable_ties(self):
        comments = [self.comment(text=str(index)) for index in range(23)]
        TbPerfilComentario.objects.update(criado_em=timezone.now())
        first = self.context(page='bad')['comments_page']
        second = self.context(page=2)['comments_page']
        last = self.context(page='999999999999999999999999999999999')['comments_page']
        self.assertEqual([row['pk'] for row in first], [item.pk for item in comments[-1:-11:-1]])
        self.assertEqual(len(second), 10)
        self.assertEqual(len(last), 3)
        self.assertEqual(last.number, 3)

    def test_wall_aggregates_without_n_plus_one_or_database_writes(self):
        authors = [get_user_model().objects.create_user(f'wall-many-{index}') for index in range(10)]
        for author in authors:
            comment = self.comment(author=author)
            TbPerfilComentarioCurtida.objects.create(comentario=comment, quem=self.viewer)
        with CaptureQueriesContext(connection) as captured:
            panel = self.context(viewer=self.viewer)
            for row in panel['comments_page']:
                _ = (row['autor'].username, row['autor'].profile.avatar_url, row['like_count'], row['liked_by_viewer'])
        queries = [query['sql'] for query in captured.captured_queries]
        self.assertEqual(len(queries), 2, queries)
        self.assertTrue(all(sql.lstrip().upper().startswith('SELECT') for sql in queries))
        self.assertTrue(any('COUNT(' in sql.upper() and 'EXISTS(' in sql.upper() for sql in queries))
        self.sync.assert_not_called()

    def test_query_cost_stays_bounded_from_one_to_ten_active_authors(self):
        with self.assertNumQueries(1):
            self.assertEqual(len(self.context(viewer=self.viewer)['comments_page']), 0)
        self.comment()
        with self.assertNumQueries(2):
            self.assertEqual(len(self.context(viewer=self.viewer)['comments_page']), 1)
        authors = [get_user_model().objects.create_user(f'wall-bounded-{index}') for index in range(9)]
        for author in authors:
            comment = self.comment(author=author)
            TbPerfilComentarioCurtida.objects.create(comentario=comment, quem=self.viewer)
            TbPerfilComentarioCurtida.objects.create(comentario=comment, quem=self.owner)
        with self.assertNumQueries(2):
            rows = list(self.context(viewer=self.viewer)['comments_page'])
            self.assertEqual(len(rows), 10)
            self.assertTrue(all(row['autor'].is_active for row in rows))
            self.assertEqual(sum(row['like_count'] for row in rows), 18)
            self.assertEqual(sum(row['liked_by_viewer'] for row in rows), 9)

    def test_create_like_remove_only_write_wall_tables(self):
        viewer_client, owner_client = Client(), Client()
        viewer_client.force_login(self.viewer)
        owner_client.force_login(self.owner)
        with CaptureQueriesContext(connection) as captured:
            self.create()
            comment = TbPerfilComentario.objects.get()
            self.like(comment, client=viewer_client)
            owner_client.post(reverse('perfil_comentario_remover', args=[comment.pk]))
            self.context(viewer=self.viewer)
        mutations = [query['sql'] for query in captured.captured_queries
                     if query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(len(mutations), 3, mutations)
        self.assertTrue(all('"TB_PerfilComentario"' in sql or '"TB_PerfilComentarioCurtida"' in sql
                            for sql in mutations), mutations)
        self.assertEqual(TbPerfilComentarioCurtida.objects.count(), 1)
        self.sync.assert_not_called()

    def test_missing_author_profile_does_not_create_profile_or_query_per_row(self):
        self.comment()
        UserProfile.objects.filter(user=self.author).delete()
        with self.assertNumQueries(2):
            row = self.context()['comments_page'][0]
            self.assertEqual(row['avatar_url'], '')
            self.assertEqual(row['frame_key'], 'none')
        self.assertFalse(UserProfile.objects.filter(user=self.author).exists())

    def test_avatar_sanitizer_and_frames_do_not_use_visitor_entitlement_or_write(self):
        self.comment()
        UserProfile.objects.filter(user=self.author).update(avatar_url='javascript:alert(1)', avatar_frame='owned')
        self.catalog.return_value = {'owned': {'slug': 'moldura-owned', 'origem': 'staff', 'escopo': 'ambos',
                                             'class': 'frame-owned'}}
        with patch.object(wall, '_frame_rights', return_value={self.author.pk: {'moldura-owned'}}), patch(
                'home.conquistas.visibilidade_conquistas_de_personagem', return_value=({}, {})):
            with CaptureQueriesContext(connection) as captured:
                row = self.context(viewer=self.viewer)['comments_page'][0]
            self.assertEqual(row['avatar_url'], '')
            self.assertEqual(row['frame_key'], 'owned')
            self.assertEqual(row['frame_class'], 'frame-owned')
            self.assertFalse(any(query['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))
                                 for query in captured.captured_queries))
        self.load.assert_called_once_with('moldura', 'owned', 'perfil')
        self.sync.assert_not_called()

    def test_private_unowned_wrong_scope_and_unsafe_frames_fall_back(self):
        self.comment()
        UserProfile.objects.filter(user=self.author).update(avatar_frame='sample')
        metadata = {'slug': 'moldura-sample', 'origem': 'staff', 'escopo': 'ambos', 'class': 'frame-sample'}
        self.catalog.return_value = {'sample': metadata}
        for rights, hidden, scope in [(set(), set(), 'ambos'), ({'moldura-sample'}, {'moldura-sample'}, 'ambos'),
                                      ({'moldura-sample'}, set(), 'ficha')]:
            metadata['escopo'] = scope
            with patch.object(wall, '_frame_rights', return_value={self.author.pk: rights}), patch(
                    'home.conquistas.visibilidade_conquistas_de_personagem',
                    return_value=({}, {self.author.pk: hidden})):
                row = self.context(viewer=self.author)['comments_page'][0]
                self.assertEqual(row['frame_key'], 'none')
                self.assertEqual(row['frame_class'], '')
        UserProfile.objects.filter(user=self.author).update(avatar_frame='../bad')
        self.assertEqual(self.context()['comments_page'][0]['frame_key'], 'none')
        self.load.assert_not_called()

    def test_collaborator_frame_uses_authors_tier_not_viewers_or_expired_inventory(self):
        self.comment()
        UserProfile.objects.filter(user=self.author).update(avatar_frame='colab')
        self.catalog.return_value = {'colab': {'slug': 'moldura-colab', 'origem': 'colaborador',
                                             'requer_plano': 'conde', 'escopo': 'perfil', 'class': 'frame-colab'}}
        for tier, expected in [(None, 'none'), ('conde', 'colab'), ('duque', 'colab')]:
            with self.subTest(tier=tier), patch.object(wall, '_frame_rights', return_value={}), patch(
                    'home.conquistas.visibilidade_conquistas_de_personagem', return_value=({}, {})), patch.object(
                    wall, '_colab_tiers', return_value={self.author.pk: tier}) as tiers:
                self.assertEqual(self.context(viewer=self.viewer)['comments_page'][0]['frame_key'], expected)
                self.assertEqual([user.pk for user in tiers.call_args.args[0]], [self.author.pk])

    def test_frame_projection_matches_existing_discovery_suspension_policy(self):
        from home import cosmetic_discovery
        self.comment()
        UserProfile.objects.filter(user=self.author).update(avatar_frame='sample')
        cases = [('staff', 'staff', False, False, None, True),
                 ('staff', 'staff', True, False, None, False),
                 ('staff', 'staff', True, True, None, True),
                 ('colaborador', 'colaborador:duque', False, False, None, False),
                 ('colaborador', 'colaborador:duque', True, False, 'conde', True)]
        for origin, source, suspended, permanent, tier, expected in cases:
            with self.subTest(origin=origin, suspended=suspended, permanent=permanent, tier=tier):
                item = dict(slug='moldura-sample', key='sample', tipo='moldura', origem=origin,
                            escopo='perfil', requer_plano='conde', **{'class': 'frame-sample'})
                snapshot = {'inventory': {'moldura-sample': {
                    'origem': source, 'suspenso_em': timezone.now() if suspended else None}},
                    'permanent': {'moldura-sample'} if permanent else set(), 'tier': tier,
                    'cash': [], 'events': [], 'rules': {}}
                self.catalog.return_value = {'sample': item}
                persisted = permanent or (not suspended and not source.startswith('colaborador'))
                with patch.object(wall, '_frame_rights', return_value={
                        self.author.pk: {'moldura-sample'} if persisted else set()}), patch.object(
                        wall, '_colab_tiers', return_value={self.author.pk: tier}), patch(
                        'home.conquistas.visibilidade_conquistas_de_personagem', return_value=({}, {})), patch.object(
                        cosmetic_discovery, '_activation_links', return_value=[]), patch.object(
                        cosmetic_discovery, 'reverse', return_value='/known-acquisition/'):
                    state, _, _ = cosmetic_discovery._availability(item, snapshot, timezone.now())
                    row = self.context(viewer=self.viewer)['comments_page'][0]
                self.assertEqual(state in {'disponivel', 'possuido'}, expected)
                self.assertEqual(row['frame_key'] == 'sample', expected)

    def test_free_safe_frame_and_shared_package_are_projected_once(self):
        self.comment()
        self.comment(author=self.viewer)
        UserProfile.objects.filter(user__in=[self.author, self.viewer]).update(
            avatar_frame='sample', avatar_url='/media/profiles/avatar.png')
        self.catalog.return_value = {'sample': {'slug': 'moldura-sample', 'origem': 'livre', 'escopo': 'perfil',
                                              'class': 'frame-sample'}}
        self.load.return_value = {'avatar': [{'url': '/static/cosmetics/a.webp'}]}
        with patch.object(wall, '_frame_rights', side_effect=AssertionError('Free frames need no ownership read')):
            rows = list(self.context()['comments_page'])
        self.assertTrue(all(row['frame_package']['avatar'] and row['avatar_url'] for row in rows))
        self.load.assert_called_once_with('moldura', 'sample', 'perfil')
        self.catalog.return_value['sample']['class'] = 'frame-x;position:fixed'
        self.assertEqual(self.context()['comments_page'][0]['frame_class'], '')

    def test_database_constraints_for_uuid_length_and_unique_like(self):
        comment = self.comment()
        for text in ('', 'x' * 4001):
            with self.assertRaises(IntegrityError), transaction.atomic():
                self.comment(text=text)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TbPerfilComentario.objects.create(autor=self.author, perfil=self.owner, texto='duplicate',
                                              chave_operacao=comment.chave_operacao)
        TbPerfilComentarioCurtida.objects.create(comentario=comment, quem=self.viewer)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TbPerfilComentarioCurtida.objects.create(comentario=comment, quem=self.viewer)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.comment(removido_por=self.staff)

    def test_admin_moderation_only_soft_removes_and_likes_are_read_only(self):
        importlib.import_module('home.profile_comments_admin')
        model_admin = admin.site._registry[TbPerfilComentario]
        like_admin = admin.site._registry[TbPerfilComentarioCurtida]
        request = RequestFactory().post('/admin/wall/')
        request.user = self.staff
        request.session = {}
        request._messages = FallbackStorage(request)
        comment = self.comment()
        TbPerfilComentarioCurtida.objects.create(comentario=comment, quem=self.viewer)
        with patch.object(model_admin, 'has_change_permission', return_value=False):
            model_admin.soft_remove_comments(request, TbPerfilComentario.objects.all())
        comment.refresh_from_db()
        self.assertIsNone(comment.removido_em)
        with patch.object(model_admin, 'has_change_permission', return_value=True):
            model_admin.soft_remove_comments(request, TbPerfilComentario.objects.all())
        comment.refresh_from_db()
        self.assertEqual(comment.removido_por_id, self.staff.pk)
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertFalse(like_admin.has_add_permission(request))
        self.assertFalse(like_admin.has_change_permission(request))
        self.assertFalse(like_admin.has_delete_permission(request))
        self.assertEqual(TbPerfilComentarioCurtida.objects.count(), 1)

    def test_migration_is_schema_only_and_matches_model_state(self):
        migration = importlib.import_module('home.migrations.0166_profile_comments').Migration('0166_profile_comments', 'home')
        self.assertTrue(all(isinstance(operation, migrations.CreateModel) for operation in migration.operations))
        state = ProjectState.from_apps(apps)
        for name in ('tbperfilcomentariocurtida', 'tbperfilcomentario'):
            state.remove_model('home', name)
        for operation in migration.operations:
            operation.state_forwards('home', state)
        expected = ProjectState.from_apps(apps)
        for name in ('tbperfilcomentario', 'tbperfilcomentariocurtida'):
            self.assertEqual(state.models['home', name], expected.models['home', name])


class ProfileWallBatchTests(unittest.TestCase):
    def test_frame_rights_batch_uses_only_persisted_active_rights(self):
        users = [SimpleNamespace(pk=1), SimpleNamespace(pk=2)]
        models = [wall.TbUsuarioCosmetico, wall.CosmeticCheckoutPurchase,
                  wall.EventCosmeticRedemption, wall.CosmeticMMRedemption]
        from contextlib import ExitStack
        with ExitStack() as stack:
            managers = [stack.enter_context(patch.object(model, 'objects')) for model in models]
            managers[0].filter.return_value.exclude.return_value.values_list.return_value = [(1, 'moldura-a')]
            for manager in managers[1:]:
                manager.filter.return_value.values_list.return_value = [(2, 'moldura-b')]
            self.assertEqual(wall._frame_rights(users, {'moldura-a', 'moldura-b'}),
                             {1: {'moldura-a'}, 2: {'moldura-b'}})
            self.assertTrue(managers[0].filter.call_args.kwargs['suspenso_em__isnull'])
            self.assertTrue(managers[1].filter.call_args.kwargs['granted_at__isnull'] is False)
            self.assertTrue(managers[3].filter.call_args.kwargs['reversed_at__isnull'])
            for manager in managers:
                self.assertEqual(manager.filter.call_args.kwargs.get('user_id__in',
                                 manager.filter.call_args.kwargs.get('beneficiary_id__in')), [1, 2])
                manager.create.assert_not_called()
                manager.update.assert_not_called()

    def test_colab_tiers_use_oauth_only_and_highest_active_plan_in_batch(self):
        from home.models import BotMember, BotTransaction
        users = [SimpleNamespace(pk=1, profile=SimpleNamespace(discord_user_id='oauth-1')),
                 SimpleNamespace(pk=2, profile=SimpleNamespace(discord_user_id=None), email='one@example.invalid'),
                 SimpleNamespace(pk=3, profile=SimpleNamespace(discord_user_id='oauth-3'))]
        with patch.object(BotMember, 'objects') as members, patch.object(BotTransaction, 'objects') as plans, patch.object(
                wall.transaction, 'atomic'):
            members.filter.return_value.order_by.return_value.values_list.return_value = [
                ('oauth-1', 'ONE@example.invalid'), ('oauth-3', 'three@example.invalid')]
            plans.filter.return_value.values_list.return_value = [
                ('one@example.invalid', 'colaborador-conde'), ('one@example.invalid', 'colaborador-duque'),
                ('three@example.invalid', 'colaborador-marques')]
            self.assertEqual(wall._colab_tiers(users), {1: 'duque', 3: 'marques'})
            members.filter.assert_called_once_with(discordUserId__in={'oauth-1', 'oauth-3'})
            self.assertEqual(plans.filter.call_args.kwargs['status'], 1)
            self.assertEqual(plans.filter.call_args.kwargs['subscriptionPlan__startswith'], 'colaborador-')


if __name__ == '__main__' and '--isolated' in sys.argv:
    # Apply only the new schema migration plus the minimum auth/profile tables in memory.
    with connection.schema_editor() as editor:
        for model in (ContentType, Permission, Group, get_user_model(), UserProfile):
            editor.create_model(model)
        state = ProjectState.from_apps(apps)
        for name in ('tbperfilcomentariocurtida', 'tbperfilcomentario'):
            state.remove_model('home', name)
        migration = importlib.import_module('home.migrations.0166_profile_comments').Migration('0166_profile_comments', 'home')
        for operation in migration.operations:
            before = state.clone()
            operation.state_forwards('home', state)
            operation.database_forwards('home', editor, before, state)
    unittest.main(argv=[sys.argv[0]], verbosity=2)
