"""Read-only source analysis and separately persisted human review decisions."""
import hashlib,json
from collections import Counter
from .domain import score,Invalid

def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def report(payload):
    issues=[]
    def add(key,stage,match,category,message):
        issues.append(dict(id=key,stage=stage,match=match,category=category,message=message))
    teams={x['id']:x for x in payload.get('teams',[])}
    players={x['id']:x for x in payload.get('players',[])}
    for kind,items in [('队伍',teams),('选手',players)]:
        names=Counter(x['name'].strip() for x in items.values())
        for name,n in names.items():
            if n>1:add(kind+':'+name,'','', '重名',f'{kind}“{name}”有{n}条记录，请核对是否为同一对象；不会自动合并')
    for m in payload.get('results',[]):
        mid=m['id'];stage=m.get('stageId','');seats=m.get('seats',[])
        missing=[];membership=[]
        if len(seats)!=4:missing.append('非四个座次')
        for i,s in enumerate(seats):
            who=players.get(s.get('playerId'));t=teams.get(s.get('teamId'))
            fields=[]
            if not who:fields.append('选手')
            if payload.get('type')=='team' and not t:fields.append('队伍')
            for field,title in [('score','终局点数'),('rank','顺位'),('points','个人PT'),('teamPoints','队伍PT'),('penalty','罚分')]:
                if s.get(field) is None:fields.append(title)
            if fields:missing.append(f'座次{i+1}：'+ '、'.join(fields))
            if who and t and who.get('teamId')!=t['id']:membership.append(who['name']+'：本场队伍与名单归属不同，需核对历史转队')
        if missing:add(mid+':missing',stage,mid,'缺失信息','；'.join(missing))
        if membership:add(mid+':membership',stage,mid,'队伍归属','；'.join(membership))
        if len(seats)==4 and all(type(s.get('score')) is int for s in seats):
            try:
                expected=score(dict(start=25000,return_=30000,bonuses=[500,100,-100,-300],**{'return':30000}),[s['score'] for s in seats])
                differences=[f'座次{i+1} 原表基础PT {s.get("base")/10 if s.get("base") is not None else "未知"} / 默认规则 {c["base"]/10}' for i,(s,c) in enumerate(zip(seats,expected)) if s.get('base') is not None and s['base']!=c['base']]
                if differences:add(mid+':score',stage,mid,'计分差异','；'.join(differences)+'。仅与默认规则比较，不自动改写原表。')
            except Invalid as e:add(mid+':score',stage,mid,'点数校验',str(e)+'；保留原表，需核对当时规则或供托')
    if payload.get('reconciliation'):
        # Source omissions are one season-level decision, never one per game.
        original=issues;issues=[]
        for category in dict.fromkeys(i['category'] for i in original):
            group=[i for i in original if i['category']==category]
            if category=='缺失信息':
                fields=Counter()
                for m in payload.get('results',[]):
                    for s in m['seats']:
                        for key,title in [('playerId','选手'),('teamId','队伍'),('score','终局点数'),('rank','顺位'),('penalty','罚分')]:
                            if s.get(key) is None:fields[title]+=1
                add('source-omissions','','',category,'原表未记录字段统一处理：'+ '、'.join(f'{k}{v}个座次' for k,v in fields.items())+'。阶段及最终队伍成绩已有依据；保留未知，不要求逐场核对。')
            else:
                add('group:'+category,'','',category,'；'.join(dict.fromkeys(i['message'] for i in group)))
        if payload.get('id')=='s2':
            add('source-adjustment:_404','','','积分差额','S2 _404：对局记录N55为-48.4PT，13600点按默认规则为-46.4PT，相差2PT。保留正式成绩，仅确认是否为罚分。')
            for name,target in [('Zing_Coco','COCO'),('菜菜子','神菜菜子'),('404','_404'),('楠哥','银河蘸酱名单中哪位选手，或独立选手')]:
                add('identity:'+name,'','','选手别名',name+'：队伍已由阶段成绩确认，仅需统一确认是否为 '+target+'；确认后批量应用全部相关对局。')
    confirmation=payload.get('reconciliation',{}).get('userConfirmation',{})
    if confirmation:
        issues=[i for i in issues if not (
            (i['id']=='source-omissions' and confirmation.get('unknownPolicy')=='retain') or
            (i['id'].startswith('identity:') and confirmation.get('identitiesConfirmed')) or
            (i['id']=='source-adjustment:_404' and confirmation.get('latePenaltyConfirmed')))]
    stages=[]
    for st in payload.get('stages',[]):
        matches=[m for m in payload.get('results',[]) if m.get('stageId')==st['id']]
        stages.append(dict(id=st['id'],name=st['name'],matches=len(matches),issues=sum(i['stage']==st['id'] for i in issues)))
    return dict(name=payload.get('name',''),stages=stages,teams=len(teams),players=len(players),matches=len(payload.get('results',[])),issues=issues,coverage=payload.get('coverage',{}))
