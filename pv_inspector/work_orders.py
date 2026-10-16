"""Loss, priority and work orders from diagnoses (과제_기획서 4.5, 4.6).

Diagnoses are grouped by inverter → junction box and then by the kind of work (electrical
check, cleaning, weeding, field check, re-shoot), so one visit to a junction box handles
everything of one kind there. Visits are ordered by priority tier, then by walking to the
nearest junction box. Orders are drafts until an operator issues them (history.set_status).
"""
from __future__ import annotations

import hashlib
import math

URGENCY_RANK = {'최우선': 0, '우선': 1, '보통': 2, '낮음': 3}
FIELD_KINDS = ('operation', 'electrical', 'field_check', 'clean', 'weed', 'manual')
SITE_KINDS = ('reshoot', 'recheck', 'retake')   # drone work: one list for the whole site
CAUTION = {'operation': 2, 'electrical': 2, 'manual': 2, 'field_check': 1}   # clean, weed: 0


def ai_downgrade(d, kb):
    """(new kind, reason) when the GPT appearance check makes a field visit unnecessary, else None.

    Only from what the rules decided (rule_kind), never for electrical or operating checks, and for
    a field check only when the rules had a shade cause on the list too: model and rules must agree.
    Nor when the model's own review raised the work (e.g. weeding → field check): it then disagrees
    with its appearance call and the cautious side wins.
    """
    look, rules = d.get('appearance'), kb.get('ai_downgrade', {})
    if CAUTION.get(d['kind'], 0) > CAUTION.get(d.get('rule_kind', d['kind']), 0):
        return None
    cond = rules.get(d.get('rule_kind', d['kind']))
    if not look or not cond or look['confidence'] not in cond['confidence'] or look['label'] not in cond['to']:
        return None
    need = cond.get('rule_needs_one_of')
    if need and not set(need) & set(d.get('rule_rules', [])):
        return None
    return cond['to'][look['label']], f"GPT 외관 '{look['label']}'({look['confidence']})" + (' + 규칙 음영 후보' if need else '')


def audit_sample(module_id, every):
    """A fixed one-in-`every` share of downgrades stays in the field to measure whether downgrading was right."""
    return bool(every) and int(hashlib.sha256(module_id.encode()).hexdigest(), 16) % every == 0


def work_kind(d, kb):
    """Rule routing, then the AI downgrade; marks the diagnosis with what happened."""
    if d.get('verdict') == 'recheck' and not d['safety'] and d['kind'] != 'exclude'             and not any(c['rule'] in kb.get('field_from_recheck', []) for c in d['candidates']):
        return 'recheck'
    kind = d['kind']
    found = ai_downgrade(d, kb)
    if found and found[0] != kind:
        if audit_sample(d['module_id'], kb.get('ai_downgrade', {}).get('audit_every', 0)):
            d['ai_audit'] = f"{found[1]} → {kb['kinds'][found[0]]['label']} 대상이지만 검증 표본으로 현장에 남김"
            return kind
        d['ai_downgraded'] = f"{found[1]} → {kb['kinds'][found[0]]['label']}"
        return found[0]
    return kind


def loss_w(diagnosis, kb):
    """Rated-power loss estimate for one module's primary cause (4.5); a string counts once per string."""
    k = kb['loss_w']
    rule = diagnosis['candidates'][0]['rule']
    delta = max(diagnosis.get('relative_temp') or 0.0, 0.0)
    cell = min(delta * k['cell_w_per_c'], k['module_rated'] * k['cell_max_share'])
    return {'string_wide': k['module_rated'] * k['string_modules'], 'diode': k['module_rated'] * k['diode_share'],
            'whole_module': k['module_rated'], 'reflection': 0.0, 'inverter_wide': 0.0, 'jb_wide': 0.0}.get(rule, cell)


def priority_key(d):
    return (not d['safety'], URGENCY_RANK.get(d['urgency'], 9), -d['loss_w'], -(d.get('votes') or 0))


def _route(groups):
    """Nearest-neighbour walk over junction boxes, starting at the most urgent one."""
    todo = dict(groups)
    if not todo:
        return []
    current = min(todo, key=lambda jb: todo[jb]['key'])
    order = []
    while todo:
        here = todo.pop(current)
        order.append(current)
        if not todo:
            break
        current = min(todo, key=lambda jb: (todo[jb]['key'][:2], math.dist(here['xy'], todo[jb]['xy'])))
    return order


