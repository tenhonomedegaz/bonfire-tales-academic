"""Q17: contrato da rota pública com os dois catálogos persistidos."""
from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse

from home.models import TbCondicao, TbRegra


class GlossarioIndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.terms = {}
        self.count = ""
        self.reading_count = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "article" and "glo-item" in values.get("class", "").split():
            self.terms[values["id"]] = values.get("data-busca", "")
        if values.get("id") == "glo-count":
            self.reading_count = True

    def handle_data(self, data):
        if self.reading_count:
            self.count += data

    def handle_endtag(self, tag):
        if tag == "span":
            self.reading_count = False


class GlossarioRouteTests(TestCase):
    def test_visitante_recebe_regras_condicoes_e_contagem_do_mesmo_indice(self):
        TbRegra.objects.create(slug="q17-acao", nome="Ação", nome_en="Action")
        TbCondicao.objects.create(
            slug="q17-impedido", nome="Impedido", nome_en="Restrained",
            efeitos_json=[{"titulo": "Movimento", "texto": "Deslocamento zero."}],
        )
        response = self.client.get(reverse("sistemas_glossario"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deslocamento zero.")
        index = GlossarioIndexParser()
        index.feed(response.content.decode("utf-8"))
        self.assertEqual(index.terms["regra-q17-acao"], "ação action")
        self.assertEqual(index.terms["condicao-q17-impedido"], "impedido restrained")
        self.assertEqual(int(index.count), TbRegra.objects.count() + TbCondicao.objects.count())
        self.assertEqual(len(index.terms), int(index.count))

    def test_rotulos_com_aspas_nao_criam_atributos_html(self):
        TbCondicao.objects.create(
            slug="q17-aspas", nome='Condição "especial"', nome_en='Quoted <condition>',
        )
        response = self.client.get(reverse("sistemas_glossario"))
        self.assertEqual(response.status_code, 200)
        index = GlossarioIndexParser()
        index.feed(response.content.decode("utf-8"))
        self.assertEqual(index.terms["condicao-q17-aspas"], 'condição "especial" quoted <condition>')
