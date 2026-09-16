from .projection import rank_metrics
from .domain import optional_note
import json,hashlib,datetime
from functools import wraps
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied,ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .permissions import role_for,actions_for,authorize,ROLES
import copy
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse,FileResponse,Http404
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET,require_POST
from .models import Event,Audit,HistoricalArchive,LoginAttempt
from .domain import initial,apply,Invalid,require,label
from .projection import public_event,settlement_preview,settle
from .lifecycle import archive_preview,archive_event,cleanup_preview,cleanup_event

def allowed(user):
    return Event.objects.all() if user.is_superuser else Event.objects.filter(editors=user)
def api(fn):
    @wraps(fn)
    def wrapper(request,*a,**kw):
        if not request.user.is_authenticated:return JsonResponse({'error':'请先登录'},status=401)
        try:return fn(request,*a,**kw)
        except PermissionDenied as e:return JsonResponse({'error':str(e)},status=403)
        except (Invalid,ValueError,TypeError,KeyError,signing.BadSignature) as e:return JsonResponse({'error':str(e) if isinstance(e,Invalid) else '请求格式错误或预览已失效'},status=400)
    return wrapper
def body(request):
    value=json.loads(request.body);require(isinstance(value,dict),'请求必须为对象');return value
def summary(e,user=None):return dict(id=str(e.id),name=e.name,kind=e.kind,public=e.public,revision=e.revision,isTest=e.is_test,archived=bool(e.document.get('archive')),**({'role':role_for(e,user),'actions':actions_for(e,user)} if user else {}))

@ensure_csrf_cookie
def signin(request):
    error=''
    if request.method=='POST':
        name=request.POST.get('username','')[:150]
        key=hashlib.sha256((request.META.get('REMOTE_ADDR','')+':'+name).encode()).hexdigest()
        attempt,_=LoginAttempt.objects.get_or_create(key=key)
        if attempt.failures>=8 and attempt.updated_at>timezone.now()-datetime.timedelta(minutes=15):error='尝试次数过多，请15分钟后重试'
        else:
            user=authenticate(request,username=name,password=request.POST.get('password',''))
            if user:
                LoginAttempt.objects.filter(key=key).delete();login(request,user);return redirect('/manage/' if user.is_superuser or allowed(user).exists() else '/')
            if attempt.updated_at<timezone.now()-datetime.timedelta(minutes=15):attempt.failures=0
            attempt.failures+=1;attempt.save();error='用户名或密码不正确'
    return render(request,'login.html',{'error':error})

@require_POST
def signout(request):logout(request);return redirect('/login/')

@login_required
@ensure_csrf_cookie
def manage(request):
    if not request.user.is_superuser and not allowed(request.user).exists():return redirect('/')
    return render(request,'manage.html')

@require_GET
def public_data(request):
    response=JsonResponse({'demo':False,'updatedAt':timezone.now().isoformat(),'tournaments':[public_event(e) for e in Event.objects.filter(public=True)]+[rank_metrics(x.payload) for x in HistoricalArchive.objects.filter(public=True)]},json_dumps_params={'ensure_ascii':False})
    response['Cache-Control']='no-store';return response

@api
def events(request):
    if request.method=='GET':return JsonResponse({'events':[summary(e,request.user) for e in allowed(request.user)],'canCreateEvent':request.user.is_superuser,'canManageAccounts':request.user.is_superuser})
    require(request.method=='POST','请求方法不支持')
    b=body(request);kind=b.get('kind');require(kind in ['team','personal'],'赛事类型错误')
    # Only total administrators create tournaments and assign event managers.

    if not request.user.is_superuser:raise PermissionDenied('只有总管理员可以创建赛事')
    require(type(b.get('isTest',False)) is bool,'测试赛事标记错误')
    with transaction.atomic():
        e=Event.objects.create(name=label(b.get('name')),kind=kind,is_test=b.get('isTest',False),document=apply(initial(),kind,'stage',{'name':'常规赛'}));e.editors.add(request.user)
        Audit.objects.create(event=e,actor=request.user,revision=1,action='create',before={},after=e.document)
    return JsonResponse(summary(e),status=201)

