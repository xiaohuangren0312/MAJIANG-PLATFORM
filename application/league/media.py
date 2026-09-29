"""Validated event-scoped roster images stored on the data disk."""
import copy,io,uuid,warnings,json,math
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,UnidentifiedImageError
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
    with transaction.atomic():
        e=get_object_or_404(Event.objects.select_for_update(),pk=id)
        from .coach_profile import permitted
        permitted(e,request.user,kind,request.POST.get('entityId'))
        require(str(e.revision)==request.POST.get('revision'),'赛事已更新，请刷新后上传')
        before=copy.deepcopy(e.document);d=copy.deepcopy(before)
        require(not d.get('archive'),'请先开启归档修订')
        source=d
        if d.get('historySnapshot'):
            d['historyCurrent']=copy.deepcopy(d.get('historyCurrent',d['historySnapshot']));source=d['historyCurrent']
        row=find(source['teams' if kind=='team' else 'players'],request.POST.get('entityId'))
        folder=settings.ENV_ROOT/'uploads'/'roster'/str(e.id);folder.mkdir(parents=True,exist_ok=True)
        file=request.FILES.get('image')
        reuse=request.POST.get('reuseSource')=='1'
        require(not reuse or kind=='team','仅队标支持重新裁剪')
        if reuse:
            original=row.get('imageSourceUrl') or row.get('imageUrl','')
            import re
            require(re.fullmatch(r'/media/roster/'+str(e.id)+r'/[0-9a-f]{32}(?:_source)?\.png',original or '') is not None,'没有可调整的原图')
            file=folder/original.rsplit('/',1)[-1]
            require(file.is_file(),'原图不存在，请重新上传')
        else:
            require(file is not None and file.size<=5*1024*1024,'请选择不超过5MB的图片')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                with Image.open(file) as raw:
                    require(raw.format in ['PNG','JPEG','WEBP'],'支持PNG、JPEG、WebP图片')
                    require(raw.width*raw.height<=16000000,'图片最多1600万像素')
                    im=ImageOps.exif_transpose(raw).convert('RGBA')
        except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning):
            require(False,'图片无法读取，请换一张图片')
        source_image=im.copy()
        crop=None
        if 'crop' in request.POST:
            require(kind=='team','仅队标支持裁剪')
            try:crop=json.loads(request.POST['crop'])
            except (ValueError,TypeError):require(False,'裁剪参数错误')
            require(isinstance(crop,dict) and set(crop)=={'x','y','size','shape'},'裁剪参数错误')
            require(all(type(crop[k]) in [int,float] and math.isfinite(crop[k]) for k in ['x','y','size']),'裁剪参数错误')
            x,y,size=[crop[k] for k in ['x','y','size']]
            require(size>=1 and x>=0 and y>=0 and x+size<=im.width+.01 and y+size<=im.height+.01,'裁剪范围超出原图')
            require(crop['shape'] in ['square','rounded','circle'],'队标形状错误')
            im=im.transform((512,512),Image.Transform.EXTENT,(x,y,x+size,y+size),Image.Resampling.BICUBIC)
            if crop['shape']!='square':
                mask=Image.new('L',(2048,2048),0);draw=ImageDraw.Draw(mask)
                if crop['shape']=='circle':draw.ellipse((0,0,2047,2047),fill=255)
                else:draw.rounded_rectangle((0,0,2047,2047),radius=320,fill=255)
                from PIL import ImageChops
                im.putalpha(ImageChops.multiply(im.getchannel('A'),mask.resize((512,512),Image.Resampling.LANCZOS)))
        else:im.thumbnail((512,512))
        paths=[]
        def save_image(image,original=False):
            path=folder/(uuid.uuid4().hex+('_source' if original else '')+'.png');paths.append(path)
            image.save(path,format='PNG');path.chmod(0o640)
            return f'/media/roster/{e.id}/{path.name}'
        try:
            row['imageUrl']=save_image(im)
            if kind=='team':
                if not reuse:row['imageSourceUrl']=save_image(source_image,original=True)
                elif not row.get('imageSourceUrl'):row['imageSourceUrl']=save_image(source_image,original=True)
                row['imageCrop']=crop
            e.document=d;e.revision+=1;e.save(update_fields=['document','revision'])
            Audit.objects.create(event=e,actor=request.user,revision=e.revision,action='roster-image',before={'document':before},after={'document':d})
        except Exception:
            for path in paths:path.unlink(missing_ok=True)
            raise
    return JsonResponse({'imageUrl':row['imageUrl']})

def serve(request,id,name):
    import re
    if not re.fullmatch(r'[0-9a-f]{32}(?:_source)?\.png',name):raise Http404
    e=get_object_or_404(Event,pk=id)
    from .coach_profile import source,permitted
    original_allowed=False
    for row in source(e).get('teams',[]):
        if row.get('imageSourceUrl')==f'/media/roster/{e.pk}/{name}':
            if not request.user.is_authenticated:raise Http404
            permitted(e,request.user,'team',row['id']);original_allowed=True
    if name.endswith('_source.png') and not original_allowed:raise Http404
    if not e.public and not(request.user.is_authenticated and (request.user.is_superuser or e.editors.filter(pk=request.user.pk).exists())):
        if not request.user.is_authenticated:raise Http404
        from .coach_profile import permitted,source
        from django.core.exceptions import PermissionDenied
        allowed=False
        for kind,key in [('team','teams'),('player','players')]:
            for row in source(e).get(key,[]):
                if f'/media/roster/{e.pk}/{name}' not in [row.get('imageUrl'),row.get('imageSourceUrl')]:continue
                try:permitted(e,request.user,kind,row['id']);allowed=True
                except PermissionDenied:pass
        if not allowed:raise Http404
    path=settings.ENV_ROOT/'uploads'/'roster'/str(id)/name
    if not path.is_file():raise Http404
    response=FileResponse(path.open('rb'),content_type='image/png');response['Cache-Control']='private, no-cache';return response
