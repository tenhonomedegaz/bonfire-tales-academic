"""Opt-in visual QA of full achievement profiles against Django and PostgreSQL."""
import os
import shutil
import subprocess
import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

from home.conquistas import conceder_conquista
from home.models import TbConquista


@unittest.skipUnless(os.environ.get("BONFIRE_PLAYWRIGHT_MODULE"),
                     "Visual E2E requires BONFIRE_PLAYWRIGHT_MODULE.")
class AchievementProfileVisualE2ETests(StaticLiveServerTestCase):
    def test_full_owner_and_public_profiles(self):
        if connection.vendor != "postgresql" or not connection.settings_dict["NAME"].startswith("test_"):
            self.skipTest("Visual E2E requires an isolated PostgreSQL test database.")
        owner = get_user_model().objects.create_user(
            "achievement-visual-owner", password="visual-test-only")
        earned = TbConquista.objects.create(
            slug="visual-earned", nome="Jornada Iniciada", descricao="Primeiro feito confirmado.",
            criterio="manual")
        TbConquista.objects.create(
            slug="visual-locked", nome="Jornada Seguinte", descricao="Siga em frente.",
            criterio="manual")
        self.assertTrue(conceder_conquista(owner, earned))
        self.client.force_login(owner)
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required for visual E2E.")
        env = dict(os.environ,
                   ACHIEVEMENT_E2E_BASE_URL=self.live_server_url,
                   ACHIEVEMENT_E2E_OWNER_PATH=reverse("profile"),
                   ACHIEVEMENT_E2E_PUBLIC_PATH=reverse("public_profile", args=[owner.username]),
                   ACHIEVEMENT_E2E_INBOX_PATH=reverse("conquista_notificacoes"),
                   ACHIEVEMENT_E2E_COOKIE_NAME=settings.SESSION_COOKIE_NAME,
                   ACHIEVEMENT_E2E_COOKIE_VALUE=self.client.cookies[settings.SESSION_COOKIE_NAME].value)
        script = os.path.join(os.path.dirname(__file__), "js_tests", "achievement_profile.e2e.cjs")
        completed = subprocess.run(
            [node, script], cwd=os.path.dirname(os.path.dirname(__file__)), env=env,
            text=True, encoding="utf-8", capture_output=True, timeout=120, check=False)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
