from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ResponsiveShellTests(SimpleTestCase):
    def test_responsive_layer_loads_after_page_styles(self):
        template = (
            Path(settings.BASE_DIR) / "home" / "templates" / "home" / "base.html"
        ).read_text(encoding="utf-8")

        page_styles = template.index("{% block extra_head %}")
        responsive_styles = template.index("css/pages/responsive.css")

        self.assertGreater(responsive_styles, page_styles)

    def test_mobile_menu_has_stable_hooks_and_keyboard_close(self):
        template = (
            Path(settings.BASE_DIR)
            / "home"
            / "templates"
            / "home"
            / "components"
            / "header.html"
        ).read_text(encoding="utf-8")

        self.assertIn("site-mobile-menu-panel", template)
        self.assertIn("event.key === 'Escape'", template)
        self.assertIn("site-mobile-menu-open", template)

    def test_shared_mobile_contract_covers_recent_workflows(self):
        stylesheet = (
            Path(settings.BASE_DIR) / "home" / "static" / "css" / "pages" / "responsive.css"
        ).read_text(encoding="utf-8")

        for selector in (
            ".workshop-tabs",
            ".cf-stepper",
            ".pb-stepper",
            ".ficha-tabs",
            ".lvl-actionbar",
            ".mkt-preview",
            ".talent-list-panel",
            ".players-tabs",
            ".jornal-grid",
            "[data-point-buy]",
        ):
            with self.subTest(selector=selector):
                self.assertIn(selector, stylesheet)
