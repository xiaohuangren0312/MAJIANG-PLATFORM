"""Excel-readable frozen CSV archive, with safe textual cells."""
import csv,io
from django.http import HttpResponse,Http404
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .models import Event

def csv_text(document,name,kind):
    out=io.StringIO(newline='');writer=csv.writer(out)
    def cell(v):
        if v is None:return '未知'
        if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')):return "'"+v
        return v
    def row(*values):writer.writerow([cell(v) for v in values])
    def pt(value):return value/10 if value is not None else None
    teams={t['id']:t['name'] for t in document['teams']};players={p['id']:p['name'] for p in document['players']};stages={s['id']:s['name'] for s in document['stages']}
    a=document['archive'];row('赛事',name);row('类型','团队赛' if kind=='team' else '个人赛');row('归档时间',a['at']);row('归档操作人',a['actor']);row()
    row('最终排名');row('名次','对象','竞技分PT','阶段净分PT','带入PT')
    for r in a['standings']['rows']:row(r['rank'],r['name'],pt(r['total']),pt(r['raw']),pt(r['carry']))
    row();row('全部个人累计');row('选手','羁绊','场数','净分PT','一位','二位','三位','四位')
    for r in a['standings']['personalOverall']:row(r['name'],'是' if r.get('bond') else '',r['games'],pt(r['raw']),*r['places'])
    row();row('报名名单');row('编号','选手','身份','常驻队伍','阶段代表队伍')
    for p in document['players']:row(p['number'],p['name'],'羁绊' if p.get('bond') else '正式',teams.get(p['teamId'],''),'；'.join(stages.get(s,s)+'：'+teams.get(t,t) for s,t in p.get('bondStages',{}).items()))
    row();row('计分规则');row('版本','名称','起始点','返点','一位PT','二位PT','三位PT','四位PT')
    for rule in document['rules']:row(rule['version'],rule['name'],rule['start'],rule['return'],*[pt(x) for x in rule['bonuses']])
    row();row('阶段结转');row('源阶段','目标阶段','对象','带入PT')
    for transfer in document['settlements']:
        for entity,value in transfer['rows'].items():row(stages[transfer['source']],stages[transfer['target']],(teams if transfer['kind']=='team' else players).get(entity,entity),pt(value))
    row();row('赛程与逐场战果');row('对局ID','阶段','日期','时间','桌','状态','座次','队伍','选手','羁绊','终局点数','顺位','基础PT','个人罚分PT','个人净分PT','队伍贡献PT','规则版本')
    for m in document['matches']:
        n=m['number'];table=''
        while n:table=chr(65+(n-1)%26)+table;n=(n-1)//26
        for i,s in enumerate(m['seats']):row(m['id'],stages[m['stageId']],m['date'],m['time'],table,{'published':'已完赛','cancelled':'已取消','draft':'待赛'}[m['state']],['东','南','西','北'][i],teams.get(s['teamId'],''),players.get(s['playerId'],''),'羁绊' if s.get('bond') else '',s.get('score'),s.get('rank'),pt(s.get('base')),pt(s.get('penalty')),pt(s.get('points')),pt(s.get('teamPoints')),m['rule']['version'])
    row();row('罚分与役满');row('对局ID','类型','选手','分值PT或倍数','范围或役种','备注或局次')
    for m in document['matches']:
        for p in m['penalties']:row(m['id'],'罚分',players.get(p['playerId'],''),pt(p['amount']),p['scope'],p.get('explanation',''))
        for y in m['yakuman']:row(m['id'],'役满',players.get(y['playerId'],''),y['multiplier'],'、'.join(y['types']),y['round'])
    return out.getvalue()

@login_required
def download(request,id):
    e=get_object_or_404(Event,pk=id)
    if not(request.user.is_superuser or e.editors.filter(pk=request.user.pk).exists()):raise Http404
    a=e.document.get('archive')
    if e.document.get('historySnapshot'):content=history_csv(e)
    elif a:content=a.get('csvExport') or csv_text(e.document,e.name,e.kind)
    else:raise Http404
    response=HttpResponse(content.encode('utf-8-sig'),content_type='text/csv; charset=utf-8')
    response['Content-Disposition']=f'attachment; filename="tournament-{e.id}.csv"'
    response['Cache-Control']='private, no-store'
    return response


def history_csv(event):
    from .projection import public_event
    p=public_event(event);out=io.StringIO(newline='');w=csv.writer(out)
    def row(*values):
        w.writerow(['未知' if v is None else "'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for v in values])
    def pt(v):return v/10 if v is not None else None
    teams={t['id']:t['name'] for t in p['teams']};players={x['id']:x['name'] for x in p['players']};stages={s['id']:s['name'] for s in p['stages']}
    row('历史赛事',event.name);row('版本',event.revision);row('说明','导出当前有效更正结果；未知字段不推造，原表快照保留');row()
    row('队伍名单');row('队伍ID','名称')
    for t in p['teams']:row(t['id'],t['name'])
    row();row('选手名单');row('选手ID','姓名','当前队伍')
    for x in p['players']:row(x['id'],x['name'],teams.get(x.get('teamId')))
    row();row('各阶段排行榜');row('阶段','积分口径','对象类型','名次','姓名','积分PT','场数','一位','二位','三位','四位','平均顺位')
    for stage,metrics in p.get('statistics',{}).items():
        for metric,kinds in metrics.items():
            for kind,rows in kinds.items():
                for r in rows:row(stages.get(stage,'全赛事'),{'raw':'原始累计','competitive':'竞技分'}.get(metric,metric),'队伍' if kind=='team' else '选手',r.get('rank'),r['name'],pt(r.get('total')),r.get('games'),*r.get('places',[None]*4),r.get('avgRank'))
    row();row('逐场战果');row('ID','阶段','日期','时间','场次','座次','队伍','选手','终局点数','顺位','个人PT','队伍PT','来源')
    for m in p['results']:
        for i,s in enumerate(m['seats']):row(m['id'],stages.get(m['stageId']),m.get('date'),m.get('time'),m.get('number'),i+1,teams.get(s.get('teamId')),players.get(s.get('playerId')),s.get('score'),s.get('rank'),pt(s.get('points')),pt(s.get('teamPoints')),m.get('source',''))
    row();row('赛程');row('ID','阶段','日期','时间','状态')
    for m in p.get('schedule',[]):row(m['id'],stages.get(m['stageId']),m.get('date'),m.get('time'),m.get('state'))
    row();row('历史更正记录');row('对局ID','操作人','时间','备注')
    for c in event.document.get('historyCorrections',[]):row(c['id'],c.get('actor'),c.get('at'),c.get('reason',''))
    return out.getvalue()
