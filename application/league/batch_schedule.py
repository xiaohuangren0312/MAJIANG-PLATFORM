"""Team tournament schedule drafts and atomic batch validation."""
import re
from collections import defaultdict
from datetime import date
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from .domain import Invalid, apply, eligible_ids, live_stage, require
from .event_tables import catalog, stage_tables
from .permissions import authorize


def available_tables(document, stage):
    if 'tables' in document or 'tableNumbers' in stage:
        return stage_tables(document, stage)
    return [table['number'] for table in catalog(document)]


@login_required
@never_cache
@ensure_csrf_cookie
@require_GET
def page(request, id):
    from .views import allowed
    event = get_object_or_404(allowed(request.user), pk=id)
    if event.kind == 'personal':
        from django.shortcuts import redirect
        authorize(event, request.user, 'pairing-preview')
        return redirect(f'/manage/?event={event.pk}&page=pairing')
    authorize(event, request.user, 'batch-schedule')
    document = event.document
    stages = []
    for stage in document['stages']:
        if stage.get('locked'):
            continue
        try:
            eligible = eligible_ids(document, 'team', stage['id'])
        except Invalid:
            eligible = set()
        stages.append(dict(id=stage['id'], name=stage['name'],
                           teams=[team['id'] for team in document['teams']
                                  if team['active'] and team['id'] in eligible],
                           tables=available_tables(document, stage)))
    matches = [dict(day=m['date'], time=m['time'], table=m['number'], stage=m['stageId'],
                    teams=[s['teamId'] for s in m['seats']]) for m in document['matches']
               if m['state'] != 'cancelled']
    config = dict(id=str(event.pk), revision=event.revision, stages=stages, matches=matches,
                  teams={t['id']: t['name'] for t in document['teams']},
                  tables={t['number']: t['name'] for t in catalog(document)})
    return render(request, 'batch_schedule.html', {'config': config, 'event': event})


def commit(document, kind, body):
    require(kind == 'team' and not document.get('archive') and not document.get('historySnapshot'),
            '当前赛事不能批量排程')
    stage = live_stage(document, body.get('stageId'))
    tables = set(available_tables(document, stage))
    rows = body.get('rows')
    require(isinstance(rows, list) and 1 <= len(rows) <= 500, '每批可保存 1 至 500 场')
    used_teams, used_tables = defaultdict(set), defaultdict(set)
    for match in document['matches']:
        if match['state'] != 'cancelled':
            slot = match['date'], match['time']
            used_tables[slot].add(match['number'])
            used_teams[slot].update(s['teamId'] for s in match['seats'])
    # Validate individual matches with the existing match creation rules. Track
    # slot conflicts across the full event, without copying its history per row.
    context = {k: document[k] for k in ('stages', 'teams', 'rules', 'settlements')}
    context.update(matches=[], players=[])
    if 'tables' in document:
        context['tables'] = document['tables']
    created = []
    for index, row in enumerate(rows, 1):
        try:
            require(isinstance(row, dict), '赛程格式错误')
            day, time, number, teams = (row.get(k) for k in ('day', 'time', 'table', 'teams'))
            require(isinstance(day, str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', day), '日期格式错误')
            require(isinstance(time, str), '时间格式错误')
            require(type(number) is int and number in tables, '桌次不在本阶段用桌范围内')
            require(isinstance(teams, list) and len(teams) == 4 and all(isinstance(t, str) for t in teams),
                    '每桌须选择四支队伍')
            slot = day, time
            require(number not in used_tables[slot], '该时段桌次已占用')
            require(not used_teams[slot].intersection(teams), '队伍在该时段已有比赛')
            match = apply(context, kind, 'match', dict(stageId=stage['id'], date=day, time=time,
                          number=number, seats=[{'teamId': t} for t in teams]))['matches'][0]
            created.append(match)
            used_tables[slot].add(number)
            used_teams[slot].update(teams)
        except Invalid as exc:
            raise Invalid(f'第 {index} 场：{exc}') from exc
    return {**document, 'matches': [*document['matches'], *created]}
