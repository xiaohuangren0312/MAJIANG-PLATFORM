"""Recover an expired login form without authenticating or replaying its POST."""
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.csrf import csrf_failure as default_failure

@never_cache
def failure(request,reason=''):
    if request.path.rstrip('/')=='/login':
        return render(request,'login.html',{
            'error':'登录页面已失效，已为你刷新，请重新输入密码后登录。',
            'username':request.POST.get('username','')[:150],
        },status=403)
    return default_failure(request,reason=reason)
