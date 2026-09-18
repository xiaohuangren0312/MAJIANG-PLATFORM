from django.core.exceptions import PermissionDenied
ROLES={'admin':'子赛事管理员'}
ACTIONS={'match-delete','match-update','stage-delete','rule-delete','team-delete','player-delete','team','bond-player','player','team-update','player-update','stage','stage-update','rule-select','rule','match','lineup','score','paste-preview','paste-commit','save-result','publish','correct','cancel','visibility','settlement-preview','settlement-commit','archive-preview','archive-commit'}
def role_for(event,user):
    if user.is_superuser:return 'superadmin'
    if event.editors.filter(pk=user.pk).exists():return 'admin'
    raise PermissionDenied('未获得该赛事管理授权')
def actions_for(event,user):
    role=role_for(event,user)
    actions={'visibility','history-inverse','history-preview','history-correct'} if event.document.get('historySnapshot') else ACTIONS
    # History rule editing is an existing event administrator business function.
    # No users, memberships, global roles or production permissions are changed.
    if event.document.get('historySnapshot') and (user.is_superuser or event.editors.filter(pk=user.pk).exists()):
        actions=actions|{'rule','rule-select','history-image','history-roster-delete','history-roster','history-player-add','history-stage-update','history-bond-register'}
    if event.kind=='personal' and not event.document.get('historySnapshot'):
        actions=actions|{'pairing-preview','pairing-commit'}
    actions=actions|{'coach-manage'}
    if event.document.get('archive') or event.document.get('archiveRevision'):
        if not user.is_superuser:return []
        if event.document.get('archive'):actions={'visibility','archive-reopen','coach-manage'}
    if user.is_superuser and event.is_test and event.document.get('archive') and not event.document.get('historySnapshot'):
        actions=actions|{'cleanup-preview','cleanup-commit'}
    if not event.document.get('archive'):actions=actions|{'match-resources'}
    return sorted(actions|({'grant'} if role=='superadmin' else set()))
def authorize(event,user,action):
    if action not in actions_for(event,user):raise PermissionDenied('当前账号无权执行此操作')
