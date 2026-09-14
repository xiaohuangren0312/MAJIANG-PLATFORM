"""Validated event-scoped roster images stored on the data disk."""
import copy,io,uuid,warnings
from pathlib import Path
from PIL import Image,ImageOps,UnidentifiedImageError
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse,FileResponse,Http404
from django.shortcuts import get_object_or_404
from .models import Event,Audit
from .domain import require,find,integer
from .permissions import authorize

def upload(request,id):
    from .views import api
    return api(_upload)(request,id)

def _upload(request,id):
    require(request.method=='POST','请使用上传操作')
    kind=request.POST.get('kind');require(kind in ['team','player'],'图片对象错误')
    file=request.FILES.get('image');require(file is not None and file.size<=5*1024*1024,'请选择不超过5MB的图片')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            im=Image.open(file);require(im.format in ['PNG','JPEG','WEBP'],'支持PNG、JPEG、WebP图片')
            require(im.width*im.height<=16000000,'图片最多1600万像素')
            im=ImageOps.exif_transpose(im).convert('RGBA');im.thumbnail((512,512))
            output=io.BytesIO();im.save(output,format='PNG')
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):
        require(False,'图片无法读取，请换一张图片')
    with transaction.atomic():
        e=get_object_or_404(Event.objects.select_for_update(),pk=id)
        authorize(e,request.user,kind+'-update')
        require(str(e.revision)==request.POST.get('revision'),'赛事已更新，请刷新后上传')
        before=copy.deepcopy(e.document);d=copy.deepcopy(before)
        require(not d.get('archive'),'赛事已归档')
        row=find(d['teams' if kind=='team' else 'players'],request.POST.get('entityId'))
        folder=settings.ENV_ROOT/'uploads'/'roster'/str(e.id);folder.mkdir(parents=True,exist_ok=True)
        name=uuid.uuid4().hex+'.png';path=folder/name;path.write_bytes(output.getvalue());path.chmod(0o640)
        row['imageUrl']=f'/media/roster/{e.id}/{name}'
        try:
            e.document=d;e.revision+=1;e.save(update_fields=['document','revision'])
            Audit.objects.create(event=e,actor=request.user,revision=e.revision,action='roster-image',before={'document':before},after={'document':d})
        except Exception:
            path.unlink(missing_ok=True);raise
    return JsonResponse({'imageUrl':row['imageUrl']})

def serve(request,id,name):
    import re
    if not re.fullmatch(r'[0-9a-f]{32}\.png',name):raise Http404
    e=get_object_or_404(Event,pk=id)
    if not e.public and not(request.user.is_authenticated and (request.user.is_superuser or e.editors.filter(pk=request.user.pk).exists())):raise Http404
    path=settings.ENV_ROOT/'uploads'/'roster'/str(id)/name
    if not path.is_file():raise Http404
    response=FileResponse(path.open('rb'),content_type='image/png');response['Cache-Control']='private, no-cache';return response
