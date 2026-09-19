def account_identity(request):
    user=request.user
    if not user.is_authenticated:return {}
    from .models import Event
    from .views import coach_account
    role='总管理员' if user.is_superuser else '赛事管理员' if Event.objects.filter(editors=user).exists() else '教练' if coach_account(user) else '观众'
    from .coach_lineups import writable,team_ids
    can_coach=any(writable(e) and team_ids(e,user) for e in Event.objects.filter(kind='team').prefetch_related('editors','draft_activities'))
    current_portal='manage' if request.path.startswith('/manage') else 'coach' if request.path.startswith('/coach') else 'public'
    from django.conf import settings
    return {'header_can_coach':can_coach,'header_portal':current_portal,'header_can_manage':role in ('总管理员','赛事管理员'),'header_is_coach':role=='教练','header_account_role':role,'environment_label':'生产环境' if settings.ENV_ROOT.name=='prod' else '开发环境'}
