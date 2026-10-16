"""Site history database, keyed by drawing module ID (과제_기획서 6.1, 6.4).

One SQLite file holds every flight's module states, diagnoses, work orders and the
field results that come back. Analysis outputs can be rebuilt from the images; field
results and work orders cannot, so this file is what must be backed up (6.6).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

ORDER_STATUS = ['초안', '발행', '점검 완료', '조치 완료', '종결']

SCHEMA = """
CREATE TABLE IF NOT EXISTS flights (
    flight_id TEXT PRIMARY KEY, analysis_dir TEXT, first_capture TEXT, last_capture TEXT,
    irradiance_w_m2 REAL, imported_at TEXT);
CREATE TABLE IF NOT EXISTS module_states (
    flight_id TEXT, module_id TEXT, string_id TEXT, jb_id TEXT, inverter_id TEXT,
    verdict TEXT, verdict_reason TEXT, relative_temp REAL, max_delta_temp REAL, wide_delta REAL,
    observations INTEGER, flagged_votes INTEGER, anomaly_type TEXT,
    PRIMARY KEY (flight_id, module_id));
CREATE TABLE IF NOT EXISTS diagnoses (
    flight_id TEXT, module_id TEXT, source TEXT, payload TEXT, created_at TEXT,
    PRIMARY KEY (flight_id, module_id));
CREATE TABLE IF NOT EXISTS work_orders (
    order_id TEXT PRIMARY KEY, flight_id TEXT, inverter_id TEXT, jb_id TEXT, string_id TEXT,
    action_kind TEXT, priority INTEGER, safety INTEGER, loss_w REAL, route_order INTEGER,
    modules TEXT, title TEXT, instructions TEXT, equipment TEXT, status TEXT,
    approved_by TEXT, approved_at TEXT, created_at TEXT, carried_from TEXT);
CREATE TABLE IF NOT EXISTS inspection_results (
    order_id TEXT, module_id TEXT, cause TEXT, action TEXT, inspector TEXT, inspected_on TEXT,
    location_ok INTEGER, memo TEXT, updated_at TEXT, PRIMARY KEY (order_id, module_id));
