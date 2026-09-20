import copy
import json
import re
from datetime import date
from urllib.request import Request, urlopen
from django.core.cache import cache
from .domain import require

def update(document, body):
    day=body.get('date','')
    try: valid=date.fromisoformat(day).isoformat()==day
    except (ValueError,TypeError): valid=False
    require(valid,'请选择有效比赛日')
    source=document.get('historyCurrent',document.get('historySnapshot',document))
    matches=source.get('results',[]) if document.get('historySnapshot') else source.get('matches',[])
    require(any(m.get('date')==day for m in matches),'该日期没有赛程')
    table=str(body.get('table',''))
    require(any(m.get('date')==day and str(m.get('number',m.get('table','')))==table for m in matches),'请选择该比赛日的桌次')
    url=body.get('url','')
    require(isinstance(url,str) and len(url)<=2000,'直播链接格式错误')
    url=url.strip()
    match=re.fullmatch(r'https?://live\.bilibili\.com/([1-9][0-9]{0,17})/?(?:[?#][^\s]*)?',url)
    require(not url or match is not None,'请填写B站直播间链接，如 https://live.bilibili.com/1750978495')
    d=copy.deepcopy(document)
    if url:d.setdefault('tableLive',{}).setdefault(day,{})[table]='https://live.bilibili.com/'+match.group(1)
    else:d.setdefault('tableLive',{}).setdefault(day,{}).pop(table,None)
    return d

def room_status(url):
    match=re.fullmatch(r'https://live\.bilibili\.com/([1-9][0-9]{0,17})',url)
    if not match:return 'unknown'
    key='bilibili-live:'+match.group(1)
    cached=cache.get(key)
    if cached is not None:return cached
    state='unknown'
    try:
        req=Request('https://api.live.bilibili.com/room/v1/Room/get_info?room_id='+match.group(1),headers={'User-Agent':'Mozilla/5.0'})
        with urlopen(req,timeout=2) as response:data=json.loads(response.read(262144))
        value=data.get('data',{}).get('live_status')
        if data.get('code')==0 and type(value) is int:state={0:'offline',1:'live',2:'offline'}.get(value,'unknown')
    except Exception:pass
    cache.set(key,state,60 if state!='unknown' else 20)
    return state

def project(payload,document):
    if document.get('archive') or document.get('archiveRevision'):return payload
    saved=document.get('tableLive',{})
    raw={m['id']:m for m in document.get('matches',[])}
    pending={}
    for m in sorted(payload.get('schedule',[]),key=lambda m:(m.get('date',''),m.get('time',''),m.get('id',''))):
        original=raw.get(m['id'],{})
        if m.get('state') in ('completed','cancelled') or m.get('resultId') or any('score' in seat for seat in original.get('seats',[])):continue
        key=(m.get('date'),str(m.get('number',m.get('table',''))))
        pending.setdefault(key,m)
    for (day,table),m in pending.items():
        url=saved.get(day,{}).get(table)
        if url:m['live']={'url':url,'status':room_status(url)}
    return payload
