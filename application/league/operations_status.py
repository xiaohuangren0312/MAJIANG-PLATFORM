"""Read-only, environment-local operational evidence for platform administrators."""
import json
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from .views import api
from django.core.exceptions import PermissionDenied
from hql.tenancy import venue as current_venue

@api
def status(request):
    if not request.user.is_superuser:raise PermissionDenied('仅总管理员可查看备份与验收')
    if request.method!='GET':raise PermissionDenied('仅支持查看')
    venue=current_venue()
    key=venue.get('key','hql')
    path=settings.ENV_ROOT/'backups'/'verification'/ (key+'.json')
    try:evidence=json.loads(path.read_text())
    except (OSError,ValueError):evidence={}
    result={'environment':'开发' if settings.ENV_ROOT.name=='dev' else '生产'}
    for key,title in [('local','本地备份'),('offsite','异机副本'),('restore','恢复验证')]:
        result[key]=evidence.get(key,{'verified':False,'status':'待验证','detail':'尚无本环境验证记录'})
    role_path=settings.ENV_ROOT/'backups'/'verification'/'roles.json'
    try:roles=json.loads(role_path.read_text())
    except (OSError,ValueError):roles={}
    result['roles']=[dict(name=n,landing=l,scope=s,result=roles.get('result','待验收')) for n,l,s in [('总管理员','管理端','跨场馆管理'),('场馆管理员','管理端','所属场馆'),('赛事管理员','管理端','获授权赛事'),('教练','教练端','自己的队伍'),('观众','观众端','公开信息，只读')]]
    result['roleNote']=roles.get('note','权限与空数据、归档、跨场馆访问仍需逐项验收。')
    return JsonResponse(result)