CREATE TABLE IF NOT EXISTS order_events (
    order_id TEXT, at TEXT, status TEXT, actor TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS llm_log (
    sent_at TEXT, flight_id TEXT, anon_id TEXT, module_id TEXT, model TEXT, ok INTEGER, detail TEXT);
"""


def now():
    return datetime.now().isoformat(timespec='seconds')


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def rows(db, sql, *args):
    return [dict(r) for r in db.execute(sql, args)]


def import_flight(db, flight_id, analysis_dir, verdicts, types=None, first=None, last=None, irradiance=None):
    """Replace one flight's module states (verdicts = module_verdict.judge output)."""
    types = types or {}
    with db:
        db.execute('INSERT OR REPLACE INTO flights VALUES (?,?,?,?,?,?)',
                   (flight_id, str(analysis_dir), first, last, irradiance, now()))
        db.execute('DELETE FROM module_states WHERE flight_id = ?', (flight_id,))
        db.executemany('INSERT INTO module_states VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', [
            (flight_id, r['drawing_module_id'], r.get('string_id'), r.get('jb_id'), r.get('inverter_id'),
             r.get('verdict'), r.get('verdict_reason'), _num(r.get('relative_temp')), _num(r.get('max_delta_temp')),
             _num(r.get('wide_delta')), int(r.get('observations') or 0), int(r.get('flagged_votes') or 0),
             types.get(r['drawing_module_id'])) for r in verdicts])


def previous_flight(db, flight_id):
    found = db.execute('SELECT flight_id FROM flights WHERE flight_id < ? ORDER BY flight_id DESC LIMIT 1', (flight_id,)).fetchone()
    return found[0] if found else None


def compare(db, flight_id):
    """{module_id: 'new' | 'persisting' | 'resolved'} against the previous flight (6.4)."""
    before = previous_flight(db, flight_id)
    flagged = lambda f: {r['module_id'] for r in rows(db, "SELECT module_id FROM module_states WHERE flight_id = ? AND verdict IN ('inspect', 'recheck')", f)}
    seen = lambda f: {r['module_id'] for r in rows(db, 'SELECT module_id FROM module_states WHERE flight_id = ?', f)}
    now_flagged = flagged(flight_id)
    if before is None:
        return {m: 'new' for m in now_flagged}
    old = flagged(before)
    out = {m: ('persisting' if m in old else 'new') for m in now_flagged}
    out.update({m: 'resolved' for m in old - now_flagged if m in seen(flight_id)})
    return out


def save_diagnoses(db, flight_id, diagnoses):
    with db:
        db.execute('DELETE FROM diagnoses WHERE flight_id = ?', (flight_id,))
        db.executemany('INSERT INTO diagnoses VALUES (?,?,?,?,?)', [
            (flight_id, d['module_id'], d['source'], json.dumps(d, ensure_ascii=False), now()) for d in diagnoses])


def save_orders(db, flight_id, orders):
    """Replace this flight's draft orders; issued ones and their results are kept."""
    with db:
        kept = {r['order_id'] for r in rows(db, "SELECT order_id FROM work_orders WHERE flight_id = ? AND status != '초안'", flight_id)}
        db.execute("DELETE FROM work_orders WHERE flight_id = ? AND status = '초안'", (flight_id,))
        for o in orders:
            if o['order_id'] in kept:
                continue
            db.execute('INSERT INTO work_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                o['order_id'], flight_id, o['inverter_id'], o['jb_id'], o.get('string_id'), o['action_kind'],
                o['priority'], int(o['safety']), o['loss_w'], o['route_order'], json.dumps(o['modules'], ensure_ascii=False),
                o['title'], o['instructions'], json.dumps(o['equipment'], ensure_ascii=False), '초안',
                None, None, now(), o.get('carried_from')))


def open_orders_before(db, flight_id):
    """Orders from earlier flights that are not closed: they carry over to this flight's list (4.7)."""
    return rows(db, "SELECT * FROM work_orders WHERE flight_id < ? AND status NOT IN ('종결', '초안')", flight_id)


def set_status(db, order_id, status, actor='', note=''):
    if status not in ORDER_STATUS:
        raise ValueError(f'unknown status {status}')
    with db:
        found = db.execute('SELECT status FROM work_orders WHERE order_id = ?', (order_id,)).fetchone()
        if not found:
            raise KeyError(order_id)
        extra = (', approved_by = ?, approved_at = ?', (actor, now())) if status == '발행' and found[0] == '초안' else ('', ())
        db.execute(f'UPDATE work_orders SET status = ?{extra[0]} WHERE order_id = ?', (status, *extra[1], order_id))
        db.execute('INSERT INTO order_events VALUES (?,?,?,?,?)', (order_id, now(), status, actor, note))


def save_result(db, order_id, module_id, **fields):
    allowed = ('cause', 'action', 'inspector', 'inspected_on', 'location_ok', 'memo')
    current = db.execute('SELECT * FROM inspection_results WHERE order_id = ? AND module_id = ?', (order_id, module_id)).fetchone()
    value = {k: (current[k] if current else None) for k in allowed}
    value.update({k: v for k, v in fields.items() if k in allowed})
    with db:
        db.execute('INSERT OR REPLACE INTO inspection_results VALUES (?,?,?,?,?,?,?,?,?)',
                   (order_id, module_id, *[value[k] for k in allowed], now()))
    # A result on every module of an issued order moves it to inspected; "이상 없음" everywhere closes it.
    order = db.execute('SELECT status, modules FROM work_orders WHERE order_id = ?', (order_id,)).fetchone()
    if order and order['status'] == '발행':
        modules = json.loads(order['modules'])
        results = rows(db, 'SELECT module_id, cause FROM inspection_results WHERE order_id = ?', order_id)
        done = {r['module_id']: r['cause'] for r in results if r['cause']}
        if all(m in done for m in modules):
            clean = all(done[m] == '이상 없음' for m in modules)
            set_status(db, order_id, '종결' if clean else '점검 완료', fields.get('inspector', ''), '현장 결과 입력')


