def account_identity(request):
    user=request.user
    if not user.is_authenticated:return {}
    from .models import Event
    from .views import coach_account
    role='总管理员' if user.is_superuser else '赛事管理员' if Event.objects.filter(editors=user).exists() else '教练' if coach_account(user) else '观众'
    return {'header_account_role':role}