@api
def event_detail(request,id):
    e=get_object_or_404(allowed(request.user),pk=id)
    if request.method=='GET':return JsonResponse({**summary(e,request.user),'document':e.document})
    require(request.method=='POST','请求方法不支持');b=body(request)
    if b.get('revision')!=e.revision:return JsonResponse({'error':'数据已被修改，请刷新后重试'},status=409)
    action=b.get('action');authorize(e,request.user,action);old=e.document;old_public=e.public;grant_user=None
    if action=='history-inverse':
        from .history_correction import effective
        from .paste_scores import inverse
        from .domain import find
        m=find(effective(old)['results'],b.get('id'))
        points=[s.get('points') if s.get('points') is not None else s.get('teamPoints') for s in m['seats']]
        require(all(type(v) is int for v in points),'本场PT不完整，无法反算')
        require(not m.get('penalties'),'本场存在罚分记录，不能按无罚分反算')
        candidates=inverse(dict(start=25000,**{'return':30000},bonuses=[500,100,-100,-300]),points)
        require(candidates,f'这四个PT合计为{sum(points)/10:g}，无法按无罚分ML规则还原，请核对原表；未修改任何数据')
        return JsonResponse({'candidates':candidates})
    if action=='paste-preview':
        from .paste_scores import preview as paste_preview
        p=paste_preview(old,e.kind,b)
        token=signing.dumps(dict(event=str(e.id),revision=e.revision,body={k:b[k] for k in ['id','text','mode'] if k in b}),salt='paste-scores')
        return JsonResponse({'preview':p,'token':token})
    if action=='pairing-preview':
        from .pairing import preview as pairing_preview
        p=pairing_preview(old,e.kind,b);p['sourceRevision']=e.revision
        token=signing.dumps(dict(event=str(e.id),revision=e.revision,preview=p),salt='pairing')
        return JsonResponse({'preview':p,'token':token})
    if action in ['archive-preview','cleanup-preview']:
        preview=archive_preview(e) if action=='archive-preview' else cleanup_preview(e)
        token=signing.dumps(dict(event=str(e.id),revision=e.revision,preview=preview),salt=action)
        return JsonResponse({'preview':preview,'token':token})
    if action=='cleanup-commit':
        # This action is authorized only for total administrators of test events.
        signed=signing.loads(b.get('token'),salt='cleanup-preview',max_age=1800)
        require(signed['event']==str(e.id) and signed['revision']==e.revision,'清理预览已过期')
        try:result=cleanup_event(e.id,e.revision,b.get('confirmName'),b.get('reason'),request.user)
        except OSError:raise Invalid('恢复备份写入失败，测试赛事未清理，请检查数据盘空间')
        return JsonResponse({'deleted':True,'summary':result})
    if action=='history-preview':
        from .history_correction import preview as history_preview
        p,_=history_preview(old,b)
        b['ruleId']=p['rule']['id']
        token=signing.dumps(dict(event=str(e.id),revision=e.revision,body={k:b[k] for k in ['id','seats','reason','scoreMode','confirmNoPenalties','ruleId'] if k in b}),salt='history-correction')
        return JsonResponse({'preview':p,'token':token})
    if action=='settlement-preview':
        preview=settlement_preview(old,e.kind,b)
        token=signing.dumps(dict(event=str(e.id),revision=e.revision,preview=preview),salt='settlement')
        return JsonResponse({'preview':preview,'token':token})
    if action=='grant':
        username=label(b.get('username'));reason=optional_note(b.get('reason'));role=b.get('role')
        require(role in ['admin','revoke'],'授权角色错误')
        grant_user=get_user_model().objects.filter(username=username,is_active=True).first()
        require(grant_user is not None,'账号不存在或已停用，请由平台管理员先创建账号')
        require(not grant_user.is_superuser,'总管理员权限不由赛事授权修改')
        new=copy.deepcopy(old);roles=new.setdefault('accessRoles',{})
        # A total administrator retains global access even with no local managers.
        if role=='revoke':roles.pop(str(grant_user.pk),None)
        else:roles[str(grant_user.pk)]=role
    elif action=='history-correct':
        from .history_correction import commit as history_commit
        signed=signing.loads(b.get('token'),salt='history-correction',max_age=1800)
        require(signed['event']==str(e.id) and signed['revision']==e.revision,'更正预览已过期，请重新生成')
        require(b.get('acknowledgeCarry') is True,'请确认原表快照与后续带入分保留不变')
        new=history_commit(old,signed['body']);new['historyCorrections'][-1].update(actor=request.user.username,at=timezone.now().isoformat());b['reason']=optional_note(signed['body'].get('reason'))
    elif action=='pairing-commit':
        from .pairing import commit as pairing_commit
        signed=signing.loads(b.get('token'),salt='pairing',max_age=1800)
        require(signed['event']==str(e.id) and signed['revision']==e.revision,'排程预览已过期，请重新预览')
        new=pairing_commit(old,e.kind,signed['preview'],b.get('tables'),b.get('reason',''))
        new['pairingRounds'][-1].update(actor=request.user.username,at=timezone.now().isoformat())
    elif action=='settlement-commit':
        signed=signing.loads(b.get('token'),salt='settlement',max_age=1800)
        require(signed['event']==str(e.id) and signed['revision']==e.revision,'预览已过期，请重新生成')
        p=signed['preview']
        check=copy.deepcopy(old)
        if p.get('createdStage'):check['stages'].append(p['createdStage'])
        settlement_preview(check,e.kind,dict(source=p['source'],target=p['target'],numerator=p['numerator'],denominator=p['denominator'],roundingMode=p.get('roundingMode','ceil'),ids=[r['id'] for r in p['rows']]))
        new=settle(old,p,b.get('overrides',{}))
    elif action=='archive-commit':
        signed=signing.loads(b.get('token'),salt='archive-preview',max_age=1800)
        require(signed['event']==str(e.id) and signed['revision']==e.revision,'归档预览已过期，请重新预览')
        new=archive_event(e,b.get('reason'),request.user.username)
    elif action=='paste-commit':
        from .paste_scores import commit as paste_commit
        signed=signing.loads(b.get('token'),salt='paste-scores',max_age=1800)
        require(signed['event']==str(e.id) and signed['revision']==e.revision,'预览已过期，请重新解析')
        new=paste_commit(old,e.kind,signed['body'],b.get('candidate',0))
    elif action=='match-resources':
        from .match_resources import update
        new=update(old,b)
    elif action=='visibility':
        require(type(b.get('public')) is bool,'公开状态错误');new=old;e.public=b['public']
    else:
        if action=='rule' and old.get('historySnapshot'):optional_note(b.get('reason'))
        new=apply(old,e.kind,action,b)
    with transaction.atomic():
        if action=='visibility' and e.public and old.get('historySnapshot'):
            from .models import HistoryImport,HistoryReview
            from .history_review import fingerprint,report
            link=HistoryImport.objects.get(event=e)
            archive=HistoricalArchive.objects.select_for_update().get(pk=link.archive_id)
            require(fingerprint(archive.payload)==link.fingerprint,'来源档案已变化，需重新核对导入版本')
            review=HistoryReview.objects.filter(archive=archive,fingerprint=link.fingerprint).first()
            decisions=review.decisions if review else {}
            require(all(decisions.get(i['id'],{}).get('status')=='retain' for i in report(archive.payload)['issues']),'历史赛事还有待核对项，请由总管理员在导入核对页处理')
            archive.public=False;archive.save(update_fields=['public'])
        changed=Event.objects.filter(id=e.id,revision=e.revision).update(document=new,public=e.public,revision=F('revision')+1)
        if not changed:
            transaction.set_rollback(True)
            return JsonResponse({'error':'并发修改冲突，请刷新'},status=409)
        if grant_user is not None:
            if b['role']=='revoke':e.editors.remove(grant_user)
            else:e.editors.add(grant_user)
        Audit.objects.create(event=e,actor=request.user,revision=e.revision+1,action=action,reason=b.get('reason',''),before={'document':old,'public':old_public},after={'document':new,'public':e.public,**({'authorization':{'username':grant_user.username,'role':b['role']}} if grant_user is not None else {})})
    return JsonResponse({'revision':e.revision+1})