def add_manual(db, flight_id, module_id, actor=''):
    """An operator adds a module the rules did not send to the field: it joins its junction box's manual order."""
    state = db.execute('SELECT * FROM module_states WHERE flight_id = ? AND module_id = ?', (flight_id, module_id)).fetchone()
    if not state:
        raise KeyError(module_id)
    order_id = f"{flight_id}-{state['jb_id']}-manual"
    found = db.execute('SELECT modules, status FROM work_orders WHERE order_id = ?', (order_id,)).fetchone()
    with db:
        if found:
            modules = json.loads(found['modules'])
            if module_id not in modules:
                modules.append(module_id)
            db.execute('UPDATE work_orders SET modules = ?, title = ? WHERE order_id = ?',
                       (json.dumps(modules, ensure_ascii=False), f"[보통] {state['inverter_id']} › {state['jb_id']} 운영자 추가 확인 {len(modules)}장", order_id))
        else:
            last = db.execute('SELECT COALESCE(MAX(route_order), 0) FROM work_orders WHERE flight_id = ?', (flight_id,)).fetchone()[0]
            db.execute('INSERT INTO work_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                order_id, flight_id, state['inverter_id'], state['jb_id'], state['string_id'], 'manual', 999, 0, 0.0, last + 1,
                json.dumps([module_id]), f"[보통] {state['inverter_id']} › {state['jb_id']} 운영자 추가 확인 1장",
                f"{state['inverter_id']} › {state['jb_id']} · 운영자가 직접 추가한 모듈", json.dumps(['열화상 카메라'], ensure_ascii=False),
                '초안', None, None, now(), None))
        db.execute('INSERT INTO order_events VALUES (?,?,?,?,?)', (order_id, now(), 'manual-add', actor, module_id))
    return order_id


def remove_module(db, order_id, module_id, actor=''):
    """Take a module out of a draft order (the operator disagrees with the rules)."""
    found = db.execute('SELECT modules, status FROM work_orders WHERE order_id = ?', (order_id,)).fetchone()
    if not found or found['status'] != '초안':
        raise ValueError('only draft orders can be edited')
    modules = [m for m in json.loads(found['modules']) if m != module_id]
    with db:
        if modules:
            db.execute('UPDATE work_orders SET modules = ? WHERE order_id = ?', (json.dumps(modules, ensure_ascii=False), order_id))
        else:
            db.execute('DELETE FROM work_orders WHERE order_id = ?', (order_id,))
        db.execute('INSERT INTO order_events VALUES (?,?,?,?,?)', (order_id, now(), 'module-removed', actor, module_id))


def log_llm(db, flight_id, anon_id, module_id, model, ok, detail=''):
    with db:
        db.execute('INSERT INTO llm_log VALUES (?,?,?,?,?,?,?)', (now(), flight_id, anon_id, module_id, model, int(ok), detail))


def snapshot(db, flight_id):
    """Everything the console needs for one flight."""
    orders = rows(db, 'SELECT * FROM work_orders WHERE flight_id = ? ORDER BY route_order, priority', flight_id)
    carried = open_orders_before(db, flight_id)
    for o in orders + carried:
        o['modules'] = json.loads(o['modules'])
        o['equipment'] = json.loads(o['equipment'] or '[]')
    ids = [o['order_id'] for o in orders + carried]
    results = rows(db, f"SELECT * FROM inspection_results WHERE order_id IN ({','.join('?' * len(ids))})", *ids) if ids else []
    return dict(flight_id=flight_id, orders=orders, carried_over=carried, results=results,
                comparison=compare(db, flight_id), statuses=ORDER_STATUS)


def _num(value):
    try:
        out = float(value)
        return out if out == out else None
    except (TypeError, ValueError):
        return None
