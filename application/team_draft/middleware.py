from django.conf import settings
from django.http import HttpResponse, JsonResponse

class DraftAvailabilityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.DRAFT_ENABLED and (request.path.rstrip('/') == '/draft' or request.path.startswith('/draft/') or request.path.rstrip('/') == '/api/draft' or request.path.startswith('/api/draft/')):
            if request.path.startswith('/api/'):
                response = JsonResponse({'error': '选人大会暂时关闭', 'disabled': True}, status=503)
            else:
                response = HttpResponse('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>选人大会暂时关闭</title><body style="margin:10vh auto;padding:24px;max-width:600px;font-family:system-ui;background:#f5f1e9"><h1>选人大会暂时关闭</h1><p>选人记录已保留，恢复开放后可继续访问。</p><a href="/">返回赛事首页</a></body></html>')
            response['Cache-Control'] = 'no-store'
            return response
        return self.get_response(request)
