from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from home.gestao_models import ManagementRolePolicyReceipt
from .forms import GrantConfirmationForm
from .roles import ROLE_NAMES, permission_label, require_admin
from .role_policy import apply_policy, editable_permissions, preview_policy
from .views import _workspace


class RolePolicyForm(forms.Form):
    role = forms.ChoiceField(label='Cargo', choices=[(name, name) for name in ROLE_NAMES])
    permissions = forms.MultipleChoiceField(label='Tarefas permitidas', required=False,
                                             widget=forms.CheckboxSelectMultiple)
    reason = forms.CharField(label='Motivo da alteração', min_length=5, max_length=500,
                              widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['permissions'].choices = [(str(p.pk), permission_label(p)) for p in editable_permissions()]


@never_cache
@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def index(request):
    require_admin(request.user)
    role = request.GET.get('role', 'Staff')
    role = role if role in ROLE_NAMES else 'Staff'
    group = Group.objects.filter(name=role).first()
    allowed = {p.pk for p in editable_permissions()}
    selected = list(group.permissions.filter(pk__in=allowed).values_list('pk', flat=True)) if group else []
    form = RolePolicyForm(initial={'role': role, 'permissions': selected})
    preview = None
    confirmation = GrantConfirmationForm()
    if request.method == 'POST':
        if request.POST.get('action') == 'confirm':
            confirmation = GrantConfirmationForm(request.POST)
            if confirmation.is_valid():
                try:
                    receipt = apply_policy(actor=request.user, ticket=confirmation.cleaned_data['ticket'])
                    messages.success(request, 'Permissões do cargo atualizadas.')
                    return redirect(request.path + '?role=' + receipt.role_name)
                except ValidationError as exc:
                    form.add_error(None, exc)
        else:
            form = RolePolicyForm(request.POST)
            if form.is_valid():
                preview = preview_policy(actor=request.user, **form.cleaned_data)
                confirmation = GrantConfirmationForm(initial={'ticket': preview['ticket']})
    return render(request, 'home/gestao/role_policy.html', _workspace(request, 'Permissões dos cargos',
        management_section='roles', form=form, preview=preview, confirmation_form=confirmation,
        receipts=ManagementRolePolicyReceipt.objects.select_related('actor')[:10]))
