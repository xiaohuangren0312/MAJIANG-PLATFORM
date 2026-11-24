"""Excel-assisted team schedules. The spreadsheet is input, never executable content."""
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, time
from io import BytesIO
from itertools import combinations
from zipfile import ZipFile

from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from .batch_schedule import available_tables, commit
from .domain import Invalid, eligible_ids, require
from .event_tables import catalog
from .permissions import authorize

HEAD = ('比赛阶段', '比赛日期', '开赛时间', '桌名', '队伍一', '队伍二', '队伍三', '队伍四')
SALT = 'team-schedule-excel-v1'


def reference(doc):
    tables = catalog(doc)
    result = []
    for stage in doc['stages']:
        if stage.get('locked'):
            continue
        try:
            eligible = eligible_ids(doc, 'team', stage['id'])
        except Invalid:
            continue
        result.append((stage, [t for t in doc['teams'] if t['active'] and t['id'] in eligible],
                       [t for t in tables if t['number'] in available_tables(doc, stage)]))
    return result


def template(ref, head=HEAD, slots=(), rankings=()):
    book = Workbook()
    sheet = book.active
    sheet.title = '赛程'
    sheet.append(head)
    for slot in slots:
        sheet.append(slot)
        for cell in sheet[sheet.max_row]:
            cell.data_type = "s"
    if rankings:
        tab = book.create_sheet("本轮排名")
        tab.append(("顺序","选手编号","姓名","已赛场次"))
        for r in rankings:
            tab.append((r["order"],r["number"],r["name"],r["games"]))
            for cell in tab[tab.max_row][1:3]:
                cell.data_type = "s"
    info = book.create_sheet('赛事参考')
    info.append(('比赛阶段', '风位', '类别', '名称'))
    for stage, teams, tables in ref:
        for kind, entries in [('选手' if head != HEAD else '队伍', teams), ('桌子', tables)]:
            for item in entries:
                info.append((stage['name'], '固定' if stage.get('windMode') == 'fixed' else '随机', kind, item['name']))
                for cell in info[info.max_row]:
                    cell.data_type = 's'
    for tab in book:
        tab.freeze_panes = 'A2'
        for cell in tab[1]:
            cell.font = Font(bold=True, color='86412F')
            tab.column_dimensions[cell.column_letter].width = 23
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def read_rows(upload, head=HEAD):
    require(upload and upload.size <= 2_000_000, '请选择 2 MB 以内的 .xlsx 文件')
    try:
        with ZipFile(upload) as archive:
            require(len(archive.infolist()) < 200 and sum(i.file_size for i in archive.infolist()) <= 8_000_000, '工作簿过大')
        upload.seek(0)
        book = load_workbook(upload, read_only=True, keep_links=False)
        try:
            require('赛程' in book.sheetnames, '缺少「赛程」工作表')
            sheet = book['赛程']
            sheet.reset_dimensions()
            rows = []
            for index, cells in enumerate(sheet.rows, 1):
                require(index <= 2000, '工作表超过 2000 行，请清除多余空行')
                values = [c.value for c in cells]
                if not any(v is not None for v in values):
                    continue
                require(len(values) <= 8 or all(v is None for v in values[8:]), f'第 {index} 行有多余列')
                require(all(c.data_type not in ('f','e') for c in cells), f'第 {index} 行含公式或错误值，请填实际值')
                if index == 1:
                    require(tuple(values[:8]) == head, '首行表头与模板不一致')
                else:
                    require(len(values) >= 8 and all(v is not None for v in values[:8]), f'第 {index} 行有空项')
                    rows.append((index, values[:8]))
                    require(len(rows) <= 500, '每次最多导入 500 场')
            require(tuple(c.value for c in next(sheet.iter_rows(min_row=1,max_row=1,max_col=8))) == head, '首行表头与模板不一致')
            require(rows, '请先在赛程表填写比赛')
            return rows
        finally:
            book.close()
    except Invalid:
        raise
    except Exception as exc:
        raise Invalid('无法读取工作簿，请上传有效的 .xlsx 文件') from exc


def lookup(entries, value, key, label):
    hits = [e[key] for e in entries if e['name'] == str(value).strip()]
    require(len(hits) == 1, f'{label}「{value}」不存在、不可用或重名')
    return hits[0]


