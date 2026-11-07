"""One nonblank email per account, with the same normalization as the DB index."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower, Trim


def normalized_email(value):
    return str(value or '').strip().lower()


def email_accounts(value):
    email = normalized_email(value)
    return get_user_model().objects.annotate(normalized_address=Lower(Trim('email'))).filter(normalized_address=email)


def available_email(value, user_id=None):
    email = normalized_email(value)
    if email and email_accounts(email).exclude(pk=user_id).exists():
        raise ValidationError('Este e-mail já pertence a outra conta. Entre nela ou recupere a senha.')
    return email


def account_email_audit(payload, api_key):
    import hashlib
    import json
    from django.db import connection
    from django.db.models import Count, Sum
    from django.core.exceptions import PermissionDenied
    from .db_access import ApiProblem
    from .master_legacy import require_admin
    from .models import TbPersonagem, UserProfile, UserAccountMergeReceipt
    try:
        require_admin(getattr(api_key, 'created_by', None))
    except PermissionDenied:
        raise ApiProblem(403, 'superuser_key_required', 'Auditoria exige superusuario ativo.') from None
    if payload != {}:
        raise ApiProblem(400, 'invalid_email_audit', 'Esta consulta nao recebe filtros.')
    User = get_user_model()
    groups = User.objects.annotate(address=Lower(Trim('email'))).exclude(address='').values('address').annotate(n=Count('pk')).filter(n__gt=1)
    owners = list(TbPersonagem.objects.order_by('pk').values_list('pk', 'dono_id'))
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, User._meta.db_table)
    return {'accounts': User.objects.count(), 'duplicate_groups': groups.count(),
            'unique_index': bool(constraints.get('auth_user_email_normalized_unique', {}).get('unique')),
            'characters': len(owners),
            'character_owners_sha256': hashlib.sha256(json.dumps(owners, separators=(',', ':')).encode()).hexdigest(),
            'wallet_totals': UserProfile.objects.aggregate(mm=Sum('moedas_mestragem'), events=Sum('moedas_evento')),
            'merge_count': UserAccountMergeReceipt.objects.count(),
            'merges': list(UserAccountMergeReceipt.objects.order_by('pk').values(
                'removed_user_id', 'removed_username', 'keeper_id', 'keeper__username')[:50])}
