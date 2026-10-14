"""Request-scoped venue routing. Never mutate process-wide Django settings."""
from contextvars import ContextVar
from pathlib import Path
from functools import wraps
from django.conf import settings
from django.http import HttpResponseBadRequest
_current=ContextVar('venue',default=None)
def venue():
 return _current.get() or {'key':'hql','database':'default','name':'欢雀楼','english':'HUAN QUE LOU','root':str(settings.ENV_ROOT)}
def database():return venue()['database']
def storage_root():return Path(venue()['root'])
class Router:
 def db_for_read(self,model,**hints):return database()
 def db_for_write(self,model,**hints):return database()
 def allow_relation(self,obj1,obj2,**hints):return obj1._state.db==obj2._state.db
 def allow_migrate(self,db,app_label,model_name=None,**hints):return True
class Middleware:
 def __init__(self,get_response):self.get_response=get_response
 def __call__(self,request):
  registry=getattr(settings,'VENUES',{})
  if not registry:return self.get_response(request)
  host=request.get_host().lower()
  selected=next((v for v in registry.values() if host in v['hosts']),None)
  if selected is None:return HttpResponseBadRequest('Unknown venue entry')
  from .venue_brand import read_brand
  selected={**selected,**read_brand(selected)}
  token=_current.set(selected)
  try:
   request.venue=selected
   suffix='' if selected['database']=='default' else '_'+selected['key']
   for canonical in (settings.SESSION_COOKIE_NAME,settings.CSRF_COOKIE_NAME):
    actual=canonical+suffix
    if suffix:
     request.COOKIES.pop(canonical,None)
     if actual in request.COOKIES:request.COOKIES[canonical]=request.COOKIES[actual]
   response=self.get_response(request)
   for canonical in (settings.SESSION_COOKIE_NAME,settings.CSRF_COOKIE_NAME):
    if canonical in response.cookies:
     morsel=response.cookies[canonical]
     if suffix:
      response.cookies[canonical+suffix]=morsel.value
      for k,v in morsel.items():response.cookies[canonical+suffix][k]=v
      del response.cookies[canonical]
     response.cookies[canonical+suffix]['secure']=request.is_secure()
   if not response.streaming and response.get('Content-Type','').startswith('text/html'):
    import json
    payload=json.dumps({'name':selected['name'],'english':selected.get('english',''),'tagline':selected.get('tagline',''),'csrfCookie':settings.CSRF_COOKIE_NAME+suffix},ensure_ascii=True).replace('<','\u003c')
    content=response.content.decode(response.charset)
    content=content.replace('</head>','<script>window.HQL_BRAND='+payload+';</script></head>')
    response.content=content
    if response.has_header('Content-Length'):response['Content-Length']=len(response.content)
   return response
  finally:_current.reset(token)
def branding(request):
 v=venue();return {'venue_name':v['name'],'venue_english':v.get('english',''),'venue_tagline':v.get('tagline','以牌会友 · 共赴山海'),'venue_credit':v.get('credit',''),'venue_icp':v.get('icp','浙ICP备2026081609号-1' if v['key']=='hql' else '')}
