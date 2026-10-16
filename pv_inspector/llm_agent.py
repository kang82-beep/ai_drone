"""Cause-estimation agent: a multimodal LLM reviews the rule diagnosis (과제_기획서 4.4).

The rules have already named cause candidates with evidence. The model sees the same
evidence plus the thermal and visible crops, judges the visible appearance (soiling,
grass, shadow, broken glass, discolouration) and may re-rank the causes. It may only
pick causes from the knowledge base and cite evidence ids it was given; whatever it
says, the rule warnings stay in the list. Anything it returns that breaks those rules
is dropped and the rule result is kept.

Transfer conditions (4.4): only module crops are sent, re-encoded so no EXIF/XMP
position survives, under a random id; the id map and a send log stay in the local
history database. Without an API key or with sending switched off, nothing is sent.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path

import cv2
import numpy as np

APPEARANCE = ['오염·새똥', '풀·식생', '그림자', '유리 파손', '변색', '이상 없음', '판단 불가']
CONFIDENCE = ['높음', '중간', '낮음']
URGENCY = ['최우선', '우선', '보통', '낮음']
KEEP_KINDS = ('electrical', 'operation')   # field checks the model may not downgrade
FIELD_WORK = ('operation', 'electrical', 'field_check', 'clean', 'weed', 'manual')

SYSTEM = """당신은 태양광 발전소 열화상 점검의 원인 추정 보조자다.
규칙 엔진이 이미 이상 후보 모듈의 원인 후보와 근거를 냈다. 당신은 같은 증거와 열화상·가시광 크롭을 보고
1) 가시광 외관을 판단하고 2) 원인 후보를 다시 정렬하며 3) 권장 조치와 긴급도를 낸다.
지켜야 할 것:
- 원인은 반드시 아래 원인 목록의 문구 그대로 고른다. 맞는 것이 없으면 "원인 판별 어려움".
- 근거는 제공된 증거 번호(E1, E2…)만 인용한다. 증거에 없는 사실을 쓰지 않는다.
- 가시광 외관만으로 셀 균열 같은 내부 결함을 확정하지 않는다.
- 오염이나 그림자가 보여도 규칙의 경고를 지우라고 하지 않는다. 조치만 바꾼다.
- 점검 대상인지는 이미 정해졌다. 원인 설명만 한다.
JSON 하나로만 답한다:
{"appearance": {"label": <외관 목록 중 하나>, "confidence": <높음|중간|낮음>, "note": <한 문장>},
 "causes": [{"cause": <원인 목록 문구>, "confidence": <높음|중간|낮음>, "evidence": ["E1", ...], "reason": <한 문장>}],
 "action": <권장 조치 한 문장>, "urgency": <최우선|우선|보통|낮음>, "needs_review": <true|false>}"""


KEY_FILE = Path.home() / '.ai_drone' / 'openai_key.txt'   # outside the project, never committed


def api_key():
    """OPENAI_API_KEY from the environment, else the key file in the user's home folder."""
    if os.environ.get('OPENAI_API_KEY'):
        return os.environ['OPENAI_API_KEY'].strip()
    return KEY_FILE.read_text(encoding='utf-8').strip() if KEY_FILE.is_file() else None


def anon_id(module_id, salt):
    return 'M' + hashlib.sha256((salt + module_id).encode()).hexdigest()[:10]


def load_salt(path):
    path = Path(path)
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(16), encoding='utf-8')
    return path.read_text(encoding='utf-8').strip()


def clean_jpeg(path, max_side=384):
    """Pixels only: decoding and re-encoding drops EXIF/XMP, including the GPS tags."""
    # cv2.imread cannot open non-ASCII Windows paths (the crops sit under sorted/정상/주의): read bytes first.
    try:
        image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    except (OSError, ValueError):
        image = None
    if image is None:
        return None
    scale = max_side / max(image.shape[:2])
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ok, data = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(data.tobytes()).decode() if ok else None


def evidence_items(diagnosis):
    """Numbered evidence lines (no IDs, coordinates or plant names)."""
    items, seen = [], set()
    for c in diagnosis['candidates']:
        for e in c['evidence']:
            text = e['text']
            for word, name in ((diagnosis.get('string_id'), '해당 스트링'), (diagnosis.get('jb_id'), '해당 접속반'),
                               (diagnosis.get('inverter_id'), '해당 인버터')):
                if word:
                    text = text.replace(str(word), name)  # equipment addresses stay in-house
            if text not in seen:
                seen.add(text)
                items.append(text)
    return [(f'E{i + 1}', t) for i, t in enumerate(items)]