def resolve(ref, rows):
    groups = defaultdict(list)
    for index, values in rows:
        stage, day, start, table, *teams = values
        try:
            sid = lookup([s for s, _, _ in ref], stage, 'id', '阶段')
            _, roster, tables = next(r for r in ref if r[0]['id'] == sid)
            if isinstance(day, datetime):
                day = day.date()
            if isinstance(start, (datetime, time)):
                require(not start.second and not start.microsecond, '开赛时间请精确到分钟')
                start = start.strftime('%H:%M')
            row = dict(day=str(day).strip(), time=str(start).strip(), table=lookup(tables, table, 'number', '桌名'),
                       teams=[lookup(roster, name, 'id', '队伍') for name in teams])
            require(len(set(row['teams'])) == 4, '同桌有重复队伍')
            groups[sid].append((index, row))
        except Invalid as exc:
            raise Invalid(f'第 {index} 行：{exc}') from exc
    return dict(groups)


def simulate(doc, groups):
    for sid, items in groups.items():
        try:
            doc = commit(doc, 'team', dict(stageId=sid, rows=[row for _, row in items]))
        except Invalid as exc:
            hit = re.match(r'第 (\d+) 场：(.*)', str(exc))
            if not hit:
                raise
            index, row = items[int(hit[1])-1]
            names = {t['id']:t['name'] for t in doc['teams']}
            table = next(t['name'] for t in catalog(doc) if t['number']==row['table'])
            lineup = '、'.join(names[t] for t in row['teams'])
            raise Invalid(f"第 {index} 行（{row['day']} {row['time']} {table}，{lineup}）：{hit[2]}") from exc
    return doc


CHECKS = ('每队出战', '每队轮空', '两队同桌', '四风座次', '每日阵容', '各桌出战')


def audit_schedule(teams, tables, rows, fixed):
    names = {team['id']: team['name'] for team in teams}
    days = sorted({row['day'] for row in rows})
    played = defaultdict(set)
    seats = defaultdict(list)
    starts = defaultdict(lambda: defaultdict(set))
    pairs = defaultdict(list)
    tables_used = Counter()
    for row in rows:
        day = row['day']
        for wind, team in enumerate(row['teams']):
            played[team].add(day)
            seats[team, day].append(wind)
            starts[day][row['time']].add(team)
            tables_used[team, row['table']] += 1
        for pair in combinations(sorted(row['teams']), 2):
            pairs[pair].append(day)

    def span(values):
        values = list(values)
        lo, hi = min(values), max(values)
        return str(lo) if lo == hi else f'{lo}–{hi}'

    def item(index, result, warning, details):
        return dict(label=CHECKS[index], result=result, warning=warning, details=details)

    appearances = {t: sum(len(seats[t,d]) for d in days) for t in names}
    days_played = [len(played[t]) for t in names]
    yield item(0, f'每队出战 {span(days_played)} 天、{span(appearances.values())} 个半庄',
               len(set(days_played))>1 or len(set(appearances.values()))>1,
               [f'{name}：{len(played[t])} 天、{appearances[t]} 个半庄' for t,name in names.items()])
    rests = [len(days)-n for n in days_played]
    consecutive = [name for t,name in names.items() if any(a not in played[t] and b not in played[t] for a,b in zip(days,days[1:]))]
    yield item(1, f'每队轮空 {span(rests)} 天；'+('连续轮空：'+'、'.join(consecutive) if consecutive else '无连续轮空'),
               len(set(rests))>1 or bool(consecutive),
               [d+'：'+('、'.join(name for t,name in names.items() if d not in played[t]) or '无轮空') for d in days])
    all_pairs = list(combinations(sorted(names),2))
    totals = [len(pairs[k]) for k in all_pairs]
    pair_days = [len(set(pairs[k])) for k in all_pairs]
    yield item(2, f'{len(all_pairs)} 种组合，每对同桌 {span(pair_days)} 天、{span(totals)} 个半庄',
               len(set(totals))>1 or len(set(pair_days))>1,
               [f'{names[a]} / {names[b]}：{d} 天、{n} 个半庄' for (a,b),d,n in zip(all_pairs,pair_days,totals)])
    if fixed:
        winds = {t:[sum(seats[t,d].count(i) for d in days) for i in range(4)] for t in names}
        repeated = sum(len(v)!=len(set(v)) for v in seats.values())
        yield item(3, '每队各风位 '+span(v for counts in winds.values() for v in counts)+' 次；'+(f'{repeated} 个队日重复座次' if repeated else '同日无重复座次'),
                   any(len(set(v))>1 for v in winds.values()) or bool(repeated),
                   [name+'：'+'、'.join(f'{wind} {n}' for wind,n in zip('东南西北',winds[t])) for t,name in names.items()])
    daily = {d:frozenset().union(*starts[d].values()) for d in days}
    frequency = Counter(daily.values())
    varying = [d for d in days if len({frozenset(v) for v in starts[d].values()})>1]
    yield item(4,f'{len(frequency)} 种出战阵容，每种安排 {span(frequency.values())} 天；'+('部分日期分时段换队' if varying else '各日各时段出战队伍一致'),
               bool(varying) or len(set(frequency.values()))>1,
               [d+'：'+'、'.join(names[t] for t in sorted(group)) for d,group in daily.items()])
    values = [[tables_used[t,table['number']] for table in tables] for t in names]
    yield item(5,f'{len(tables)} 张阶段用桌，每队在各桌出战 '+span(n for v in values for n in v)+' 次',
               any(len(set(v))>1 for v in values),
               [name+'：'+'、'.join(f"{table['name']} {n} 次" for table,n in zip(tables,v)) for name,v in zip(names.values(),values)])


