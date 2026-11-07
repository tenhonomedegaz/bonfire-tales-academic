# -*- coding: utf-8 -*-
"""Regras persistentes dos servicos financeiros do Mercado."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone


TRAINING_COST_PC = 10000
SERVICE_MONTH = timedelta(days=30)
OVERDUE_TOTAL_PERCENT = 120
LOAN_LIMITS_PO = {
    'Obsidiana': 600,
    'Ametista': 1250,
    'Topazio': 2000,
    'Esmeralda': 4250,
    'Ambar': 5000,
    'Rubi': 6000,
    'Diamante': 8000,
    'Lenda': 8000,
}


def _ascii(value):
    import unicodedata
    return unicodedata.normalize('NFKD', str(value or '')).encode(
        'ascii', 'ignore').decode('ascii')


def loan_rank(personagem):
    from .character_engine import nivel_por_aventuras, rank_por_nivel
    return rank_por_nivel(nivel_por_aventuras(personagem.aventuras))


def loan_limit_pc(personagem):
    return LOAN_LIMITS_PO.get(_ascii(loan_rank(personagem)), 0) * 100


def tables_played(personagem):
    """Conta mesas auditadas; personagens legados usam aventuras como fallback."""
    ledger = personagem.aventuras_ledger.filter(
        revertido=False).exclude(origem='recompensa_comunidade')
    if personagem.aventuras_ledger.exclude(origem='recompensa_comunidade').exists():
        return ledger.count()
    community = personagem.aventuras_ledger.filter(
        revertido=False, origem='recompensa_comunidade').aggregate(
            total=Sum('qtd_aventuras'))['total'] or 0
    return max(0, int(personagem.aventuras or 0) - int(community))


def sync_training(personagem, *, now=None):
    """Conclui treinamentos vencidos e credita a proficiencia uma unica vez."""
    from .models import (
        TbPersonagemProficiencia, TbPersonagemTreinamento,
    )
    now = now or timezone.now()
    completed = []
    with transaction.atomic():
        due = list(TbPersonagemTreinamento.objects.select_for_update().filter(
            id_personagem=personagem, status='ativo', conclui_em__lte=now))
        for row in due:
            TbPersonagemProficiencia.objects.get_or_create(
                id_personagem=personagem, tipo=row.tipo, nome__iexact=row.nome,
                defaults={'nome': row.nome, 'origem': 'Treinamento'})
            row.status = 'concluido'
            row.concluido_em = now
            row.save(update_fields=['status', 'concluido_em'])
            completed.append(row)
    return completed


def start_training(personagem, token):
    from .models import (
        TbIdioma, TbItemMundano, TbPersonagem, TbPersonagemTreinamento,
    )
    tipo, sep, slug = str(token or '').partition(':')
    if not sep or tipo not in {'idioma', 'ferramenta'} or not slug:
        return None, 'treinamento_invalido'
    catalog = (TbIdioma.objects.filter(slug=slug).first() if tipo == 'idioma'
               else TbItemMundano.objects.filter(
                   slug=slug, categoria='ferramenta').first())
    if catalog is None:
        return None, 'treinamento_invalido'

    now = timezone.now()
    with transaction.atomic():
        personagem = TbPersonagem.objects.select_for_update().get(pk=personagem.pk)
        sync_training(personagem, now=now)
        if TbPersonagemTreinamento.objects.filter(
                id_personagem=personagem, status='ativo').exists():
            return None, 'treinamento_ativo'
        if personagem.proficiencias.filter(
                tipo=tipo, nome__iexact=catalog.nome).exists():
            return None, 'treinamento_conhecido'
        if int(personagem.carteira_pc or 0) < TRAINING_COST_PC:
            return None, 'saldo'
        personagem.carteira_pc = int(personagem.carteira_pc or 0) - TRAINING_COST_PC
        personagem.save(update_fields=['carteira_pc', 'atualizado_em'])
        row = TbPersonagemTreinamento.objects.create(
            id_personagem=personagem, tipo=tipo, nome=catalog.nome,
            custo_pc=TRAINING_COST_PC, conclui_em=now + SERVICE_MONTH)
        register_transaction(
            personagem, 'treinamento', 'Treinamento: %s' % catalog.nome,
            -TRAINING_COST_PC,
            {'treinamento_id': row.pk, 'tipo': tipo, 'conclui_em': row.conclui_em.isoformat()})
    return row, 'treinamento_iniciado'


def sync_overdue_loans(*, personagem=None, now=None):
    """Aplica uma unica multa de 20% sobre o valor original do contrato."""
    from .models import TbEmprestimoPersonagem
    now = now or timezone.now()
    query = TbEmprestimoPersonagem.objects.filter(
        status='ativo', multa_aplicada=False, vence_em__lt=now)
    if personagem is not None:
        query = query.filter(Q(credor=personagem) | Q(devedor=personagem))
    with transaction.atomic():
        for loan in query.select_for_update():
            previous_total = int(loan.valor_total_pc or 0)
            loan.valor_total_pc = (
                int(loan.valor_original_pc) * OVERDUE_TOTAL_PERCENT + 99) // 100
            loan.multa_aplicada = True
            loan.save(update_fields=['valor_total_pc', 'multa_aplicada'])
            _record_only(
                loan.devedor, 'ajuste', 'Multa de 20% por emprestimo vencido', 0,
                {
                    'emprestimo_id': loan.pk,
                    'valor_total_anterior_pc': previous_total,
                    'valor_total_atual_pc': loan.valor_total_pc,
                    'base_da_multa_pc': loan.valor_original_pc,
                })


def active_loan_for(personagem):
    from .models import TbEmprestimoPersonagem
    sync_overdue_loans(personagem=personagem)
    return TbEmprestimoPersonagem.objects.filter(
        Q(credor=personagem) | Q(devedor=personagem), status='ativo').select_related(
            'credor__dono', 'devedor__dono', 'proponente__dono').first()


def _record_only(personagem, tipo, descricao, delta_pc, detalhes=None):
    from .models import TbTransacao
    payload = dict(detalhes or {})
    payload.setdefault('aventuras_no_momento', int(personagem.aventuras or 0))
    return TbTransacao.objects.create(
        id_personagem=personagem, tipo=tipo, descricao=(descricao or '')[:255],
        valor_pc=int(delta_pc), saldo_pc=int(personagem.carteira_pc or 0),
        detalhes_json=payload)


def _garnish_overdue_income(personagem, received_pc, source_transaction):
    """Repassa renda nova ao credor enquanto houver divida vencida."""
    from .models import TbEmprestimoPersonagem, TbPersonagem
    sync_overdue_loans(personagem=personagem)
    with transaction.atomic():
        loan = TbEmprestimoPersonagem.objects.select_for_update().filter(
            devedor=personagem, status='ativo', multa_aplicada=True).first()
        if not loan:
            return 0
        people = {
            row.pk: row for row in TbPersonagem.objects.select_for_update().filter(
                pk__in=(loan.devedor_id, loan.credor_id)).order_by('pk')
        }
        debtor, creditor = people[loan.devedor_id], people[loan.credor_id]
        amount = min(int(received_pc), loan.saldo_devedor_pc,
                     int(debtor.carteira_pc or 0))
        if amount <= 0:
            return 0
        debtor.carteira_pc = int(debtor.carteira_pc or 0) - amount
        creditor.carteira_pc = int(creditor.carteira_pc or 0) + amount
        debtor.save(update_fields=['carteira_pc', 'atualizado_em'])
        creditor.save(update_fields=['carteira_pc', 'atualizado_em'])
        loan.valor_pago_pc = int(loan.valor_pago_pc or 0) + amount
        if loan.saldo_devedor_pc == 0:
            loan.status = 'quitado'
            loan.encerrado_em = timezone.now()
        loan.save(update_fields=['valor_pago_pc', 'status', 'encerrado_em'])
        details = {'emprestimo_id': loan.pk, 'origem_transacao': source_transaction.pk}
        _record_only(
            debtor, 'repasse-divida', 'Repasse automatico de renda ao credor',
            -amount, details)
        _record_only(
            creditor, 'repasse-divida', 'Recebimento automatico de divida',
            amount, details)
        personagem.carteira_pc = debtor.carteira_pc
        return amount


def register_transaction(personagem, tipo, descricao, delta_pc, detalhes=None):
    """Registra uma movimentacao e aplica a retencao de renda vencida."""
    if tipo in {'compra', 'mercado-compra'} and int(delta_pc) < 0:
        from .conquistas import registrar_fato_compra
        with transaction.atomic():
            row = _record_only(personagem, tipo, descricao, delta_pc, detalhes)
            registrar_fato_compra(row)
        return row
    row = _record_only(personagem, tipo, descricao, delta_pc, detalhes)
    if int(delta_pc) > 0 and tipo != 'repasse-divida':
        _garnish_overdue_income(personagem, int(delta_pc), row)
    return row


def create_loan_proposal(proponent, other, role, amount_pc):
    from .models import TbEmprestimoPersonagem
    if proponent.pk == other.pk or proponent.dono_id == other.dono_id:
        return None, 'emprestimo_alvo'
    if tables_played(proponent) < 2 or tables_played(other) < 2:
        return None, 'emprestimo_mesas'
    creditor, debtor = ((proponent, other) if role == 'oferecer'
                        else (other, proponent))
    amount_pc = int(amount_pc or 0)
    if amount_pc <= 0 or amount_pc > loan_limit_pc(debtor):
        return None, 'emprestimo_limite'
    if active_loan_for(proponent) or active_loan_for(other):
        return None, 'emprestimo_ativo'
    duplicate = TbEmprestimoPersonagem.objects.filter(
        credor=creditor, devedor=debtor, status='pendente').first()
    if duplicate:
        return duplicate, 'emprestimo_pendente'
    row = TbEmprestimoPersonagem.objects.create(
        credor=creditor, devedor=debtor, proponente=proponent,
        valor_original_pc=amount_pc, valor_total_pc=amount_pc)
    return row, 'emprestimo_solicitado'


def respond_loan(user, loan_id, action):
    from .models import TbEmprestimoPersonagem, TbPersonagem
    with transaction.atomic():
        loan = TbEmprestimoPersonagem.objects.select_for_update().select_related(
            'credor', 'devedor', 'proponente').filter(pk=loan_id).first()
        if not loan or loan.status != 'pendente':
            return None, 'emprestimo_invalido'
        recipient = loan.devedor if loan.proponente_id == loan.credor_id else loan.credor
        if recipient.dono_id != user.id:
            return None, 'emprestimo_invalido'
        if action == 'recusar':
            loan.status = 'recusado'
            loan.encerrado_em = timezone.now()
            loan.save(update_fields=['status', 'encerrado_em'])
            return loan, 'emprestimo_recusado'
        if action != 'aceitar':
            return None, 'emprestimo_invalido'
        people = {
            row.pk: row for row in TbPersonagem.objects.select_for_update().filter(
                pk__in=(loan.credor_id, loan.devedor_id)).order_by('pk')
        }
        creditor, debtor = people[loan.credor_id], people[loan.devedor_id]
        if (active_loan_for(creditor) or active_loan_for(debtor)):
            return None, 'emprestimo_ativo'
        if tables_played(creditor) < 2 or tables_played(debtor) < 2:
            return None, 'emprestimo_mesas'
        if int(loan.valor_original_pc) > loan_limit_pc(debtor):
            return None, 'emprestimo_limite'
        if int(creditor.carteira_pc or 0) < int(loan.valor_original_pc):
            return None, 'emprestimo_saldo_credor'
        amount = int(loan.valor_original_pc)
        creditor.carteira_pc = int(creditor.carteira_pc or 0) - amount
        debtor.carteira_pc = int(debtor.carteira_pc or 0) + amount
        creditor.save(update_fields=['carteira_pc', 'atualizado_em'])
        debtor.save(update_fields=['carteira_pc', 'atualizado_em'])
        loan.status = 'ativo'
        loan.aceito_em = timezone.now()
        loan.vence_em = loan.aceito_em + SERVICE_MONTH
        loan.save(update_fields=['status', 'aceito_em', 'vence_em'])
        details = {'emprestimo_id': loan.pk, 'contraparte_id': debtor.pk}
        register_transaction(
            creditor, 'emprestimo', 'Emprestimo concedido a %s' % debtor.nome,
            -amount, details)
        details = {'emprestimo_id': loan.pk, 'contraparte_id': creditor.pk}
        register_transaction(
            debtor, 'emprestimo', 'Emprestimo recebido de %s' % creditor.nome,
            amount, details)
        return loan, 'emprestimo_aceito'


def cancel_loan_proposal(user, loan_id):
    from .models import TbEmprestimoPersonagem
    loan = TbEmprestimoPersonagem.objects.filter(
        pk=loan_id, status='pendente', proponente__dono=user).first()
    if not loan:
        return None, 'emprestimo_invalido'
    loan.status = 'cancelado'
    loan.encerrado_em = timezone.now()
    loan.save(update_fields=['status', 'encerrado_em'])
    return loan, 'emprestimo_cancelado'


def staff_manage_loan(staff_user, loan_id, action):
    """Permite reconciliar contratos sem tentar gerenciar cargos do Discord."""
    from .models import TbEmprestimoPersonagem

    sync_overdue_loans(now=timezone.now())
    with transaction.atomic():
        loan = TbEmprestimoPersonagem.objects.select_for_update().select_related(
            'credor', 'devedor').filter(pk=loan_id).first()
        if not loan or loan.status not in {'pendente', 'ativo'}:
            return None, 'emprestimo_invalido'

        now = timezone.now()
        if action == 'cancelar' and loan.status == 'pendente':
            loan.status = 'cancelado'
            loan.encerrado_em = now
            status = 'emprestimo_staff_cancelado'
            fields = ['status', 'encerrado_em']
        elif (action == 'prorrogar' and loan.status == 'ativo'
              and not loan.multa_aplicada):
            loan.vence_em = max(loan.vence_em or now, now) + SERVICE_MONTH
            status = 'emprestimo_staff_prorrogado'
            fields = ['vence_em']
        elif action == 'quitar' and loan.status == 'ativo':
            loan.valor_pago_pc = int(loan.valor_total_pc or 0)
            loan.status = 'quitado'
            loan.encerrado_em = now
            status = 'emprestimo_staff_quitado'
            fields = ['valor_pago_pc', 'status', 'encerrado_em']
        else:
            return loan, 'emprestimo_invalido'

        loan.save(update_fields=fields)
        details = {
            'emprestimo_id': loan.pk,
            'operacao_staff': action,
            'staff_user_id': staff_user.pk,
            'staff_username': staff_user.get_username(),
        }
        for personagem in (loan.credor, loan.devedor):
            _record_only(
                personagem, 'ajuste',
                'Emprestimo #%s ajustado pela staff: %s' % (loan.pk, action),
                0, details)
        return loan, status


def pay_loan(user, loan_id, amount_pc=None):
    from .models import TbEmprestimoPersonagem, TbPersonagem
    sync_overdue_loans(now=timezone.now())
    with transaction.atomic():
        loan = TbEmprestimoPersonagem.objects.select_for_update().filter(
            pk=loan_id, status='ativo', devedor__dono=user).first()
        if not loan:
            return None, 'emprestimo_invalido'
        people = {
            row.pk: row for row in TbPersonagem.objects.select_for_update().filter(
                pk__in=(loan.credor_id, loan.devedor_id)).order_by('pk')
        }
        debtor, creditor = people[loan.devedor_id], people[loan.credor_id]
        requested = loan.saldo_devedor_pc if amount_pc is None else int(amount_pc)
        amount = min(max(0, requested), loan.saldo_devedor_pc)
        if amount <= 0:
            return None, 'emprestimo_valor'
        if int(debtor.carteira_pc or 0) < amount:
            return None, 'saldo'
        debtor.carteira_pc = int(debtor.carteira_pc or 0) - amount
        creditor.carteira_pc = int(creditor.carteira_pc or 0) + amount
        debtor.save(update_fields=['carteira_pc', 'atualizado_em'])
        creditor.save(update_fields=['carteira_pc', 'atualizado_em'])
        loan.valor_pago_pc = int(loan.valor_pago_pc or 0) + amount
        if loan.saldo_devedor_pc == 0:
            loan.status = 'quitado'
            loan.encerrado_em = timezone.now()
        loan.save(update_fields=['valor_pago_pc', 'status', 'encerrado_em'])
        details = {'emprestimo_id': loan.pk, 'contraparte_id': creditor.pk}
        register_transaction(
            debtor, 'emprestimo', 'Pagamento de emprestimo a %s' % creditor.nome,
            -amount, details)
        details = {'emprestimo_id': loan.pk, 'contraparte_id': debtor.pk}
        register_transaction(
            creditor, 'emprestimo', 'Pagamento recebido de %s' % debtor.nome,
            amount, details)
        return loan, ('emprestimo_quitado' if loan.status == 'quitado'
                      else 'emprestimo_pago')
