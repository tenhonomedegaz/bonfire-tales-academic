from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase

from home.models import TbMapLayer, TbRegiao
from home.views import mapa_view, regiao_detail_view


class MapaViewsRegressionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        TbMapLayer.objects.create(
            id_layer=0,
            nome="Superficie",
            imagem_url="assets/superficie.jpg",
            ordem=0,
            publica=True,
        )
        TbMapLayer.objects.create(
            id_layer=1,
            nome="Subterraneo",
            imagem_url=None,
            ordem=1,
            publica=False,
        )
        self.public_region = TbRegiao.objects.create(
            nome="Cidade Publica",
            slug="cidade-publica",
            lore_markdown="# Cidade Publica\nLore visivel para visitantes.",
            camada=0,
        )
        self.private_region = TbRegiao.objects.create(
            nome="Cidade Secreta",
            slug="cidade-secreta",
            lore_markdown="# Cidade Secreta\nLore exclusiva da staff.",
            camada=1,
        )

    def _map_context(self, user):
        request = self.factory.get("/mapa/")
        request.user = user
        with patch("home.views.render", return_value=HttpResponse("ok")) as render:
            response = mapa_view(request)
        self.assertEqual(response.status_code, 200)
        return render.call_args.args[2]

    def test_visitor_sees_only_public_layers_and_content(self):
        context = self._map_context(AnonymousUser())

        self.assertEqual([layer["id_layer"] for layer in context["json_layers"]], [0])
        self.assertEqual(
            {region["slug"] for region in context["json_regions"]},
            {self.public_region.slug},
        )

    def test_staff_sees_private_layer_and_content(self):
        context = self._map_context(User(is_staff=True))

        layer_ids = {layer["id_layer"] for layer in context["json_layers"]}
        region_slugs = {region["slug"] for region in context["json_regions"]}
        self.assertIn(1, layer_ids)
        self.assertIn(self.private_region.slug, region_slugs)

    def test_private_region_detail_is_404_for_visitor(self):
        request = self.factory.get("/mundo/regioes/cidade-secreta/")
        request.user = AnonymousUser()

        with self.assertRaises(Http404):
            regiao_detail_view(request, slug=self.private_region.slug)

    def test_private_region_detail_works_for_staff(self):
        request = self.factory.get("/mundo/regioes/cidade-secreta/")
        request.user = User(is_staff=True)

        with patch("home.views.render", return_value=HttpResponse("ok")) as render:
            response = regiao_detail_view(request, slug=self.private_region.slug)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(render.call_args.args[2]["regiao"], self.private_region)

    def test_underground_layer_without_image_uses_surface_image_as_placeholder(self):
        context = self._map_context(User(is_staff=True))
        underground = next(
            layer for layer in context["json_layers"] if layer["id_layer"] == 1
        )

        self.assertEqual(underground["imagem_url"], "/static/assets/superficie.jpg")
        self.assertTrue(underground["is_placeholder"])
