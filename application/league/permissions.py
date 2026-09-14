from django.core.exceptions import PermissionDenied
ROLES={'admin':'子赛事管理员'}
ACTIONS={'team','bond-player','player','team-update','player-update','stage','stage-update','rule','match','lineup','score','save-result','publish','correct','cancel','visibility','settlement-preview','settlement-commit','archive-preview','archive-commit'}
def role_for(event,user):
    if user.is_superuser:return 'superadmin'
    if event.editors.filter(pk=user.pk).exists():return 'admin'
    raise PermissionDenied('未获得该赛事管理授权')
def actions_for(event,user):
    role=role_for(event,user)
    actions={'visibility','history-preview','history-correct'} if event.document.get('historySnapshot') else ACTIONS
    # History rule editing is an existing event administrator business function.
    # No users, memberships, global roles or production permissions are changed.
    if event.document.get('historySnapshot') and (user.is_superuser or event.editors.filter(pk=user.pk).exists()):
        actions=actions|{'rule'}
    if event.kind=='personal' and not event.document.get('historySnapshot'):
        actions=actions|{'pairing-preview','pairing-commit'}
    if event.document.get('archive'):actions={'visibility'}
    if user.is_superuser and event.is_test and event.document.get('archive') and not event.document.get('historySnapshot'):
        actions=actions|{'cleanup-preview','cleanup-commit'}
    actions=actions|{'match-resources'}
    return sorted(actions|({'grant'} if role=='superadmin' else set()))
def authorize(event,user,action):
    if action not in actions_for(event,user):raise PermissionDenied('当前账号无权执行此操作')
