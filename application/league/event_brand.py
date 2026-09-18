"""Event-scoped logos; omission falls back to the platform default."""
import copy,io,uuid,warnings,re
from PIL import Image,ImageOps,UnidentifiedImageError
from django.conf import settings
from django.db import transaction
from django.http import FileResponse,JsonResponse,Http404
from django.shortcuts import get_object_or_404
from .models import Event,Audit
from .permissions import authorize
from .domain import require
from . import brand

def logo(request,id):
    e=get_object_or_404(Event,pk=id)
    if not e.public and not(request.user.is_authenticated and (request.user.is_superuser or e.editors.filter(pk=request.user.pk).exists())):raise Http404
    name=e.document.get('eventLogo','')
    path=settings.ENV_ROOT/'uploads/events'/str(e.id)/name
    if re.fullmatch(r'[0-9a-f]{32}\.png',name) and path.is_file():response=FileResponse(path.open('rb'),content_type='image/png')
    else:response=brand.logo(request)
    response['Cache-Control']='private, no-cache'
    return response

def upload(request,id):
    from .views import api
    return api(_upload)(request,id)

def _upload(request,id):
    from .views import allowed
    require(request.method=='POST','请使用上传操作')
    with transaction.atomic():
        e=get_object_or_404(allowed(request.user).select_for_update(),pk=id)
        authorize(e,request.user,'event-logo')
        if str(e.revision)!=request.POST.get('revision'):return JsonResponse({'error':'赛事已更新，请刷新后重试'},status=409)
        old=copy.deepcopy(e.document);path=None
        if request.POST.get('remove')=='1':e.document.pop('eventLogo',None)
        else:
            file=request.FILES.get('image');require(file is not None and file.size<=5*1024*1024,'请选择5MB以内的PNG、JPEG或WebP图片')
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error',Image.DecompressionBombWarning)
                    im=Image.open(file);require(im.format in ['PNG','JPEG','WEBP'],'支持PNG、JPEG、WebP')
                    require(im.width*im.height<=16000000,'图片最多1600万像素')
                    im=ImageOps.exif_transpose(im).convert('RGBA');im.thumbnail((512,512));buf=io.BytesIO();im.save(buf,format='PNG')
            except (OSError,UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning):require(False,'图片无法读取')
            folder=settings.ENV_ROOT/'uploads/events'/str(e.id);folder.mkdir(parents=True,exist_ok=True)
            name=uuid.uuid4().hex+'.png';path=folder/name;path.write_bytes(buf.getvalue());path.chmod(0o640);e.document['eventLogo']=name
        try:
            e.revision+=1;e.save(update_fields=['document','revision'])
            Audit.objects.create(event=e,actor=request.user,revision=e.revision,action='event-logo',before={'document':old},after={'document':e.document})
        except Exception:
            if path:path.unlink(missing_ok=True)
            raise
    return JsonResponse({'revision':e.revision})
