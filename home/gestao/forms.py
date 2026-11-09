from django import forms

from home.models import TbCosmetico
from .roles import ROLE_NAMES


class PeopleSearchForm(forms.Form):
    q = forms.CharField(
        label='Buscar pessoa', required=False, max_length=150,
        widget=forms.TextInput(attrs={'type': 'search', 'autocomplete': 'off'}),
    )


class CosmeticCatalogFilterForm(forms.Form):
    q = forms.CharField(
        label='Buscar cosmético', required=False, max_length=150,
        widget=forms.TextInput(attrs={'type': 'search', 'autocomplete': 'off'}),
    )
    type = forms.ChoiceField(
        label='Tipo', required=False,
        choices=[('', 'Todos os tipos'), *TbCosmetico.TIPO_CHOICES],
    )


class ManualGrantForm(forms.Form):
    cosmetic_id = forms.IntegerField(
        label='Cosmético', min_value=1, widget=forms.HiddenInput,
        error_messages={'required': 'Selecione um cosmético no catálogo.'},
    )
    reason = forms.CharField(
        label='Motivo da concessão', min_length=5, max_length=500,
        widget=forms.Textarea(attrs={'rows': 4, 'maxlength': 500}),
        error_messages={
            'required': 'Informe o motivo da concessão.',
            'min_length': 'O motivo deve ter pelo menos 5 caracteres.',
            'max_length': 'O motivo deve ter no máximo 500 caracteres.',
        },
    )


class GrantConfirmationForm(forms.Form):
    ticket = forms.CharField(max_length=8192, widget=forms.HiddenInput,
                             error_messages={'required': 'Confira uma nova prévia antes de confirmar.'})


class RoleAssignmentForm(forms.Form):
    roles = forms.MultipleChoiceField(label='Cargos', required=False,
        choices=[(name, name) for name in ROLE_NAMES], widget=forms.CheckboxSelectMultiple)
    reason = forms.CharField(label='Motivo da alteração', min_length=5, max_length=500,
                             widget=forms.Textarea(attrs={'rows': 3}))
