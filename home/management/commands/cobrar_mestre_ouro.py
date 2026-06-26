# -*- coding: utf-8 -*-
"""Cobrança mensal do Mestre Ouro (500 MM). Rode periodicamente (ex.: cron diário):

    manage.py cobrar_mestre_ouro

Cobra a mensalidade dos perfis com Mestre Ouro ativo cujo `mestre_ouro_proximo_pgto`
já venceu. Quem não tem MM suficiente PERDE a assinatura (e, por consequência, o 5º slot
— se tiver 5 personagens ativos, um deles passa a exceder o limite até ser arquivado)."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from home.models import UserProfile, TbRecompensaMestre
from home import views


class Command(BaseCommand):
    help = 'Cobra a mensalidade (MM) dos Mestres Ouro com pagamento vencido; desativa quem nao pode pagar.'

    def handle(self, *args, **options):
        hoje = timezone.now().date()
        assinatura = TbRecompensaMestre.objects.filter(tipo='assinatura').first()
        mensalidade = assinatura.mensalidade_mm if assinatura else 500
        cobrados = desativados = 0
        qs = UserProfile.objects.filter(mestre_ouro_ativo=True,
                                        mestre_ouro_proximo_pgto__isnull=False,
                                        mestre_ouro_proximo_pgto__lte=hoje)
        for perfil in qs:
            if (perfil.moedas_mestragem or 0) >= mensalidade:
                views._creditar_mm(perfil.user, 'mensalidade', 'Mestre Ouro (cobranca automatica)', -mensalidade)
                perfil.mestre_ouro_proximo_pgto = (perfil.mestre_ouro_proximo_pgto or hoje) + timedelta(days=30)
                perfil.save(update_fields=['mestre_ouro_proximo_pgto'])
                cobrados += 1
            else:
                perfil.mestre_ouro_ativo = False
                perfil.save(update_fields=['mestre_ouro_ativo'])
                desativados += 1
        self.stdout.write(self.style.SUCCESS('Mestre Ouro — cobrados: %d | desativados: %d' % (cobrados, desativados)))
