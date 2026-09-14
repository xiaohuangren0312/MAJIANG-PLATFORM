import copy
from urllib.parse import urlsplit
from .domain import require,label,find

def update(document,body):
    d=copy.deepcopy(document)
    source=d.get('historyCurrent',d.get('historySnapshot',{}))
    matches=source.get('results',[]) if d.get('historySnapshot') else d['matches']
    find(matches,body.get('id'))
    commentators=body.get('commentators',[])
    require(isinstance(commentators,list) and len(commentators)<=10,'最多10位解说员')
    data={'commentators':[label(n) for n in commentators]}
    for field in ['videos','records']:
        rows=body.get(field,[]);require(isinstance(rows,list) and len(rows)<=20,'每类最多20条链接')
        data[field]=[]
        for row in rows:
            require(isinstance(row,dict),'链接格式错误')
            url=row.get('url','');require(isinstance(url,str) and len(url)<=2000,'链接过长')
            try:parts=urlsplit(url);valid=parts.scheme in ['http','https'] and bool(parts.hostname) and not parts.username and not parts.password
            except ValueError:valid=False
            require(valid,'视频和牌谱链接须为完整的HTTP或HTTPS网址')
            data[field].append({'title':label(row.get('title') or ('视频' if field=='videos' else '牌谱')),'url':url})
    d.setdefault('matchResources',{})[body['id']]=data
    return d

def project(payload,document):
    payload=copy.deepcopy(payload)
    for collection in ['results','schedule']:
        for m in payload.get(collection,[]):
            key=m.get('resultId') or m['id']
            if key in document.get('matchResources',{}):m['resources']=document['matchResources'][key]
    return payload