def statistics(ref, groups):
    for s, teams, tables in ref:
        if s['id'] not in groups:
            continue
        counts, winds, pairs = Counter(), defaultdict(Counter), Counter()
        for _, row in groups[s['id']]:
            counts.update(row['teams'])
            pairs.update(combinations(sorted(row['teams']), 2))
            for seat, team in enumerate(row['teams']):
                winds[team][seat] += 1
        names = {t['id']:t['name'] for t in teams}
        yield dict(audit=list(audit_schedule(teams,tables,[row for _,row in groups[s['id']]],s.get('windMode')=='fixed')), stage=s['name'], fixed=s.get('windMode')=='fixed',
                   counts=[(name, counts[t], [winds[t][i] for i in range(4)]) for t,name in names.items()],
                   pairs=[(names[a],names[b],n) for (a,b),n in sorted(pairs.items(),key=lambda item:-item[1])])


PERSONAL_HEAD = (*HEAD[:4], '选手一', '选手二', '选手三', '选手四')


def personal_reference(doc):
    result = []
    for stage in doc['stages']:
        if stage.get('locked'):
            continue
        try:
            eligible = eligible_ids(doc, 'personal', stage['id'])
        except Invalid:
            continue
        players = [p for p in doc['players'] if p['id'] in eligible and p['active'] and not p.get('nonPlayingCoach')]
        entries = [dict(p, name=f"{p['number']} · {p['name']}") for p in players]
        tables = [t for t in catalog(doc) if t['number'] in available_tables(doc, stage)]
        if 'tables' not in doc and 'tableNumbers' not in stage:
            from .event_tables import display
            tables = [dict(name=display(doc,n),number=n) for n in range(1,1+len(players)//4)]
        result.append((stage, entries, tables))
    return result


def round_preview(doc, groups):
    from .pairing import context, commit as save_round
    require(len(groups)==1, '每次只能导入当前一轮')
    sid, items = next(iter(groups.items()))
    rows = sorted((r for _,r in items),key=lambda r:r['table'])
    require(len({(r['day'],r['time']) for r in rows})==1,'本轮所有桌必须在同一时间开赛')
    p = context(doc,'personal',dict(stageId=sid,date=rows[0]['day'],time=rows[0]['time'],
                                    tableNumbers=[r['table'] for r in rows]) if 'tables' in doc else
                dict(stageId=sid,date=rows[0]['day'],time=rows[0]['time']))
    require(sorted(p['tableNumbers'])==[r['table'] for r in rows],'请排入本轮全部桌次')
    ranking=p['ranking']
    p['tables']=[dict(number=n,players=[r['id'] for r in ranking[i*4:i*4+4]]) for i,n in enumerate(p['tableNumbers'])]
    tables=[dict(number=r['table'],players=r['teams']) for r in rows]
    save_round(doc,'personal',p,tables)
    return p,tables


@login_required
@never_cache
@require_http_methods(['GET','POST'])
def page(request, id):
    from .views import allowed
    from .pairing import context
    event=get_object_or_404(allowed(request.user),pk=id)
    personal=event.kind=='personal'
    authorize(event,request.user,'pairing-preview' if personal else 'batch-schedule')
    ref=personal_reference(event.document) if personal else reference(event.document)
    head=PERSONAL_HEAD if personal else HEAD
    selected=request.POST.getlist('checks') if 'check_selection' in request.POST else CHECKS
    stages=[dict(id=s['id'],name=s['name'],fixed=s.get('windMode')=='fixed',entries=entries,tables=tables)
            for s,entries,tables in ref]
    ctx=dict(event=event,stages=stages,checks=() if personal else CHECKS,selected=selected,personal=personal)
    data=request.POST
    try:
        if 'template' in request.GET or data.get('mode')=='template':
            slots=[]
            rankings=[]
            if 'stage' in data:
                ref=[r for r in ref if r[0]['id']==data['stage']]
                require(bool(ref),'请选择有效阶段')
                stage,entries,tables=ref[0]
                entries=[p for p in entries if p['id'] in data.getlist('entries')]
                tables=[t for t in tables if str(t['number']) in data.getlist('tables')]
                days=sorted(set(data.getlist('days')))
                times=sorted(set(data.getlist('times')))
                require(len(entries)>=4 and tables and days and times,'请选择名单、比赛日、时间和用桌')
                require(len(days)*len(times)*len(tables)<=500,'每批最多 500 场')
                if personal:
                    require(len(days)==len(times)==1,'每次安排一轮')
                    p=context(event.document,'personal',dict(stageId=stage['id'],date=days[0],time=times[0],**({'tableNumbers':[t['number'] for t in tables]} if 'tables' in event.document else {})))
                    rankings=p['ranking']
                    require(len(entries)==len(rankings) and len(tables)==len(rankings)//4,'请选择本轮全部选手及对应桌数')
                ref=[(stage,entries,tables)]
                slots=[(stage['name'],day,time_,t['name']) for day in days for time_ in times for t in tables]
            return HttpResponse(template(ref,head,slots,rankings),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="schedule.xlsx"'})
        if request.method=='POST':
            if data.get('mode')=='edit':
                require(str(event.revision)==data.get('revision'),'赛事已更新，请重新上传')
                values=json.loads(data.get('rows','[]'))
                require(isinstance(values,list) and 0<len(values)<=500 and all(isinstance(v,list) and len(v)==8 and all(isinstance(x,str) for x in v) for v in values),'预览格式错误')
                rows=list(enumerate(values,2))
            else:
                rows=read_rows(request.FILES.get('workbook'),head)
            if data.get('scope'):
                scope=json.loads(data['scope'])
                require(isinstance(scope,dict) and isinstance(scope.get('entries'),list) and isinstance(scope.get('tables'),list),'排程范围无效')
                ref=[(s,[p for p in entries if p['id'] in scope['entries']],
                        [t for t in tables if str(t['number']) in scope['tables']])
                     for s,entries,tables in ref if s['id']==scope.get('stage')]
            groups=resolve(ref,rows)
            if personal:
                p,tables=round_preview(event.document,groups)
                token=signing.dumps(dict(event=str(id),revision=event.revision,preview=p),salt='pairing',compress=True)
                stats=[]
            else:
                simulate(event.document,groups)
                token=signing.dumps((str(id),event.revision,groups),salt=SALT,compress=True)
                stats=list(statistics(ref,groups))
                tables=[]
            clean=[]
            for sid,items in groups.items():
                stage,entries,ts=next(r for r in ref if r[0]['id']==sid)
                names={p['id']:p['name'] for p in entries}
                table_names={t['number']:t['name'] for t in ts}
                clean.extend([stage['name'],r['day'],r['time'],table_names[r['table']],*[names[t] for t in r['teams']]] for _,r in items)
            preview=dict(rows=clean,stats=stats,token=token,tables=tables,revision=event.revision)
            if data.get('ajax'):
                return JsonResponse(preview)
            ctx.update(token=token,preview=preview,rows=clean)
    except (Invalid,ValueError) as exc:
        if data.get('ajax'):
            return JsonResponse(dict(error=str(exc)),status=400)
        ctx['error']=str(exc)
    return render(request,'schedule_excel.html',ctx)
