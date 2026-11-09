"""Workflow vocabulary adapted from Meagea/portal_bonfire workflow-config.json."""
QUEUES = {
    'ficha': ('Correções de ficha', 'Correção de ficha', 'st'),
    'ticket': ('Tickets de suporte', 'Ticket de suporte', 'st'),
    'historia': ('Histórias de personagens', 'História de personagem', 'lo'),
    'desenvolvimento': ('Bugs e melhorias', 'Solicitação técnica', 'de'),
    'regras': ('Dúvidas e pareceres', 'Solicitação sobre regras', 'ru'),
    'midia': ('Pedidos de mídia', 'Solicitação de mídia', 'me'),
}
STATUSES = [('new', 'Nova'), ('reviewing', 'Em atendimento'),
            ('waiting', 'Aguardando solicitante'), ('done', 'Concluída'),
            ('rejected', 'Recusada')]
ACTION_LABELS = {'create': 'Solicitação aberta', 'comment': 'Comentário',
                 'training': 'Treinamento comprovado registrado',
                 'profile': 'Dados da ficha corrigidos',
                 'start': 'Atendimento iniciado', 'return': 'Ajustes solicitados',
                 'finish': 'Concluída', 'reject': 'Recusada',
                 'resubmit': 'Reenviada', 'reopen': 'Reaberta'}


def can_review(user, queue):
    return bool(queue in QUEUES and user.is_authenticated and user.is_active
                and (user.is_superuser or user.has_perm('home.review_portal_' + queue)))


def review_queues(user):
    return [key for key in QUEUES if can_review(user, key)]


def allowed_actions(user, task):
    operator = can_review(user, task.queue)
    own = user.pk == task.requester_id
    actions = []
    if own or operator:
        actions.append('comment')
    if operator and task.status == 'new':
        actions += ['start', 'reject']
    if operator and task.status == 'reviewing' and task.assignee_id in (None, user.pk):
        actions += ['return', 'finish', 'reject']
    if operator and task.status in ('done', 'rejected'):
        actions.append('reopen')
    if own and task.status == 'waiting':
        actions.append('resubmit')
    return actions