def build(diagnoses, kb, flight_id, viewer_link=None, retake=()):
    """Draft work orders plus the safety list that must be notified at once.

    `retake` = modules photographed only while turning; they go on the re-shoot list.
    """
    kinds = kb['kinds']
    for d in diagnoses:
        d['loss_w'] = loss_w(d, kb)
    seen_strings = set()
    for d in sorted(diagnoses, key=priority_key):
        if d['candidates'][0]['rule'] == 'string_wide':
            if d['string_id'] in seen_strings:
                d['loss_w'] = 0.0  # the string's loss is counted on its first module
            seen_strings.add(d['string_id'])

    grouped = {}
    for d in diagnoses:
        kind = work_kind(d, kb)
        if kind == 'exclude':
            continue
        key = ('site', kind) if kind in SITE_KINDS else (d['jb_id'], kind)
        grouped.setdefault(key, []).append(d)

    orders = []
    for (jb, kind), items in grouped.items():
        items.sort(key=priority_key)
        lead = items[0]
        xy = [(d['east_m'], d['north_m']) for d in items if d.get('east_m') is not None]
        centre = tuple(sum(v) / len(v) for v in zip(*xy)) if xy else (0.0, 0.0)
        strings = sorted({d['string_id'] for d in items if d.get('string_id')})
        label = kinds[kind]['label']
        urgency = min((d['urgency'] for d in items), key=lambda u: URGENCY_RANK.get(u, 9))
        lines = []
        for d in items:
            c = d['candidates'][0]
            evidence = '; '.join(e['text'] for e in c['evidence'][:2])
            look = f" · 외관: {d['appearance']['label']}" if d.get('appearance') else ''
            link = f" · 3D: {viewer_link(d['module_id'])}" if viewer_link else ''
            flag = f" · [검증 표본: {d['ai_audit']}]" if d.get('ai_audit') else (f" · [AI 하향: {d['ai_downgraded']}]" if d.get('ai_downgraded') else '')
            lines.append(f"- {d['module_id']} ({d['string_id']}): {d['primary']} [{c['confidence']}] → {d['action']}. 근거: {evidence}{look}{flag}{link}")
        where = '현장 전체' if jb == 'site' else f"{lead['inverter_id']} › {jb}"
        orders.append(dict(
            order_id=f'{flight_id}-{jb}-{kind}', inverter_id=lead['inverter_id'] if jb != 'site' else None,
            jb_id=None if jb == 'site' else jb, string_id=strings[0] if len(strings) == 1 else None,
            action_kind=kind, priority=0, safety=any(d['safety'] for d in items),
            loss_w=round(sum(d['loss_w'] for d in items), 1), route_order=0,
            modules=[d['module_id'] for d in items],
            title=f"[{urgency}] {where} {label} {len(items)}장",
            instructions=f"{where} · {label} · 스트링 {', '.join(strings) or '-'}\n" + '\n'.join(lines),
            equipment=kinds[kind]['equipment'], key=priority_key(lead), xy=centre))

    by_jb = {}
    for o in orders:
        if o['action_kind'] in FIELD_KINDS:
            g = by_jb.setdefault(o['jb_id'], {'key': o['key'], 'xy': o['xy']})
            g['key'] = min(g['key'], o['key'])
    stop = {jb: i + 1 for i, jb in enumerate(_route(by_jb))}
    orders.sort(key=lambda o: (o['action_kind'] not in FIELD_KINDS, stop.get(o['jb_id'], 999), o['key']))
    for rank, o in enumerate(sorted(orders, key=lambda o: o['key']), start=1):
        o['priority'] = rank
    for i, o in enumerate(orders, start=1):
        o['route_order'] = i
        o.pop('key'); o.pop('xy')
    if len(retake):
        orders.append(dict(order_id=f'{flight_id}-site-retake', inverter_id=None, jb_id=None, string_id=None, action_kind='retake',
                           priority=len(orders) + 1, safety=False, loss_w=0.0, route_order=len(orders) + 1, modules=sorted(retake),
                           title=f"[보통] 현장 전체 {kinds['retake']['label']} {len(retake)}장",
                           instructions='회전 구간 영상에서만 찍혀 판정하지 않은 모듈입니다. 다음 촬영에서 직선 비행으로 다시 찍습니다.',
                           equipment=kinds['retake']['equipment']))
    safety = [d['module_id'] for d in diagnoses if d['safety']]
    return orders, safety
