"""Campos assistidos para os critérios automáticos já avaliados pelo site."""
from django import forms

from .conquistas import QUEST_CATEGORIES, identidades_itens_ausentes
from .models import TbClasse, TbConquista


METRICAS = (
    ('', 'Editar JSON diretamente'),
    ('characters_created', 'Primeira ficha real'),
    ('stories_published', 'Primeira Crônica publicada'),
    ('items_purchased', 'Primeira compra de item'),
    ('class_started', 'Início de classe no nível 1'),
    ('items_purchased_units', 'Unidades de itens compradas'),
    ('adventures_played', 'Aventuras de mesa comprovadas'),
    ('character_level', 'Nível atual por classe principal'),
    ('quests_completed', 'Primeira quest categorizada e comprovada'),
)
CATALOGOS = {'mundano', 'magico', 'oficina', 'comunidade'}


class ConquistaAdminForm(forms.ModelForm):
    metrica_assistida = forms.ChoiceField(
        choices=METRICAS, required=False,
        help_text='Selecione uma métrica para gerar o critério validado. Em branco, edite o JSON diretamente.',
    )
    classe_inicial = forms.ModelChoiceField(
        queryset=TbClasse.objects.all().order_by('nome'), required=False,
        help_text='Obrigatória apenas para Início de classe.',
    )
    categoria_quest = forms.ChoiceField(
        choices=[('', 'Selecione a categoria')] + list(QUEST_CATEGORIES.items()),
        required=False, help_text='Categoria confirmada pela staff no lançamento da missão.',
    )
    itens_comprados = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Para unidades compradas, uma identidade por linha: catalogo:ID. '
                  'Catálogos: mundano, magico, oficina (ID da magia) e comunidade (ID do anúncio).',
    )
    operador_unidades = forms.ChoiceField(
        choices=(('gte', 'Pelo menos'), ('gt', 'Mais que')),
        required=False, initial='gte', label='Operador (unidades ou aventuras)',
    )
    alvo_unidades = forms.IntegerField(required=False, min_value=1,
                                       label='Limiar (unidades ou aventuras)',
                                       help_text='Limiar positivo definido pelo PO antes da ativação.')
    classe_nivel = forms.ModelChoiceField(
        queryset=TbClasse.objects.all().order_by('nome'), required=False,
        label='Classe principal (nível)',
    )
    alvo_nivel = forms.IntegerField(required=False, min_value=2, max_value=20,
                                    label='Nível mínimo',
                                    help_text='Escolha o marco com o PO antes da ativação.')
    classe_unica = forms.BooleanField(
        required=False, label='Nível 20 sem multiclasse',
        help_text='Exige uma única classe desde a criação da ficha, comprovada pelo histórico.',
    )

    class Meta:
        model = TbConquista
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound or not self.instance.pk:
            return
        rule = self.instance.criterio_json or {}
        metric = rule.get('metric')
        if metric not in dict(METRICAS):
            return
        if metric == 'class_started':
            slug = (rule.get('filters') or {}).get('class_slug')
            self.fields['classe_inicial'].initial = TbClasse.objects.filter(slug=slug).first()
        elif metric == 'character_level':
            slug = (rule.get('filters') or {}).get('class_slug')
            self.fields['classe_nivel'].initial = TbClasse.objects.filter(slug=slug).first()
            self.fields['alvo_nivel'].initial = rule.get('target')
            self.fields['classe_unica'].initial = (rule.get('filters') or {}).get('single_class', False)
        elif metric == 'quests_completed':
            self.fields['categoria_quest'].initial = (rule.get('filters') or {}).get('category')
        elif metric in ('items_purchased_units', 'adventures_played'):
            if metric == 'items_purchased_units':
                items = (rule.get('filters') or {}).get('items') or []
                self.fields['itens_comprados'].initial = '\n'.join(
                    f"{item['catalog']}:{item['id']}" for item in items
                    if isinstance(item, dict) and {'catalog', 'id'} <= set(item))
            self.fields['operador_unidades'].initial = rule.get('operator', 'gte')
            self.fields['alvo_unidades'].initial = rule.get('target')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('criterio') != 'automatico':
            return cleaned
        metric = cleaned.get('metrica_assistida')
        if not metric:
            return cleaned
        rule = {'schema_version': 1, 'metric': metric, 'scope': 'account'}
        if metric == 'class_started':
            classe = cleaned.get('classe_inicial')
            if classe is None:
                self.add_error('classe_inicial', 'Selecione uma classe real.')
                return cleaned
            rule.update(filters={'class_slug': classe.slug}, operator='gte', target=1)
        elif metric == 'character_level':
            classe = cleaned.get('classe_nivel')
            target = cleaned.get('alvo_nivel')
            if classe is None:
                self.add_error('classe_nivel', 'Selecione uma classe real.')
            if target is None:
                self.add_error('alvo_nivel', 'Informe o nível definido pelo PO.')
            if cleaned.get('classe_unica') and target != 20:
                self.add_error('classe_unica', 'Sem multiclasse só é válido para o marco de nível 20.')
            if self.errors:
                return cleaned
            filters = {'class_slug': classe.slug}
            if cleaned.get('classe_unica'):
                filters['single_class'] = True
            rule.update(filters=filters,
                        operator='gte', target=target)
        elif metric == 'quests_completed':
            category = cleaned.get('categoria_quest')
            if not category:
                self.add_error('categoria_quest', 'Selecione uma categoria confirmável.')
                return cleaned
            rule.update(filters={'category': category, 'valid': True},
                        operator='gte', target=1)
        elif metric == 'items_purchased_units':
            items = []
            for line in (cleaned.get('itens_comprados') or '').splitlines():
                line = line.strip()
                if not line:
                    continue
                catalog, separator, item_id = line.partition(':')
                if (not separator or catalog not in CATALOGOS or
                        not item_id.isdecimal() or int(item_id) <= 0):
                    self.add_error('itens_comprados', f'Identidade inválida: {line}')
                    return cleaned
                items.append({'catalog': catalog, 'id': int(item_id)})
            if not items or len(items) > 100 or len({(i['catalog'], i['id']) for i in items}) != len(items):
                self.add_error('itens_comprados', 'Informe de 1 a 100 identidades distintas.')
            if items and not self.errors:
                missing = identidades_itens_ausentes(items)
                if missing:
                    self.add_error('itens_comprados',
                                   'Identidades não encontradas: ' + ', '.join(missing))
            if cleaned.get('alvo_unidades') is None:
                self.add_error('alvo_unidades', 'Informe o limiar definido pelo PO.')
            if not cleaned.get('operador_unidades'):
                self.add_error('operador_unidades', 'Escolha o operador definido pelo PO.')
            if self.errors:
                return cleaned
            rule.update(aggregate='sum', filters={'items': items},
                        operator=cleaned['operador_unidades'],
                        target=cleaned['alvo_unidades'])
        elif metric == 'adventures_played':
            if cleaned.get('alvo_unidades') is None:
                self.add_error('alvo_unidades', 'Informe o limiar definido pelo PO.')
            if not cleaned.get('operador_unidades'):
                self.add_error('operador_unidades', 'Escolha o operador definido pelo PO.')
            if self.errors:
                return cleaned
            rule.update(aggregate='sum', filters={'valid': True, 'origin': 'played_session'},
                        operator=cleaned['operador_unidades'],
                        target=cleaned['alvo_unidades'])
        else:
            rule.update(operator='gte', target=1)
        cleaned['criterio_json'] = rule
        return cleaned
