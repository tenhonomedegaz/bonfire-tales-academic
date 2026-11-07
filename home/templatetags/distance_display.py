"""Presentation filters for rules that include physical distances."""
from django import template
from home.distance_presentation import distance_text
from home.rules_terminology import rules_terms

register = template.Library()


@register.filter
def dual_distance(value):
    return rules_terms(distance_text(value))


register.filter('rules_terms', rules_terms)
