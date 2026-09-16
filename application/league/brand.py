import io,os,uuid,warnings
from PIL import Image,ImageOps,UnidentifiedImageError
from django.conf import settings
from django.http import HttpResponse,FileResponse,JsonResponse
from django.core.exceptions import PermissionDenied
from .domain import require

def logo(request):
    path=settings.ENV_ROOT/'uploads/brand/logo.png'
    if path.exists():
        response=FileResponse(path.open('rb'),content_type='image/png')
    else:
        response=HttpResponse('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><rect width="64" height="64" rx="10" fill="#272522"/><text x="32" y="44" text-anchor="middle" font-size="38" fill="#f7f4ed">雀</text></svg>',content_type='image/svg+xml')
    response['Cache-Control']='no-cache';return response

def upload(request):
    from .views import api
    return api(_upload)(request)

def _upload(request):
    if not request.user.is_superuser:raise PermissionDenied('仅总管理员可更换品牌Logo')
    require(request.method=='POST','请上传图片')
    file=request.FILES.get('image');require(file is not None and file.size<=5*1024*1024,'请选择5MB以内的PNG、JPEG或WebP图片')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            im=Image.open(file);require(im.format in ['PNG','JPEG','WEBP'],'支持PNG、JPEG、WebP')
            require(im.width*im.height<=16000000,'图片最多1600万像素')
            im=ImageOps.exif_transpose(im).convert('RGBA');im.thumbnail((512,512));buf=io.BytesIO();im.save(buf,format='PNG')
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning):require(False,'图片无法读取')
    folder=settings.ENV_ROOT/'uploads/brand';folder.mkdir(parents=True,exist_ok=True)
    target=folder/'logo.png';temporary=folder/(uuid.uuid4().hex+'.png')
    try:
        temporary.write_bytes(buf.getvalue());temporary.chmod(0o640);os.replace(temporary,target)
    finally:temporary.unlink(missing_ok=True)
    import logging
    logging.getLogger(__name__).warning('Brand logo updated by %s',request.user.username)
    return JsonResponse({'saved':True})