@require_GET
def asset(request,name):
    # Deliberate allowlist; no directory traversal or app source exposure.
    require_names={'pairing.js','lifecycle.js','public.js','trend-data.js','public.css','history-ui.js','ink-ivory.css','red-white.css','manager.js','manager.css','roster.js','match-editor.js','access.js','history-review.js','history-editor.js'}
    if name not in require_names:raise Http404
    path=settings.BASE_DIR/'static'/name
    response=FileResponse(path.open('rb'),content_type='text/javascript' if name.endswith('.js') else 'text/css')
    response['Cache-Control']='no-cache';return response

@require_GET
def index(request):return render(request,'public.html')

@require_GET
def health(request):
    Event.objects.exists();return JsonResponse({'status':'ok','environment':'development'})


@api
@require_GET
def access_list(request,id):
    e=get_object_or_404(allowed(request.user),pk=id);authorize(e,request.user,'grant')
    return JsonResponse({'members':[{'username':u.username,'role':role_for(e,u),'active':u.is_active,'platformAdmin':u.is_superuser} for u in e.editors.all()]})

@api
@require_POST
def create_account(request):
    if not request.user.is_superuser:raise PermissionDenied('只有总管理员可以创建账号')
    b=body(request);username=label(b.get('username'));password=b.get('password','1234@qwer')
    require(isinstance(password,str),'请填写初始密码')
    User=get_user_model();require(not User.objects.filter(username=username).exists(),'用户名已存在')
    user=User(username=username,is_staff=False,is_superuser=False)
    try:
        user.full_clean(exclude=['password'])
        # User-approved initial password for new ordinary accounts only.
        if password!='1234@qwer':validate_password(password,user)
    except ValidationError as e:raise Invalid('；'.join(e.messages))
    user.set_password(password);user.save()
    return JsonResponse({'username':user.username},status=201)


