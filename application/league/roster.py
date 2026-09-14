from .domain import optional_note
"""Roster changes preserve result team snapshots and accept optional notes."""
import datetime, re
from .domain import find, require, label

def update_roster(d,kind,action,b):
    is_team=action=='team-update'
    require(not is_team or kind=='team','个人赛不设置队伍')
    rows=d['teams' if is_team else 'players'];row=find(rows,b.get('id'))
    name=label(b.get('name',row['name']))
    active=b.get('active',row['active']);require(type(active) is bool,'参赛状态格式错误')
    reason=optional_note(b.get('reason'))
    pending=[m for m in d['matches'] if m['state']=='draft' and any(s['teamId' if is_team else 'playerId']==row['id'] for s in m['seats'])]
    if is_team:
        require(not any(x['id']!=row['id'] and x['name']==name for x in rows),'队伍名称重复')
        color=b.get('color',row['color']);require(isinstance(color,str) and re.fullmatch(r'#[0-9a-fA-F]{6}',color),'代表色必须为六位十六进制颜色')
        require(not any(t['id']!=row['id'] and t['color'].lower()==color.lower() for t in rows),'该颜色已被其他队伍使用，请选择不同颜色')
        if not active: require(not pending,'该队伍仍有待赛对局，请先取消或调整赛程')
        row.update(name=name,color=color,active=active)
    else:
        number=label(b.get('number',row['number']))
        require(not any(x['id']!=row['id'] and x['number']==number for x in rows),'报名编号重复')
        tid=b.get('teamId',row['teamId']) or None
        require(kind=='team' or tid is None,'个人赛不能设置队伍')
        if tid:
            team=find(d['teams'],tid)
            if tid!=row['teamId']: require(team['active'],'不能转入已停用队伍')
        if tid!=row['teamId'] or not active:
            require(not pending,'选手仍在待赛名单中，请先调整该场出战名单或取消对局')
        bio=b.get('bio',row.get('bio',''));require(isinstance(bio,str) and len(bio)<=500,'公开简介最多500字')
        if tid!=row['teamId']:
            row.setdefault('membershipHistory',[]).append(dict(fromTeamId=row['teamId'],toTeamId=tid,effectiveAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),reason=reason))
        row.update(name=name,number=number,teamId=tid,active=active,bio=bio)
    return d


def next_number(players):
    used={str(p['number']) for p in players}
    n=max([int(v) for v in used if v.isdecimal()]+[0])+1
    while str(n) in used:n+=1
    return str(n)

def next_color(teams):
    used={t['color'].lower() for t in teams}
    for color in ['#ba3c30','#315b9b','#26745a','#a77a24','#785194','#d06b38','#478e99','#935467']:
        if color not in used:return color
    import colorsys
    for i in range(10000):
        rgb=colorsys.hsv_to_rgb((i*0.61803398875)%1,0.62,0.68)
        color='#'+''.join(f'{round(x*255):02x}' for x in rgb)
        if color not in used:return color
    raise ValueError('没有可分配的队伍颜色')