def build_messages(diagnosis, kb, images):
    evidence = evidence_items(diagnosis)
    causes = sorted({r['cause'] for r in kb['rules']})
    rule_view = [{'cause': c['cause'], 'confidence': c['confidence'], 'action': c['action'], 'urgency': c['urgency']}
                 for c in diagnosis['candidates']]
    text = (f"원인 목록: {json.dumps(causes, ensure_ascii=False)}\n외관 목록: {json.dumps(APPEARANCE, ensure_ascii=False)}\n"
            f"규칙 판정: {diagnosis['verdict']} (촬영 {diagnosis['views']}회 중 {diagnosis['votes']}회 이상)\n"
            f"열 패턴: {diagnosis['anomaly_type']}\n규칙 원인 후보: {json.dumps(rule_view, ensure_ascii=False)}\n증거:\n"
            + '\n'.join(f'{k}: {t}' for k, t in evidence)
            + f"\n첨부 영상: {', '.join(name for name, _ in images) or '없음'}")
    content = [{'type': 'text', 'text': text}]
    for name, data in images:
        content.append({'type': 'text', 'text': name})
        content.append({'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{data}'}})
    return [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': content}], {k for k, _ in evidence}


def validate(answer, kb, evidence_ids):
    """The reply if it keeps every rule, else None."""
    causes = {r['cause'] for r in kb['rules']}
    try:
        a = answer['appearance']
        if a['label'] not in APPEARANCE or a['confidence'] not in CONFIDENCE:
            return None
        picked = []
        for c in answer['causes'][:4]:
            if c['cause'] not in causes or c['confidence'] not in CONFIDENCE:
                return None
            if not set(c.get('evidence') or []) <= evidence_ids:
                return None
            picked.append(dict(cause=c['cause'], confidence=c['confidence'], evidence=list(c.get('evidence') or []),
                               reason=str(c.get('reason', ''))[:300]))
        if not picked or answer['urgency'] not in URGENCY:
            return None
        return dict(appearance=dict(label=a['label'], confidence=a['confidence'], note=str(a.get('note', ''))[:300]),
                    causes=picked, action=str(answer['action'])[:300], urgency=answer['urgency'],
                    needs_review=bool(answer.get('needs_review')))
    except (KeyError, TypeError, AttributeError):
        return None


def merge(diagnosis, review, kb, model):
    """Model order first, every rule candidate kept; the stricter urgency wins."""
    by_cause = {r['cause']: r for r in kb['rules']}
    rules = {c['cause']: c for c in diagnosis['candidates']}
    merged = []
    for c in review['causes']:
        base = rules.get(c['cause']) or dict(rule=by_cause[c['cause']]['rule'], cause=c['cause'],
                                             action=by_cause[c['cause']]['action'], urgency=by_cause[c['cause']]['urgency'],
                                             kind=by_cause[c['cause']]['kind'], safety=bool(by_cause[c['cause']].get('safety')),
                                             evidence=[])
        merged.append({**base, 'confidence': c['confidence'], 'llm_reason': c['reason'], 'llm_evidence': c['evidence']})
    merged += [c for cause, c in rules.items() if cause not in {m['cause'] for m in merged}]
    out = dict(diagnosis)
    out['rule_kind'], out['rule_primary'] = diagnosis['kind'], diagnosis['primary']
    out['rule_rules'] = [c['rule'] for c in diagnosis['candidates']]
    out['candidates'] = merged
    out['primary'], out['kind'] = merged[0]['cause'], merged[0]['kind']
    # The model explains and re-ranks; it cannot take an electrical or operating check off the field plan.
    # Leaving the field happens only through the gated, audited downgrade (work_orders.ai_downgrade).
    if (diagnosis['kind'] in KEEP_KINDS and out['kind'] != diagnosis['kind']) or             (diagnosis['kind'] in FIELD_WORK and out['kind'] not in FIELD_WORK):
        out['kind'] = diagnosis['kind']
        out['field_kind_kept'] = f"규칙의 {diagnosis['primary']} 점검을 유지 (GPT 1순위: {out['primary']})"
    rank = {u: i for i, u in enumerate(URGENCY)}
    out['urgency'] = min([review['urgency'], diagnosis['urgency']], key=lambda u: rank[u])
    out['action'] = review['action']
    out['appearance'] = review['appearance']
    out['needs_review'] = review['needs_review'] or diagnosis['needs_review'] and merged[0]['confidence'] == '낮음'
    out['exclude'] = out['kind'] == 'exclude'
    out['safety'] = any(c['safety'] for c in merged)
    out['source'] = f'rule+llm:{model}'
    return out


class Agent:
    """Wraps the OpenAI client; `client` can be any object with chat.completions.create (tests pass a fake)."""

    def __init__(self, model, client=None, key=None):
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=key or api_key())
        self.client, self.model = client, model

    def review(self, diagnosis, kb, images):
        messages, ids = build_messages(diagnosis, kb, images)
        for _ in range(2):  # one retry when the reply breaks the format
            reply = self.client.chat.completions.create(model=self.model, messages=messages,
                                                        response_format={'type': 'json_object'})
            try:
                answer = validate(json.loads(reply.choices[0].message.content), kb, ids)
            except (json.JSONDecodeError, AttributeError, IndexError):
                answer = None
            if answer:
                return answer
        return None


def available(model, send_images):
    return bool(model and send_images and api_key())
