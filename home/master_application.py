"""Versioned private application answers, independent from public portfolios."""
import json
from pathlib import Path

from django import forms


def application_schema():
    path = Path(__file__).resolve().parent / 'content_packages/master_application_v1.json'
    return json.loads(path.read_text(encoding='utf-8'))


class MasterApplicationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.schema = application_schema()
        for question in self.schema['questions']:
            params = {'label': question['label'], 'required': question['required']}
            kind, key = question['type'], question['key']
            if kind in ('choice', 'multiple'):
                params['choices'] = [(value, value) for value in question['choices']]
                params['widget'] = forms.CheckboxSelectMultiple if kind == 'multiple' else forms.RadioSelect
                field = forms.MultipleChoiceField if kind == 'multiple' else forms.ChoiceField
            else:
                params['max_length'] = question['max_length']
                if kind == 'paragraph':
                    params['widget'] = forms.Textarea(attrs={'rows': 4})
                field = forms.CharField
            self.fields[key] = field(**params)
            if question.get('other'):
                self.fields[key + '_outro'] = forms.CharField(label='Outro estilo ou temática', required=False, max_length=200)

    def clean(self):
        data = super().clean()
        for question in self.schema['questions']:
            key = question['key']
            value = data.get(key, [])
            if question['type'] == 'multiple' and len(value) > question['max_choices']:
                self.add_error(key, f"Escolha no máximo {question['max_choices']} opções.")
            if question.get('other') and 'Outro' in value and not data.get(key + '_outro'):
                self.add_error(key + '_outro', 'Descreva o outro estilo ou temática.')
        return data

    def snapshot(self):
        if not self.is_valid():
            raise ValueError('Application must be valid before recording answers.')
        return {**self.schema, 'answers': dict(self.cleaned_data)}


def application_answers(snapshot):
    result = []
    for question in snapshot.get('questions', []):
        value = snapshot.get('answers', {}).get(question['key'], '')
        if isinstance(value, list):
            value = '\n'.join(value)
        other = snapshot.get('answers', {}).get(question['key'] + '_outro')
        result.append({'label': question['label'], 'value': value + ('\n' + other if other else '')})
    return result
