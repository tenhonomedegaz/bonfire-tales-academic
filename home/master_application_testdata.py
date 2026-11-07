"""Representative answers for request-flow regression tests."""
from .master_application import application_schema


def application_data():
    return {q['key']: [q['choices'][0]] if q['type'] == 'multiple'
            else q['choices'][0] if q['type'] == 'choice' else 'Resposta de teste'
            for q in application_schema()['questions']}
