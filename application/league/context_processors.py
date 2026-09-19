def account_identity(request):
    user=request.user
    if not user.is_authenticated:return {}
    from .models import Event
    from .views import coach_account
    role='总管理员' if user.is_superuser else '赛事管理员' if Event.objects.filter(editors=user).exists() else '教练' if coach_account(user) else '观众'
    from django.conf import settings
    return {'header_can_manage':role in ('总管理员','赛事管理员'),'header_is_coach':role=='教练','header_account_role':role,'environment_label':'生产环境' if settings.ENV_ROOT.name=='prod' else '开发环境'}
