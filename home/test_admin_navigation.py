from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from home.admin_navigation import ADMIN_GROUPS, MODEL_GROUP, grouped_admin_apps


class AdminNavigationTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            "navigation-admin", "navigation@example.test", "password"
        )

    def test_groups_cover_visible_models_once_in_stable_task_order(self):
        request = RequestFactory().get(reverse("admin:index"))
        request.user = self.superuser
        source = admin.site._build_app_dict(request)
        grouped = admin.site.get_app_list(request)

        expected = sorted(
            model["object_name"]
            for app in source.values() for model in app["models"]
        )
        self.assertEqual(set(expected), set(MODEL_GROUP))
        self.assertEqual(sum(len(names) for _title, _slug, names in ADMIN_GROUPS), len(MODEL_GROUP))
        actual = sorted(
            model["object_name"]
            for group in grouped for model in group["models"]
        )
        self.assertEqual(actual, expected)
        self.assertEqual(
            [group["name"] for group in grouped],
            [title for title, _slug, _models in ADMIN_GROUPS],
        )
        self.assertEqual(
            {group["name"]: group["app_url"] for group in grouped},
            {title: reverse("admin:index") for title, _slug, _models in ADMIN_GROUPS},
        )

    def test_grouping_never_adds_a_model_not_authorized_by_admin(self):
        source = {
            "home": {"models": [
                {"object_name": "TbClasse", "name": "Classes"},
            ]},
        }
        grouped = grouped_admin_apps(source, "/admin/")
        self.assertEqual([group["name"] for group in grouped], ["Regras e conteúdo"])
        self.assertEqual(grouped[0]["models"], source["home"]["models"])

    def test_dashboard_and_sidebar_show_task_groups_and_search(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        for title, _slug, _models in ADMIN_GROUPS:
            self.assertContains(response, title)
        self.assertNotContains(response, "Tables Site")
        self.assertNotContains(response, "Tables Bot")
        self.assertContains(response, 'id="nav-filter"')
        self.assertContains(response, 'id="dashboard-search-input"')
        self.assertContains(response, 'id="dashboard-search-clear"')
        self.assertContains(response, 'id="dashboard-search-status"')
        self.assertContains(response, 'js/admin/dashboard_search.js')
        self.assertContains(response, 'css/admin/dashboard_search.css')
        self.assertContains(response, reverse("admin:home_tbclasse_changelist"))
        self.assertContains(response, "Ferramentas editoriais")
        self.assertContains(response, 'id="admin-operation-title"')
        self.assertContains(response, reverse("managed_api_key_console"))

    def test_staff_without_superuser_stays_outside_admin(self):
        staff = User.objects.create_user(
            "navigation-staff", "staff@example.test", "password", is_staff=True
        )
        self.client.force_login(staff)
        self.assertNotEqual(self.client.get(reverse("admin:index")).status_code, 200)
