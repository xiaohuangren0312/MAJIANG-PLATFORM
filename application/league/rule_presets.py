"""Built-in scoring presets shared by new events and the rule library."""
from copy import deepcopy

ML_TEMPLATE_ID = 'builtin-mleague'
ML_RULE = {'name': 'M.LEAGUE 默认计分', 'start': 25000, 'return': 30000,
           'bonuses': [500, 100, -100, -300]}

def builtin_templates():
    return [{'id': ML_TEMPLATE_ID, 'name': ML_RULE['name'],
             'rule': deepcopy(ML_RULE), 'builtin': True}]

def resolve_rule(template_id):
    if template_id == ML_TEMPLATE_ID:
        return deepcopy(ML_RULE)
    from django.shortcuts import get_object_or_404
    from .models import RuleTemplate
    return get_object_or_404(RuleTemplate, pk=template_id).rule