@login_required
@ensure_csrf_cookie
def account(request):
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash
    from django.views.decorators.debug import sensitive_post_parameters
    # Password fields are never echoed into templates or audit records.
    request.sensitive_post_parameters=('old_password','new_password1','new_password2')
    if request.method not in ['GET','POST']:return JsonResponse({'error':'请求方法不支持'},status=405)
    form=PasswordChangeForm(request.user,request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        user=form.save();update_session_auth_hash(request,user)
        return redirect('/account/?changed=1')
    managed=allowed(request.user)
    role='总管理员' if request.user.is_superuser else '子赛事管理员' if managed.exists() else '普通账号'
    response=render(request,'account.html',{'password_form':form,'account_role':role,'managed_events':managed,'can_manage':request.user.is_superuser or managed.exists(),'changed':request.GET.get('changed')=='1'})
    response['Cache-Control']='no-store'
    return response


@login_required
@ensure_csrf_cookie
def history_page(request):
    if not request.user.is_superuser:raise PermissionDenied('只有总管理员可以核对历史导入')
    return render(request,'history-review.html')

@api
def history_reviews(request,key=None):
    from .models import HistoryReview,HistoryReviewAudit
    from .history_review import fingerprint,report
    if not request.user.is_superuser:raise PermissionDenied('只有总管理员可以核对历史导入')
    if key is None:
        require(request.method=='GET','请求方法不支持')
        return JsonResponse({'archives':[{'id':a.key,'name':a.payload.get('name',a.key)} for a in HistoricalArchive.objects.all()]})
    archive=get_object_or_404(HistoricalArchive,pk=key)
    if request.method=='GET':
        from .models import HistoryImport
        imported=HistoryImport.objects.filter(archive=archive).first()
        digest=fingerprint(archive.payload);review=HistoryReview.objects.filter(archive=archive).first()
        same=review is not None and review.fingerprint==digest
        response=JsonResponse({'importedEvent':str(imported.event_id) if imported else None,'report':report(archive.payload),'fingerprint':digest,'revision':review.revision if review else 0,'decisions':review.decisions if same else {},'sourceChanged':review is not None and not same})
        response['Cache-Control']='no-store';return response
    require(request.method=='POST','请求方法不支持');b=body(request)
    with transaction.atomic():
        archive=HistoricalArchive.objects.select_for_update().get(pk=key)
        digest=fingerprint(archive.payload)
        if b.get('fingerprint')!=digest:return JsonResponse({'error':'原始档案已变化，请重新加载核对'},status=409)
        review,_=HistoryReview.objects.get_or_create(archive=archive,defaults={'fingerprint':digest})
        if type(b.get('revision')) is not int or b['revision']!=review.revision:return JsonResponse({'error':'核对记录已更新，请重新加载'},status=409)
        issue_ids={i['id'] for i in report(archive.payload)['issues']}
        issue=b.get('issue');require(isinstance(issue,str) and issue in issue_ids,'核对项不存在')
        status=b.get('status');require(status in ['pending','retain'],'核对状态错误')
        note=b.get('note','');require(isinstance(note,str) and len(note)<=1000,'备注最多1000字')
        require(status!='retain' or bool(note.strip()),'保留原表时请填写核对依据或缺失说明')
        before=copy.deepcopy(review.decisions)
        decisions=copy.deepcopy(before) if review.fingerprint==digest else {}
        decisions[issue]={'status':status,'note':note.strip(),'actor':request.user.username,'at':timezone.now().isoformat()}
        review.decisions=decisions;review.fingerprint=digest;review.revision+=1;review.save()
        HistoryReviewAudit.objects.create(review=review,actor=request.user,revision=review.revision,before=before,after=decisions)
    return JsonResponse({'revision':review.revision})


@api
@require_POST
def import_history(request,key):
    from .models import HistoryImport,HistoryReview
    from .history_review import fingerprint,report
    if not request.user.is_superuser:raise PermissionDenied('只有总管理员可以导入历史赛事')
    b=body(request);reason=optional_note(b.get('reason'))
    with transaction.atomic():
        archive=get_object_or_404(HistoricalArchive.objects.select_for_update(),pk=key)
        digest=fingerprint(archive.payload)
        if b.get('fingerprint')!=digest:return JsonResponse({'error':'原始档案已变化，请重新预览'},status=409)
        linked=HistoryImport.objects.filter(archive=archive).first()
        if linked:return JsonResponse({'id':str(linked.event_id),'existing':True})
        review=HistoryReview.objects.filter(archive=archive).first()
        if b.get('revision')!=(review.revision if review else 0):return JsonResponse({'error':'核对记录已变化，请重新预览'},status=409)
        payload=copy.deepcopy(archive.payload);d=initial()
        d.update(season=payload.get('season',''),venue=payload.get('venue','欢雀楼'),historySnapshot=payload,historySource={'key':key,'fingerprint':digest,'reason':reason})
        e=Event.objects.create(name=label(payload['name']),kind=payload.get('type','team'),document=d,public=False)
        e.editors.add(request.user)
        HistoryImport.objects.create(archive=archive,event=e,fingerprint=digest)
        Audit.objects.create(event=e,actor=request.user,revision=1,action='history-import',reason=reason,before={},after={'document':d,'review':review.decisions if review and review.fingerprint==digest else {}})
    return JsonResponse({'id':str(e.id),'existing':False},status=201)
