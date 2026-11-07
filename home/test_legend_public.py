"""Memorial de Lenda expõe somente a projeção editorial publicada."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from .models import TbFeitoLenda, TbPersonagem


class LegendPublicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user('legend-owner')
        cls.other = User.objects.create_user('legend-other')
        cls.person = TbPersonagem.objects.create(
            dono=cls.owner, nome='Lenda do Norte', publico=True,
            aventuras=200, descricao_publica='Legado público',
            historia='SEGREDO DA HISTORIA', anotacoes='SEGREDO DA NOTA',
        )
        TbFeitoLenda.objects.create(personagem=cls.person, titulo='Feito publicado',
                                   descricao='Vitória conhecida', publicado=True)
        TbFeitoLenda.objects.create(personagem=cls.person, titulo='Feito em rascunho',
                                   descricao='SEGREDO DO FEITO', publicado=False)

    def test_memorial_publico_e_ficha_ligados_sem_vazar_dados(self):
        url = reverse('personagem_lenda', args=[self.person.pk])
        writes = []

        def watch(execute, sql, params, many, context):
            if sql.lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')):
                writes.append(sql.split()[0])
            return execute(sql, params, many, context)

        with connection.execute_wrapper(watch):
            page = self.client.get(url)
            head = self.client.head(url)
        self.assertEqual((page.status_code, head.status_code), (200, 200))
        self.assertContains(page, 'Feito publicado')
        self.assertContains(page, 'Legado público')
        self.assertContains(page, 'index, follow')
        for secret in ('Feito em rascunho', 'SEGREDO DO FEITO',
                       'SEGREDO DA HISTORIA', 'SEGREDO DA NOTA'):
            self.assertNotContains(page, secret)
        self.assertEqual(writes, [])
        self.assertContains(self.client.get(reverse('ficha_publica', args=[self.person.pk])), url)
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_titulo_e_visibilidade_sao_obrigatorios_com_previa_so_do_dono(self):
        url = reverse('personagem_lenda', args=[self.person.pk])
        self.person.aventuras = 199
        self.person.save(update_fields=['aventuras'])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse('ficha_publica', args=[self.person.pk])),
                               'Conhecer o memorial')
        self.person.aventuras = 200
        self.person.publico = False
        self.person.save(update_fields=['aventuras', 'publico'])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(url + '?preview=1').status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url + '?preview=1').status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 404)
        preview = self.client.get(url + '?preview=1')
        self.assertContains(preview, 'noindex, nofollow')
        self.assertContains(preview, 'Feito publicado')
        self.assertContains(self.client.get(reverse('ficha_publica', args=[self.person.pk]) +
                                            '?preview=1'), url + '?preview=1')
        self.person.publico = True
        self.person.arquivado = True
        self.person.save(update_fields=['publico', 'arquivado'])
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url + '?preview=1').status_code, 200)
