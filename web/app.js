// AeroSolar OPS console. Renders window.SITE and window.SITE_MAP (written by export_web_data.py); no build step, no network.
(() => {
const S = window.SITE, M = window.SITE_MAP;
const app = document.getElementById('app');
if (!S || !M) {
  app.innerHTML = '<p style="padding:24px">data 폴더에 내보낸 결과가 없습니다. 프로젝트 폴더에서 <code>python export_web_data.py</code>를 먼저 실행하세요.</p>';
  return;
}

const store = {
  get(key) { try { return localStorage.getItem('aerosolar.' + key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem('aerosolar.' + key, value); } catch { /* private mode */ } },
};
const state = {
  theme: store.get('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'),
  filter: 'all', query: '', module: null, obs: 0, zoom: 1, layer: 'final', lightbox: false,
  stage: store.get('stage') === '3d' ? '3d' : 'map',
  reviews: JSON.parse(store.get('reviews') || '{}'),
};

const ICONS = {
  radar: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 12l6-6"/>',
  map: '<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14"/>',
  flow: '<path d="M3 17l5-6 4 4 8-9"/>',
  task: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3h6v3H9zM9 13l2 2 4-4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/>',
  wind: '<path d="M3 9h11a3 3 0 10-3-3M3 14h15a3 3 0 11-3 3M3 19h6"/>',
  moon: '<path d="M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z"/>',
  cube: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3zM12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
  bot: '<rect x="5" y="8" width="14" height="11" rx="2"/><path d="M12 8V4M9 13v2M15 13v2M2 13v2M22 13v2"/>',
  temp: '<path d="M10 14V5a2 2 0 114 0v9a4 4 0 11-4 0z"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  left: '<path d="M15 5l-7 7 7 7"/>',
  right: '<path d="M9 5l7 7-7 7"/>',
  expand: '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
  scan: '<path d="M4 8V5a1 1 0 011-1h3M16 4h3a1 1 0 011 1v3M20 16v3a1 1 0 01-1 1h-3M8 20H5a1 1 0 01-1-1v-3"/><circle cx="12" cy="12" r="3"/>',
  list: '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
  shield: '<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z"/>',
  inbox: '<path d="M4 13l3-8h10l3 8v6H4v-6zM4 13h5l1 2h4l1-2h5"/>',
  pin: '<path d="M12 21s7-6.5 7-12a7 7 0 10-14 0c0 5.5 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
  download: '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
  print: '<path d="M7 9V4h10v5M7 17H5a1 1 0 01-1-1v-5a2 2 0 012-2h12a2 2 0 012 2v5a1 1 0 01-1 1h-2M7 14h10v6H7z"/>',
  trash: '<path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13"/>',
  layers: '<path d="M12 4l9 5-9 5-9-5 9-5zM3 14l9 5 9-5"/>',
};
const icon = name => `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const int = value => value == null ? '–' : Number(value).toLocaleString('ko-KR');
const num = (value, digits = 1) => value == null ? '–' : Number(value).toFixed(digits);
const signed = value => value == null ? '–' : (value > 0 ? '+' : '') + Number(value).toFixed(1);
const pct = (part, whole) => whole ? (100 * part / whole) : 0;
const time = iso => iso ? iso.slice(11, 19) : '–';
const frameNo = imageId => (imageId.match(/_(\d{4})_T$/) || [])[1] || imageId;

const FINAL = { abnormal: ['이상', 'crit'], attention: ['주의', 'warn'], normal: ['정상', 'ok'] };
// Module verdict from repeated views (pv_inspector/module_verdict.py).
const VERDICT = { inspect: ['점검 대상', 'crit'], recheck: ['재확인', 'warn'], normal: ['정상', 'ok'] };
const verdictChip = v => chip(VERDICT[v || 'inspect'][0], VERDICT[v || 'inspect'][1], true);
const MAP_STATE = [['미관측', ''], ['후보 없음', 'ok'], ['주의', 'warn'], ['이상', 'crit']];
// pv_inspector/anomaly_patterns.py TYPES; shade-like shapes are reported as shadow suspects to confirm.
const TYPE = { single_cell: '단일 셀 핫스팟', multi_cell: '다중 셀 핫스팟', diode: '다이오드 의심 (1/3 띠)', whole_module: '모듈 전체 발열',
  low_edge_band: '하단 띠 (낮은 쪽)', high_edge_band: '상단 띠 (높은 쪽)', linear_streak: '선형 띠', partial_shade: '부분 그늘',
  none: '뚜렷한 형상 없음', unreadable: '형상 판독 불가' };
const typeChip = type => type ? chip(TYPE[type] || type, ['single_cell', 'multi_cell', 'diode', 'whole_module'].includes(type) ? 'crit' : type === 'none' || type === 'unreadable' ? '' : 'info') : '';
const REASON = { hotspot: '국부 고온', delta_temperature: '모듈 내 온도차', neighbor_delta: '주변 대비 고온', hierarchical: '분류 모델' };
const NAV = [['overview', '현황', 'map'], ['pipeline', '파이프라인', 'flow'], ['orders', '작업지시', 'task']];
const CAUSES = ['오염에 의한 부분 음영', '셀 균열·셀 불량', '바이패스 다이오드 고장', '커넥터 불량·모듈 개방', '스트링 단선·퓨즈 용단', '식생·구조물 음영', '태양 반사', '이상 없음', '원인 판별 어려움'];
const ACTIONS = ['조치 없음', '청소', '제초', '모듈 교체 접수', '커넥터·퓨즈 교체', '재촬영 필요'];
// 과제_기획서.md 2절의 구성요소별 현재 상태.
const COMPONENTS = [
  ['촬영 조건 확인 (일사, 속도)', '규칙', 'part', '일사 기준만 구현'], ['방사온도 추출', 'DJI SDK', 'done', ''],
  ['모듈 검출·분할', 'Mask R-CNN', 'done', '정확도 미측정'], ['열화상–가시광 정합', '고정 변환 (M4T 짐벌)', 'part', S.rgb_alignment ? `오차 중앙값 ${num(S.rgb_alignment.offset_from_fixed_px_median, 0)}px · 프레임별 미세 조정 없음` : ''],
  ['설비 주소 연결', 'RTK 투영 + 카메라 보정 + 비행 줄 연결', 'part', S.registration.lines ? `비행 줄 ${S.registration.lines.resolved}/${S.registration.lines.total} 결정 · 측량 검증 전` : '한 칸 어긋남 미해결'], ['다중 촬영 통합', '규칙', 'done', '다수결 판정, 가장자리 관측 제외'],
  ['주변 대비 온도차', '규칙', 'done', ''], ['접속반·인버터 단위 비교', '규칙', 'part', '반경 6m 이웃·스트링 비교, 인버터 단위는 전체 분석 후'],
  ['이상 탐지', '규칙 + EfficientNet-B3', 'done', '표시 영상 기반'], ['이상 유형 분류', '형상 규칙 (온도 배열)', 'part', '1차 규칙 · 현장 검증 전'],
  ['원인 추정', '규칙 + GPT 보강', 'part', (S.orders_summary?.llm || 'off') === 'off' ? '기준표 규칙으로 동작 · GPT 꺼짐' : `GPT ${S.orders_summary.llm} · ${S.orders_summary.llm_reviewed}건 보강`],
  ['손실·우선순위 산정', '규칙', 'part', '정격 기준 추정 · 안전 → 손실 → 반복 순'],
  ['작업지시 생성', '규칙 (에이전트 문구는 이후)', 'part', '접속반 × 작업 종류로 묶고 방문 순서 산정'], ['점검 결과 환류', '머신러닝 운영', 'part', '결과 입력·오경보율·원인 일치율'],
];
const KNOWLEDGE = [
  ['셀 고온 + 같은 위치에 새똥·오염', '오염에 의한 부분 음영', '청소 후 재촬영'], ['셀 고온 + 가시광 정상', '셀 균열, 셀 불량, 납땜 불량', '현장 점검, 필요 시 I-V 측정'],
  ['모듈 1/3 띠 고온', '바이패스 다이오드 동작 또는 고장', '음영 확인 후 정션박스 점검'], ['모듈 전체 균일 고온', '모듈 개방, 커넥터 불량', '커넥터·개방전압 확인'],
  ['스트링 전체 고온', '스트링 단선, 퓨즈 용단', '접속반 퓨즈·전류 측정'], ['프레임마다 위치가 바뀌는 고온', '태양 반사', '이상에서 제외'],
  ['어느 것에도 맞지 않음', '원인 판별 어려움', '추가 촬영 또는 현장 확인'],
];

const R = S.registration, F = S.flight;
const candidateById = new Map(S.candidates.map(c => [c.id, c]));
const indexById = new Map(M.ids.map((id, i) => [id, i]));
const address = index => { const [string, jb, inverter] = M.strings[M.string[index]]; return { id: M.ids[index], string, jb, inverter, state: Number(M.state[index]) }; };
const chunksDone = S.chunks.filter(c => c.status === 'done').length;
const abnormalModules = S.candidates.filter(c => c.final === 'abnormal').length;
const byVerdict = v => S.candidates.filter(c => (c.verdict || 'inspect') === v);
const inspectCount = byVerdict('inspect').length, recheckCount = byVerdict('recheck').length;
const scopeNote = `이상 후보와 주소 연결은 도면 정합을 마친 ${int(R.frames)}장 기준입니다 (분석 완료 ${int(F.analysed)}장).`;
const chip = (text, tone = '', dot = false) => `<span class="chip ${tone}">${dot ? '<i class="dot"></i>' : ''}${esc(text)}</span>`;
const finalChip = final => chip(FINAL[final][0], FINAL[final][1], true);
const note = text => `<p class="note">${icon('info')}<span>${text}</span></p>`;
const empty = (name, title, text) => `<div class="empty">${icon(name)}<b>${title}</b><span>${text}</span></div>`;
// ---------- Work orders: live from serve_console.py (history DB) or, opened as a file, kept in this browser ----------
const DIAG = new Map((S.diagnoses || []).map(d => [d.id, d]));
const KB = S.kb || { causes: [], kinds: {}, rules: [], version: '' };
const WO_STATUS = ['초안', '발행', '점검 완료', '조치 완료', '종결'];
const STATUS_TONE = { 초안: '', 발행: 'warn', '점검 완료': 'info', '조치 완료': 'ok', 종결: 'ok' };
const FIELD = new Set(['operation', 'electrical', 'field_check', 'clean', 'weed', 'manual']);
const URGENCY_TONE = { 최우선: 'crit', 우선: 'warn', 보통: 'info', 낮음: '' };
const CONF_TONE = { 높음: 'ok', 중간: 'info', 낮음: 'warn' };
const live = { on: false, snapshot: null };
const local = Object.assign({ status: {}, results: {}, manual: {}, removed: {} }, JSON.parse(store.get('workorders') || '{}'));
const saveLocal = () => store.set('workorders', JSON.stringify(local));
const resultKey = (order, module) => `${order}|${module}`;
let orderIndex = null;

function workOrders() {
  if (live.on && live.snapshot) return [...live.snapshot.orders, ...live.snapshot.carried_over.map(o => ({ ...o, carried: true }))];
  const base = (S.work_orders || []).map(o => ({ ...o, status: local.status[o.order_id] || '초안', modules: o.modules.filter(m => !local.removed[resultKey(o.order_id, m)]) }));
  const manual = {};
  Object.entries(local.manual).forEach(([module, info]) => {
    const id = `${S.flight_id}-${info.jb}-manual`;
    (manual[id] ||= { order_id: id, inverter_id: info.inverter, jb_id: info.jb, action_kind: 'manual', priority: 999, route_order: 999, loss_w: 0, safety: 0,
      title: '', instructions: `${info.inverter} › ${info.jb} · 운영자가 직접 추가한 모듈`, equipment: ['열화상 카메라'], modules: [], status: local.status[id] || '초안' }).modules.push(module);
  });
  Object.values(manual).forEach(o => { o.title = `[보통] ${o.inverter_id} › ${o.jb_id} 운영자 추가 확인 ${o.modules.length}장`; });
  return [...base.filter(o => o.modules.length), ...Object.values(manual)];
}
const results = () => live.on && live.snapshot ? Object.fromEntries(live.snapshot.results.map(r => [resultKey(r.order_id, r.module_id), r])) : local.results;
const orderMap = () => orderIndex ||= new Map(workOrders().flatMap(o => o.modules.map(m => [m, o])));
const orderOf = module => orderMap().get(module);
const fieldOrder = module => { const o = orderOf(module); return o && FIELD.has(o.action_kind) ? o : null; };
const openOrders = () => workOrders().filter(o => FIELD.has(o.action_kind) && o.status !== '종결').length;

async function connect() {
  if (!location.protocol.startsWith('http')) return;
  try {
    const health = await (await fetch('/api/health')).json();
    if (!health.ok) return;
    live.snapshot = await (await fetch('/api/snapshot')).json();
    live.on = true;
  } catch { /* opened without serve_console.py */ }
}
async function act(path, body, localChange) {
  try {
    if (live.on) {
      const response = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || response.statusText);
      live.snapshot = data;
    } else { localChange(); saveLocal(); }
  } catch (error) { toast(`저장하지 못했습니다: ${error.message}`); }
  orderIndex = null;
  render();
}
function setStatus(order, status) {
  const actor = status === '발행' ? prompt('발행(승인)하는 사람 이름', store.get('actor') || '') : (store.get('actor') || '');
  if (actor === null) return render();
  if (status === '발행') store.set('actor', actor);
  return act(`/api/orders/${encodeURIComponent(order)}/status`, { status, actor }, () => { local.status[order] = status; });
}
function saveResult(order, module, field, value) {
  const fields = { [field]: value };
  if (field === 'cause' && value && !results()[resultKey(order, module)]?.inspected_on) fields.inspected_on = new Date().toISOString().slice(0, 10);
  return act('/api/results', { order_id: order, module_id: module, ...fields }, () => {
    const key = resultKey(order, module);
    local.results[key] = { ...(local.results[key] || {}), order_id: order, module_id: module, ...fields };
    const o = workOrders().find(x => x.order_id === order);
    if (o && o.status === '발행' && o.modules.every(m => local.results[resultKey(order, m)]?.cause)) {
      local.status[order] = o.modules.every(m => local.results[resultKey(order, m)].cause === '이상 없음') ? '종결' : '점검 완료';
    }
  });
}
function addManual(module) {
  const c = candidateById.get(module) || address(indexById.get(module));
  return act('/api/manual', { module_id: module, actor: store.get('actor') || '' }, () => { local.manual[module] = { jb: c.jb, inverter: c.inverter }; });
}
function removeModule(order, module) {
  return act(`/api/orders/${encodeURIComponent(order)}/remove`, { module_id: module }, () => {
    if (order.endsWith('-manual')) delete local.manual[module]; else local.removed[resultKey(order, module)] = true;
  });
}
const diagChip = id => { const d = DIAG.get(id); return !d ? chip('결과 없음') : d.source.startsWith('rule+llm') ? chip('GPT 보강', 'info') : chip('규칙 판단'); };
function diagnosisView(id) {
  const d = DIAG.get(id);
  if (!d) return note('이 모듈의 원인 추정 결과가 없습니다. python run_flight.py 로 원인 추정을 만든 뒤 다시 여세요.');
  const head = `<div class="row wrap">${chip(d.urgency, URGENCY_TONE[d.urgency] || '', true)}${d.ai_downgraded ? chip('AI 하향', 'info') : ''}${d.ai_audit ? chip('AI 하향 검증 표본', 'warn') : ''}${d.exclude ? chip('이상에서 제외 후보') : ''}${d.needs_review ? chip('사람 검토 필요', 'warn') : ''}${d.safety ? chip('안전 위험', 'crit') : ''}${d.loss_w ? chip(`예상 손실 ${num(d.loss_w, 0)} W`) : ''}</div>
    <p style="margin:8px 0"><b>${esc(d.primary)}</b> → ${esc(d.action)}</p>`;
  const look = (d.appearance ? `<p class="sub">가시광 외관: <b>${esc(d.appearance.label)}</b> (${esc(d.appearance.confidence)}) ${esc(d.appearance.note || '')}</p>` : '')
    + (d.ai_downgraded ? note(`AI 하향: ${esc(d.ai_downgraded)}. 다음 촬영에서 다시 걸리면 현장 작업지시로 올라갑니다.`) : '')
    + (d.ai_audit ? note(`검증 표본: ${esc(d.ai_audit)}. 현장 결과로 AI 하향이 맞았는지 잽니다.`) : '')
    + (d.field_kind_kept ? note(`${esc(d.field_kind_kept)}. 전기 점검은 영상만으로 빼지 않습니다.`) : '');
  const list = d.candidates.map((c, i) => `<div class="reason">${icon(i ? 'layers' : 'bot')}<span><b>${i + 1}. ${esc(c.cause)}</b> ${chip(c.confidence, CONF_TONE[c.confidence] || '')}<br>${esc(c.action)}${c.llm_reason ? `<br><span class="sub">GPT: ${esc(c.llm_reason)}</span>` : ''}${(c.evidence || []).map(e => `<br><span class="sub">· ${esc(e.text)}</span>`).join('')}</span></div>`).join('');
  return head + look + list + note('원인은 후보와 근거입니다. 점검 대상인지는 판정 규칙이 정하고, 이 결과는 현장 점검을 시작하기 위한 설명입니다.');
}
const saveReviews = () => store.set('reviews', JSON.stringify(state.reviews));
const SHADOW_REVIEW = { yes: ['그림자 확인됨', 'ok'], no: ['그림자 아님', 'crit'] };

function route() {
  const [path, query = ''] = location.hash.replace(/^#\/?/, '').split('?');
  return { page: NAV.some(n => n[0] === path) ? path : 'overview', params: new URLSearchParams(query) };
}

// ---------- Shell ----------
function shell(page, body) {
  const condition = F.irradiance_w_m2 == null ? chip('촬영 조건 미확인', 'warn', true)
    : F.irradiance_w_m2 >= 600 ? chip('점검 적합 조건', 'ok', true) : chip('일사 부족', 'warn', true);
  return `
<header class="top">
  <a class="brand" href="#/overview">${icon('radar')}<span>AeroSolar <b>OPS</b></span></a>
  <span class="site">${esc(S.site.name)}<small>${int(S.site.modules)} 모듈 · 촬영 ${esc((F.first || '').slice(0, 10))}</small></span>
  <nav class="tabs">${NAV.map(([id, label, ic]) => `<a href="#/${id}" class="${id === page ? 'on' : ''}">${icon(ic)}<span>${label}</span>${id === 'orders' && openOrders() ? `<em>${openOrders()}</em>` : ''}</a>`).join('')}</nav>
  <div class="tools">
    <div class="cond"><span>${icon('sun')}${F.irradiance_w_m2 == null ? '일사 미기록' : int(F.irradiance_w_m2) + ' W/m²'}</span><i></i>
      <span>${icon('wind')}${F.wind_m_s == null ? '풍속 미기록' : num(F.wind_m_s) + ' m/s'}</span><i></i>${condition}</div>
    <a class="btn" href="viewer/Shinan3_Viewer.html" target="_blank" rel="noopener" title="전기실·케이블까지 걸어 다니며 보는 상세 3D">${icon('cube')}상세 3D</a>
    <button class="btn icon" data-act="theme" title="밝은 화면 / 어두운 화면" aria-label="화면 테마 전환">${icon(state.theme === 'dark' ? 'sun' : 'moon')}</button>
  </div>
</header>
<main class="${page}">${body}</main>`;
}

// The five stages of 과제_기획서.md double as the headline numbers.
function stageStrip() {
  const running = chunksDone < S.chunks.length;
  const steps = [
    ['촬영·수집', `${int(F.thermal_images)}쌍`, F.irradiance_w_m2 == null ? '일사 미기록' : `${int(F.irradiance_w_m2)} W/m²`, 'part', '#/pipeline'],
    ['자동 분석', `${num(pct(F.analysed, F.thermal_images), 0)}%`, `${int(F.analysed)} / ${int(F.thermal_images)}장${running ? ' · 실행 중' : ''}`, running ? 'run' : 'done', '#/pipeline'],
    ['이상 탐지', `점검 ${inspectCount}건`, `재확인 ${recheckCount} · 그림자 의심 ${S.candidates.filter(c => c.shadow).length}`, 'done', '#/overview'],
    ['AI 원인 추정', DIAG.size ? `${int(DIAG.size)}건` : '결과 없음', (S.orders_summary?.llm || 'off') === 'off' ? '규칙 판단 · GPT 꺼짐' : `GPT 보강 ${int(S.orders_summary.llm_reviewed)}건`, DIAG.size ? 'part' : 'none', '#/orders'],
    ['점검·환류', `${openOrders()}건`, '진행 중인 현장 작업지시', openOrders() ? 'part' : 'none', '#/orders'],
  ];
  return `<nav class="strip" aria-label="점검 단계">${steps.map(([title, value, sub, tone, href], i) => `<a class="step ${tone}" href="${href}">
    <span class="n">${i + 1}</span><span class="body"><span class="label">${title}</span><b>${value}</b><small>${sub}</small></span></a>`).join('')}</nav>`;
}

// ---------- Overview: queue + 3D map + detail ----------
function matches(candidate) {
  const text = state.query.trim().toLowerCase();
  return (state.filter === 'all' || (candidate.verdict || 'inspect') === state.filter || (state.filter === 'picked' && fieldOrder(candidate.id))
      || (state.filter === 'shadow' && candidate.shadow))
    && (!text || [candidate.id, candidate.string, candidate.jb, candidate.inverter].some(v => v.toLowerCase().includes(text)));
}

function listItems() {
  const items = S.candidates.filter(matches);
  if (!items.length) return empty('search', '조건에 맞는 후보가 없습니다', '검색어나 구분을 바꿔 보세요.');
  return items.map(c => `<button class="item ${VERDICT[c.verdict || 'inspect'][1]} ${c.id === state.module ? 'sel' : ''}" data-act="module" data-id="${esc(c.id)}">
    <span class="between"><b class="mono">${esc(c.id)}</b><span class="delta">${signed(c.max_neighbor_delta)}℃</span></span>
    <span class="between sub"><span>${esc(c.jb)} · ${esc(c.string)}</span><span>${fieldOrder(c.id) ? `<span class="t-pri">작업지시 · </span>` : ''}후보 ${c.flagged_count}/${c.observation_count}회</span></span>
    <span class="row wrap tags">${typeChip(c.type)}${c.shadow ? (state.reviews[c.id] ? chip(SHADOW_REVIEW[state.reviews[c.id]][0], SHADOW_REVIEW[state.reviews[c.id]][1]) : chip('그림자 의심', 'warn')) : ''}${c.edge_only ? chip('가장자리만', 'warn') : ''}</span></button>`).join('');
}

function donut(parts, total, caption) {
  const radius = 42, length = 2 * Math.PI * radius;
  let offset = 0;
  const arcs = parts.map(([, value, color]) => {
    const arc = `<circle cx="56" cy="56" r="${radius}" fill="none" stroke="${color}" stroke-width="12" stroke-dasharray="${length * value / total} ${length}" stroke-dashoffset="${-offset}" transform="rotate(-90 56 56)"/>`;
    offset += length * value / total;
    return arc;
  }).join('');
  return `<div class="donut"><svg viewBox="0 0 112 112"><circle cx="56" cy="56" r="${radius}" fill="none" stroke="var(--inset)" stroke-width="12"/>${arcs}</svg>
    <div class="mid"><b>${int(total)}</b><span class="sub">${caption}</span></div></div>`;
}

function summaryPanel() {
  const reasons = Object.entries(R.reasons).sort((a, b) => b[1] - a[1]);
  const total = reasons.reduce((n, [, v]) => n + v, 0);
  const colors = { hierarchical: 'var(--primary)', neighbor_delta: 'var(--warn)', delta_temperature: 'var(--crit)', hotspot: '#8b5cf6' };
  const inverters = S.inverters.map(inv => ({ id: inv.id, modules: inv.jbs.reduce((n, jb) => n + jb.modules, 0), observed: inv.jbs.reduce((n, jb) => n + jb.observed, 0),
    flagged: inv.jbs.reduce((n, jb) => n + jb.flagged, 0), abnormal: inv.jbs.reduce((n, jb) => n + jb.abnormal, 0) }));
  return `<div class="pane-head"><h2>이번 비행 요약</h2><span class="sub">모듈을 고르면 상세가 열립니다</span></div>
  <div class="pane-body">
    <section><h3>인버터별 현황</h3><p class="sub">누르면 지도가 그 구역으로 이동합니다.</p>
      <div class="invs">${inverters.map(inv => `<button class="invrow" data-act="inverter" data-id="${esc(inv.id)}">
        <b class="mono">${esc(inv.id)}</b><span class="bar"><i style="width:${pct(inv.observed, inv.modules)}%;background:var(--ok)"></i></span>
        <span class="sub">${inv.observed ? `관측 ${num(pct(inv.observed, inv.modules), 0)}%` : '미관측'}</span>
        ${inv.flagged ? chip(`후보 ${inv.flagged}`, inv.abnormal ? 'crit' : 'warn') : '<span></span>'}</button>`).join('')}</div></section>
    <section><h3>스트링 비교</h3><p class="sub">같은 접속반의 다른 스트링보다 평균 2℃ 이상 높은 스트링입니다. 스트링 단선·퓨즈를 의심할 수 있지만 음영도 같은 모양으로 나타납니다.</p>
      ${(S.strings_flagged || []).length ? (S.strings_flagged || []).map(s => `<button class="invrow" data-act="string" data-id="${esc(s.string_id)}"><b class="mono">${esc(s.string_id)}</b><span class="sub">${esc(s.jb_id)}</span><span class="sub">모듈 ${int(s.modules_observed)}장</span>${chip(signed(s.string_delta) + '℃', 'warn')}</button>`).join('') : '<p class="sub">해당 스트링이 없습니다.</p>'}</section>
    <section><h3>형상 판정 (1차 규칙)</h3><p class="sub">후보 모듈을 가운데에서 찍힌 관측 기준으로 나눴습니다. 그림자 의심은 확인이 필요합니다.</p>
      <div class="dist">${Object.entries(S.pattern_types || {}).map(([key, value]) => `<div class="between"><span>${TYPE[key] || esc(key)}</span><b>${int(value)}</b></div>`).join('')}</div></section>
    <section><h3>판정 근거별 분포</h3>
      <div class="donut-row">${donut(reasons.map(([key, value]) => [key, value, colors[key] || 'var(--text-4)']), total, '근거')}
        <div class="dist">${reasons.map(([key, value]) => `<div class="between"><span class="row"><i class="lg" style="background:${colors[key] || 'var(--text-4)'}"></i>${REASON[key] || esc(key)}</span><b>${int(value)}</b></div>`).join('')}</div></div>
      ${note('고장 유형(핫스팟·다이오드·스트링 단선) 분류는 아직 없어, 정상·주의·이상 세 단계와 판정 근거만 나옵니다.')}</section>
    <section>${note(scopeNote + ' 회색(미관측) 구역은 정상이 아니라 아직 결과가 없는 구역입니다.')}</section>
  </div>`;
}

function shadowCallout(candidate, o) {
  const notes = [...new Set(candidate.observations.flatMap(item => item.final !== 'normal' ? item.cautions || [] : []))];
  if (!candidate.shadow && !candidate.edge_only) return '';
  const review = state.reviews[candidate.id];
  const title = candidate.shadow ? '그림자·음영에 의한 발열로 보입니다' : '영상 가장자리에서만 이상으로 찍혔습니다';
  return `<section class="callout warn"><b>${title}</b>
    <ul class="sub plain">${notes.map(n => `<li>${esc(n)}</li>`).join('')}${candidate.edge_only ? '<li>가운데에서 찍힌 같은 모듈은 정상이었습니다. 반사에 의한 오인식일 가능성이 큽니다.</li>' : ''}</ul>
    ${candidate.shadow ? `<div class="row wrap"><span class="label">확인 결과</span>
      <button class="btn ${review === 'yes' ? 'on' : ''}" data-act="review" data-id="yes">그림자 맞음</button>
      <button class="btn ${review === 'no' ? 'on' : ''}" data-act="review" data-id="no">그림자 아님</button>
      ${review ? '<button class="btn" data-act="review" data-id="">되돌리기</button>' : ''}</div>` : ''}</section>`;
}

function evidence(candidate, o) {
  const repeated = candidate.flagged_count === candidate.observation_count;
  return [
    ['temp', `열 패턴: ${o.reasons.length ? o.reasons.map(r => REASON[r]).join(', ') : '분류 모델 판정만'}`,
      `최고 ${num(o.max_temp)}℃, 모듈 내 온도차 ${num(o.delta_temp)}℃, 주변 대비 ${signed(o.neighbor_delta_mean)}℃ (최고점은 ${signed(o.neighbor_delta_max)}℃).`],
    ['camera', `반복 관측: ${candidate.observation_count}회 중 ${candidate.flagged_count}회`,
      candidate.observation_count < 2 ? '한 번만 촬영되어 반사 여부를 가릴 수 없습니다.' : repeated ? '촬영된 모든 프레임에서 걸렸습니다.' : '일부 프레임에서만 걸렸습니다. 태양 반사 가능성이 남아 있습니다.'],
    o.rgb_crop ? ['scan', '가시광 외관: 크롭 준비됨, 판독 전', '고정 변환으로 맞춘 같은 모듈의 가시광 크롭이 있습니다. 오염·풀·그림자 판독은 원인 추정 단계에서 합니다.']
      : ['scan', '가시광 외관: 확인 전', '이 관측은 가시광 크롭을 만들지 못했습니다.'],
    ['layers', `형상: ${TYPE[o.type] || '판정 전'}`, o.type === 'unreadable' ? '모듈 윤곽을 확실히 잡지 못해 형상을 판정하지 않았습니다.' : '온도 배열에서 고온·저온 영역의 모양으로 정한 1차 규칙 판정입니다.'],
    ['scan', `영상 위치: ${o.edge ? '가장자리' : '가운데 쪽'}`, o.radius == null ? '' : `영상 중심에서 ${num(100 * o.radius, 0)}% 거리. 가장자리일수록 비스듬히 찍혀 반사로 온도가 틀어질 수 있습니다.`],
    ['clock', '과거 이력: 없음', '첫 회차라 비교할 이전 결과가 없습니다.'],
  ].map(([ic, title, text]) => `<div class="reason">${icon(ic)}<span><b>${esc(title)}</b>${esc(text)}</span></div>`).join('');
}

function thermalView(o, zoom) {
  const [x1, y1, x2, y2] = o.bbox;
  return `<div class="view"><span class="tag"><i class="dot t-crit"></i>열화상</span><span class="tag r">최고 ${num(o.max_temp)}℃</span>
    <div class="pan" style="transform:scale(${zoom});transform-origin:${50 * (x1 + x2)}% ${50 * (y1 + y2)}%">
      ${o.thermal ? `<img src="${esc(o.thermal)}" alt="열화상 프레임 ${esc(frameNo(o.image_id))}">` : ''}
      <span class="box" style="left:${100 * x1}%;top:${100 * y1}%;width:${100 * (x2 - x1)}%;height:${100 * (y2 - y1)}%"></span></div></div>`;
}
function rgbView(o, zoom) {
  const [x1, y1, x2, y2] = o.rgb_bbox || [0, 0, 0, 0];
  return `<div class="view"><span class="tag"><i class="dot t-pri"></i>가시광</span>
    <div class="pan" style="${o.rgb_bbox ? `transform:scale(${zoom});transform-origin:${50 * (x1 + x2)}% ${50 * (y1 + y2)}%` : ''}">
      ${o.rgb ? `<img src="${esc(o.rgb)}" alt="가시광 프레임 ${esc(frameNo(o.image_id))}">` : ''}
      ${o.rgb_bbox ? `<span class="box" style="left:${100 * x1}%;top:${100 * y1}%;width:${100 * (x2 - x1)}%;height:${100 * (y2 - y1)}%"></span>` : ''}</div>
    <span class="cap">${o.rgb_bbox ? '고정 변환으로 정합' : '모듈 위치 정합 전'}</span></div>`;
}
const zoomSeg = () => `<div class="seg">${[1, 2, 4].map(z => `<button class="${state.zoom === z ? 'on' : ''}" data-act="zoom" data-id="${z}">${z}x</button>`).join('')}</div>`;

// Detailed 3D viewer (shinan3_viewer, built into web/viewer) at this module, sun set to its capture time.
const viewerLink = candidate => `viewer/Shinan3_Viewer.html?module=${encodeURIComponent(candidate.id)}&at=${encodeURIComponent(candidate.observations[0]?.time || '')}`;

function candidatePanel(candidate) {
  const o = candidate.observations[Math.min(state.obs, candidate.observations.length - 1)];
  const visible = S.candidates.filter(matches), position = visible.findIndex(c => c.id === candidate.id);
  const order = orderOf(candidate.id), inField = order && FIELD.has(order.action_kind);
  return `<div class="pane-head">
    <div><div class="row wrap"><h2 class="mono">${esc(candidate.id)}</h2>${verdictChip(candidate.verdict)}${typeChip(candidate.type)}${o.reasons.map(r => chip(REASON[r], r === 'hotspot' ? 'crit' : 'warn')).join('')}</div>
      <p class="sub">${esc(candidate.inverter)} › ${esc(candidate.jb)} › ${esc(candidate.string)}</p>
      ${candidate.verdict_reason ? `<p class="sub">판정: ${esc(candidate.verdict_reason)}${candidate.wide_delta != null ? `; 주변 ${int(candidate.wide_neighbours)}장 대비 ${signed(candidate.wide_delta)}℃` : ''}</p>` : ''}</div>
    <div class="row"><button class="btn icon" data-act="step" data-id="-1" title="이전 후보 (K)" aria-label="이전 후보" ${position <= 0 ? 'disabled' : ''}>${icon('left')}</button>
      <button class="btn icon" data-act="step" data-id="1" title="다음 후보 (J)" aria-label="다음 후보" ${position < 0 || position >= visible.length - 1 ? 'disabled' : ''}>${icon('right')}</button>
      <button class="btn icon" data-act="close" title="닫기 (Esc)" aria-label="상세 닫기">${icon('close')}</button></div></div>
  <div class="pane-body">
    ${shadowCallout(candidate, o)}
    <div class="row">
      ${order ? `<a class="btn ${inField ? 'on' : ''}" style="flex:1" href="#/orders?o=${encodeURIComponent(order.order_id)}">${icon(inField ? 'check' : 'clock')}${esc(KB.kinds[order.action_kind] || order.action_kind)} · ${esc(order.status)}</a>` : ''}
      ${inField ? '' : `<button class="btn primary" style="flex:1" data-act="manual" data-id="${esc(candidate.id)}" title="이 모듈을 해당 접속반의 운영자 추가 확인 작업지시에 넣습니다">${icon('plus')}현장 작업지시에 추가</button>`}</div>
    <a class="btn" href="${esc(viewerLink(candidate))}" target="_blank" rel="noopener" title="상세 3D 발전소에서 이 모듈로 이동하고 촬영 시각의 해로 그림자를 봅니다">${icon('cube')}3D 현장 보기 (촬영 시각 그림자)</a>
    <section><div class="between"><h3>영상</h3><div class="row">${zoomSeg()}<button class="btn icon" data-act="lightbox" title="크게 보기" aria-label="영상 크게 보기">${icon('expand')}</button></div></div>
      <div class="views">${thermalView(o, state.zoom)}${rgbView(o, state.zoom)}</div>
      <p class="sub mono">프레임 ${esc(frameNo(o.image_id))} · ${time(o.time)} · 도면 위치와의 거리 ${num(o.link_distance_m, 2)} m</p></section>
    <section><h3>같은 모듈 확대 비교</h3><div class="pair">
      <figure>${o.crop ? `<img class="px" src="${esc(o.crop)}" alt="열화상 모듈 크롭">` : ''}<figcaption>열화상</figcaption></figure>
      <figure>${o.rgb_crop ? `<img src="${esc(o.rgb_crop)}" alt="가시광 모듈 크롭">` : ''}<figcaption>가시광 (주변 포함)</figcaption></figure></div></section>
    <section class="stats">
      <div class="stat"><span class="label">최고 온도</span><b class="t-crit">${num(o.max_temp)}℃</b><span class="sub">평균 ${num(o.mean_temp)}℃</span></div>
      <div class="stat"><span class="label">주변 대비</span><b class="t-warn">${signed(o.neighbor_delta_mean)}℃</b><span class="sub">최고점 ${signed(o.neighbor_delta_max)}℃</span></div>
      <div class="stat"><span class="label">모듈 내 온도차</span><b>${num(o.delta_temp)}℃</b><span class="sub">최고 − 평균</span></div>
      <div class="stat"><span class="label">분류 모델</span><b>${num(100 * (o.prob_abnormal + o.prob_attention), 0)}%</b><span class="sub">이상 ${num(100 * o.prob_abnormal, 0)} · 주의 ${num(100 * o.prob_attention, 0)}</span></div>
    </section>
    <section><div class="between"><h3>같은 모듈의 관측 이력</h3><span class="sub">${candidate.observation_count}회 촬영 · ${candidate.flagged_count}회 후보</span></div>
      <div class="history">${candidate.observations.map((item, index) => `<button class="obs ${index === state.obs ? 'sel' : ''} ${FINAL[item.final][1]}" data-act="obs" data-id="${index}">
        <b class="mono">${esc(frameNo(item.image_id))}${item.edge ? ' <span class="t-warn">· 가장자리</span>' : ''}</b><span class="sub">${FINAL[item.final][0]} · ${signed(item.neighbor_delta_mean)}℃${item.type ? ' · ' + (TYPE[item.type] || '') : ''}</span></button>`).join('')}</div>
      ${note('태양 반사는 프레임마다 위치가 바뀝니다. 여러 프레임에서 반복해서 걸릴수록 실제 발열일 가능성이 높습니다.')}</section>
    <section><div class="between"><h3>${icon('bot')}AI 원인 추정</h3>${diagChip(candidate.id)}</div>
      ${diagnosisView(candidate.id)}
      <details class="kb"><summary>규칙 엔진이 본 증거</summary>${evidence(candidate, o)}</details>
      <details class="kb"><summary>원인 판단 기준표 (기획서 4.4절${KB.version ? ' · ' + esc(KB.version) : ''})</summary><ul>${(KB.rules.length ? KB.rules.map(r => [r.observation, r.cause, r.action]) : KNOWLEDGE).map(([seen, why, act]) => `<li><b>${esc(seen)}</b><br>${esc(why)} → ${esc(act)}</li>`).join('')}</ul></details></section>
  </div>`;
}

function modulePanel(index) {
  const a = address(index), mates = S.candidates.filter(c => c.string === a.string);
  return `<div class="pane-head"><div><div class="row wrap"><h2 class="mono">${esc(a.id)}</h2>${chip(MAP_STATE[a.state][0], MAP_STATE[a.state][1], true)}</div>
      <p class="sub">${esc(a.inverter)} › ${esc(a.jb)} › ${esc(a.string)}</p></div>
    <button class="btn icon" data-act="close" title="닫기 (Esc)" aria-label="상세 닫기">${icon('close')}</button></div>
  <div class="pane-body">
    <section>${a.state ? note('이 모듈은 촬영된 프레임에서 이상 후보로 걸리지 않았습니다. 정상 보증은 아니며, 놓쳤을 가능성은 현장 표본 검수로 확인합니다.')
      : note('이 모듈은 아직 도면 정합을 마친 촬영분에 없습니다. 결과가 없는 것이지 정상이라는 뜻이 아닙니다.')}</section>
    <section><h3>같은 스트링의 이상 후보 (${mates.length}건)</h3>
      ${mates.length ? `<div class="list flat">${mates.map(c => `<button class="item ${VERDICT[c.verdict || 'inspect'][1]}" data-act="module" data-id="${esc(c.id)}">
        <span class="between"><b class="mono">${esc(c.id)}</b><span class="delta">${signed(c.max_neighbor_delta)}℃</span></span></button>`).join('')}</div>` : '<p class="sub">이 스트링에는 후보가 없습니다.</p>'}</section>
  </div>`;
}

function lightbox(candidate) {
  const o = candidate.observations[Math.min(state.obs, candidate.observations.length - 1)];
  return `<div class="lightbox" role="dialog" aria-label="영상 크게 보기"><div class="lb-head"><b class="mono">${esc(candidate.id)}</b>
      <span class="sub">프레임 ${esc(frameNo(o.image_id))} · ${time(o.time)}</span><span style="flex:1"></span>
      <div class="seg">${candidate.observations.map((item, index) => `<button class="${index === state.obs ? 'on' : ''}" data-act="obs" data-id="${index}">${esc(frameNo(item.image_id))}</button>`).join('')}</div>
      ${zoomSeg()}<button class="btn icon" data-act="lightbox" title="닫기 (Esc)" aria-label="닫기">${icon('close')}</button></div>
    <div class="lb-body">${thermalView(o, state.zoom)}${rgbView(o, state.zoom)}</div></div>`;
}

function overview(params) {
  if (params.has('q')) { state.query = params.get('q'); state.filter = 'all'; }
  if (params.has('m')) { state.module = params.get('m'); state.obs = 0; state.zoom = 1; }
  if (params.size) history.replaceState(null, '', '#/overview');
  const candidate = candidateById.get(state.module), index = indexById.get(state.module);
  const picked = S.candidates.filter(c => fieldOrder(c.id)).length;
  return `${stageStrip()}
<div class="work ${state.module ? 'open' : ''}">
  <aside class="pane queue">
    <div class="pane-head"><h2>이상 후보</h2><span class="sub">${S.candidates.filter(matches).length} / ${S.candidates.length}건</span></div>
    <div class="queue-tools"><div class="seg">${[['all', '전체'], ['inspect', `점검 ${inspectCount}`], ['recheck', `재확인 ${recheckCount}`], ['shadow', `그림자 ${S.candidates.filter(c => c.shadow).length}`], ['picked', `작업지시 ${picked}`]]
      .map(([key, label]) => `<button class="${state.filter === key ? 'on' : ''}" data-act="filter" data-id="${key}">${label}</button>`).join('')}</div>
      <label class="search">${icon('search')}<input id="q" type="search" placeholder="모듈·스트링·접속반·인버터 ( / )" value="${esc(state.query)}" aria-label="후보 검색"></label></div>
    <div class="list" id="list">${listItems()}</div>
    <p class="keys"><kbd>J</kbd><kbd>K</kbd> 이동 · <kbd>A</kbd> 담기 · <kbd>Esc</kbd> 닫기</p>
  </aside>
  <section class="pane mapbox">
    <div id="map-slot"></div>
    <div class="float tl"><div class="seg">${[['map', '개요 지도'], ['3d', '현장 3D']].map(([key, label]) => `<button class="${state.stage === key ? 'on' : ''}" data-act="stage" data-id="${key}">${label}</button>`).join('')}</div>
      ${state.stage === '3d' ? '' : `<div class="seg">${[['final', '판정'], ['delta', '주변 대비 온도차']].map(([key, label]) => `<button class="${state.layer === key ? 'on' : ''}" data-act="layer" data-id="${key}">${label}</button>`).join('')}</div>`}</div>
    ${state.stage === '3d' ? `<div class="float tr legend"><span><i class="lg crit"></i>점검 대상</span><span><i class="lg warn"></i>재확인</span><span class="t-mute">후보를 고르면 그 모듈로 이동하고 해를 촬영 시각으로 맞춥니다</span></div>` : `<div class="float tr"><button class="btn" data-act="fit" data-id="site">전체</button><button class="btn" data-act="fit" data-id="observed">관측 구역</button>
      <button class="btn" data-act="view" data-id="top">위에서</button><button class="btn" data-act="view" data-id="tilt">기울여</button>
      <button class="btn icon" data-act="mapzoom" data-id="0.6" aria-label="확대">${icon('plus')}</button><button class="btn icon" data-act="mapzoom" data-id="1.6" aria-label="축소">${icon('minus')}</button></div>
    <div class="float bl legend">${state.layer === 'final'
      ? `<span><i class="lg crit"></i>점검 대상</span><span><i class="lg warn"></i>재확인</span><span><i class="lg ok"></i>후보 없음</span><span><i class="lg"></i>미관측</span>`
      : `<span>−2℃</span><i class="ramp"></i><span>+4℃</span><span><i class="lg"></i>미관측</span>`}<span><i class="lg pri"></i>선택한 스트링</span></div>
    <div class="float br sub">끌기: 이동 · 오른쪽 끌기: 회전 · 휠: 확대</div>`}
  </section>
  <aside class="pane detail" id="detail">${candidate ? candidatePanel(candidate) : index != null ? modulePanel(index) : summaryPanel()}</aside>
</div>
${state.lightbox && candidate ? lightbox(candidate) : ''}`;
}

// ---------- Pipeline ----------
function pipeline() {
  const unsupported = int((S.observations.structure.review || 0) + (S.observations.structure.low || 0));
  const tag = { done: chip('구현됨', 'ok'), part: chip('일부', 'warn'), none: chip('미구현') };
  return `${stageStrip()}
<div class="grid cols">
  <div class="stack">
    <div class="card"><div class="head"><h2>${icon('list')}묶음별 실행 현황</h2><span class="sub">50장 단위로 실행 · 중단되면 끝난 묶음 다음부터 이어감</span></div>
      <div class="chunks">${S.chunks.map(c => `<i class="${c.status}" title="묶음 ${esc(c.id)}"></i>`).join('')}</div>
      <div class="table-box" style="max-height:360px;margin-top:12px"><table><thead><tr><th>묶음</th><th>상태</th><th class="num">열화상</th><th class="num">모듈 관측</th><th class="num">이상·주의</th><th class="num">소요</th></tr></thead>
        <tbody>${S.chunks.map(c => `<tr><td class="mono">${esc(c.id)}</td><td>${c.status === 'done' ? chip('완료', 'ok', true) : c.status === 'running' ? chip('실행 중', 'info', true) : chip('대기')}</td>
          <td class="num">${int(c.thermal_images)}</td><td class="num">${int(c.observations)}</td><td class="num ${c.flagged ? 't-warn' : ''}">${int(c.flagged)}</td>
          <td class="num mono">${c.seconds ? num(c.seconds / 60) + '분' : '–'}</td></tr>`).join('')}</tbody></table></div></div>
    <div class="card"><div class="head"><h2>${icon('shield')}구성요소 구현 상태</h2><span class="sub">과제 기획서 2절 기준</span></div>
      <div class="engines">${COMPONENTS.map(([name, method, status, remark]) => `<div class="engine ${status}"><span><b>${name}</b><br><span class="sub">${method}${remark ? ' · ' + remark : ''}</span></span>${tag[status]}</div>`).join('')}</div></div>
  </div>
  <div class="stack">
    <div class="card"><div class="head"><h2>${icon('pin')}도면 정합과 주소 연결</h2>${chip(R.pitch_resolved ? '확정' : '후보 단계', R.pitch_resolved ? 'ok' : 'warn')}</div>
      <div class="stats two">
        <div class="stat"><span class="label">정합된 프레임</span><b>${R.frames_registered} / ${R.frames}</b></div>
        <div class="stat"><span class="label">주소 연결률</span><b>${num(pct(R.linked, R.observations))}%</b></div>
        <div class="stat"><span class="label">관측된 도면 모듈</span><b>${int(R.modules_observed)}</b></div>
        <div class="stat"><span class="label">관측된 스트링</span><b>${int(R.strings_observed)} / ${int(S.site.strings)}</b></div>
      </div>
      <p class="label" style="margin:14px 0 6px">프레임별 정합 (촬영 순)</p>
      <div class="frames">${R.frame_rows.map(f => `<i class="${f.status === 'registered' ? '' : 'no'}" title="${esc(frameNo(f.image_id))} · ${esc(f.status)} · 관측 ${f.observations}"></i>`).join('')}</div>
      ${R.lines ? `<div class="callout warn" style="margin-top:14px"><b>비행 줄 ${R.lines.resolved} / ${R.lines.total}줄의 모듈 위치를 정했습니다.</b>
        <p class="sub">줄마다 도로 틈·배열 끝(${int(R.lines.decided_by.row_ends || 0)}줄)과 줄 추세(${int(R.lines.decided_by.trend || 0)}줄)로 몇 번째 모듈인지 정했습니다. 정하지 못한 줄의 관측 ${int(R.lines.unresolved_observations)}건은 한 칸 어긋남을 배제할 수 없습니다. 측량 기준점으로 검증하기 전이므로 모든 연결은 후보입니다.</p></div>`
      : `<div class="callout warn" style="margin-top:14px"><b>모듈 한 칸 어긋남을 아직 배제하지 못했습니다.</b>
        <p class="sub">가장 잘 맞는 위치와 그다음 위치의 차이가 작아 모든 연결은 후보입니다. 측량 기준점으로 확정하기 전에는 스트링 단위로 보는 것이 안전합니다.</p></div>`}
      <ul class="sub" style="padding-left:16px;margin:10px 0 0">${R.limitations.map(l => `<li>${esc(l)}</li>`).join('')}</ul></div>
    <div class="card"><div class="head"><h2>${icon('scan')}검출 품질</h2><span class="sub">분석 완료분 ${int(S.observations.total)}건</span></div>
      ${[['배열 구조와 맞는 검출', S.observations.structure.supported || 0, 'var(--ok)'], ['검토 필요', S.observations.structure.review || 0, 'var(--warn)'], ['신뢰 낮음', S.observations.structure.low || 0, 'var(--crit)']]
        .map(([label, value, color]) => `<div style="margin-bottom:10px"><div class="between"><b>${label}</b><span class="sub">${int(value)}건 (${num(pct(value, S.observations.total))}%)</span></div>
          <div class="bar" style="margin-top:4px"><i style="width:${pct(value, S.observations.total)}%;background:${color}"></i></div></div>`).join('')}
      ${note(`배열 구조와 맞지 않는 검출이 ${unsupported}건 있습니다. 모듈 검출 정확도(누락·병합)는 현장 정답과 비교한 적이 없어 아직 수치가 없습니다.`)}</div>
  </div>
</div>`;
}

// ---------- Work orders: issue, field results, feedback metrics ----------
function orders(params) {
  if (params?.has('o')) { state.focusOrder = params.get('o'); history.replaceState(null, '', '#/orders'); }
  const list = workOrders(), res = results(), focus = state.focusOrder;
  const field = list.filter(o => FIELD.has(o.action_kind)), drone = list.filter(o => !FIELD.has(o.action_kind));
  const byStatus = WO_STATUS.map(status => field.filter(o => o.status === status).length);
  const done = Object.values(res).filter(r => r.cause), falseAlarms = done.filter(r => r.cause === '이상 없음').length;
  const causes = done.filter(r => r.cause !== '이상 없음' && r.cause !== '원인 판별 어려움'), matched = causes.filter(r => DIAG.get(r.module_id)?.primary === r.cause).length;
  const located = done.filter(r => r.location_ok !== null && r.location_ok !== undefined && r.location_ok !== ''), locatedOk = located.filter(r => Number(r.location_ok) === 1).length;
  const safety = S.orders_summary?.safety_notify || [];
  const NO_FIELD = new Set(['이상 없음', '식생 음영', '구조물·수목 음영', '오염에 의한 부분 음영', '반사 또는 음영', '태양 반사']);
  const audits = done.filter(r => DIAG.get(r.module_id)?.ai_audit), auditsRight = audits.filter(r => NO_FIELD.has(r.cause)).length;
  const sm = S.orders_summary || {};
  const options = (items, value, blank) => `<option value="">${blank}</option>` + items.map(v => `<option ${v === value ? 'selected' : ''}>${esc(v)}</option>`).join('');
  const metric = (label, value, hint, tone = 't-mute') => `<div class="stat"><span class="label">${label}</span><b class="${tone}">${value}</b><span class="sub">${hint}</span></div>`;
  const attrs = (o, m, editable) => `data-o="${esc(o.order_id)}" data-m="${esc(m)}" ${editable ? '' : 'disabled'}`;
  const card = o => {
    const editable = o.status !== '초안' && o.status !== '종결';
    const rows = o.modules.map(m => {
      const r = res[resultKey(o.order_id, m)] || {}, d = DIAG.get(m), loc = r.location_ok === null || r.location_ok === undefined || r.location_ok === '' ? '' : String(Number(r.location_ok));
      return `<tr><td><a class="mono" href="#/overview?m=${esc(m)}">${esc(m)}</a>${d ? `<br><span class="sub">${esc(d.primary)}</span>` : ''}${d?.ai_audit ? `<br>${chip('검증 표본', 'warn')}` : ''}</td>
        <td><select data-res="cause" ${attrs(o, m, editable)} aria-label="현장 확인 원인">${options([...KB.causes, '이상 없음'], r.cause, '미입력')}</select></td>
        <td><select data-res="action" ${attrs(o, m, editable)} aria-label="조치">${options(ACTIONS, r.action, '미입력')}</select></td>
        <td><select data-res="location_ok" ${attrs(o, m, editable)} aria-label="표시된 위치가 맞았는지"><option value="">위치 확인</option><option value="1" ${loc === '1' ? 'selected' : ''}>위치 맞음</option><option value="0" ${loc === '0' ? 'selected' : ''}>위치 다름</option></select></td>
        <td><input data-res="inspector" ${attrs(o, m, editable)} value="${esc(r.inspector || '')}" placeholder="확인자" aria-label="확인자"></td>
        <td><input data-res="memo" ${attrs(o, m, editable)} value="${esc(r.memo || '')}" placeholder="메모" aria-label="메모"></td>
        <td class="noprint">${o.status === '초안' ? `<button class="btn icon" data-act="remove" data-o="${esc(o.order_id)}" data-m="${esc(m)}" title="작업지시에서 빼기" aria-label="작업지시에서 빼기">${icon('close')}</button>` : ''}</td></tr>`;
    }).join('');
    return `<details class="group wo" id="wo-${esc(o.order_id)}" ${focus === o.order_id || o.status === '발행' ? 'open' : ''}>
      <summary><b>${int(o.route_order)}. ${esc(o.title)}</b> ${chip(o.status, STATUS_TONE[o.status] || '', true)}${o.carried ? chip('이전 회차 이월', 'warn') : ''}${o.safety ? chip('안전', 'crit') : ''}${o.loss_w ? ` <span class="sub">예상 손실 ${num(o.loss_w, 0)} W</span>` : ''}</summary>
      <div class="row wrap noprint" style="margin:8px 0">${o.status === '초안' ? `<button class="btn primary" data-act="issue" data-id="${esc(o.order_id)}">${icon('check')}발행 (승인)</button>`
        : `<select data-status="${esc(o.order_id)}" aria-label="작업지시 상태">${WO_STATUS.slice(1).map(v => `<option ${v === o.status ? 'selected' : ''}>${v}</option>`).join('')}</select>`}
        <span class="sub">준비물: ${esc((o.equipment || []).join(', ') || '없음')}</span></div>
      <pre class="instructions">${esc(o.instructions)}</pre>
      <div class="table-box"><table class="orders"><thead><tr><th>모듈 · 추정 원인</th><th>현장 확인 원인</th><th>조치</th><th>위치</th><th>확인자</th><th>메모</th><th class="noprint"></th></tr></thead><tbody>${rows}</tbody></table></div></details>`;
  };
  const droneCard = o => `<details class="group"><summary><b>${esc(KB.kinds[o.action_kind] || o.action_kind)}</b> · ${int(o.modules.length)}장 ${chip(o.status, STATUS_TONE[o.status] || '')}</summary>
    <p class="sub">${{ recheck: '촬영 한 번에서만 이상으로 걸렸거나 AI 외관 확인으로 내린 모듈입니다. 다음 정기 촬영에서 다시 걸리면 현장 작업지시로 올립니다.',
      retake: '드론이 줄을 바꾸며 회전하는 동안에만 찍혀 판정하지 않은 모듈입니다. 다음 촬영에서 직선 비행으로 다시 찍습니다.' }[o.action_kind] || '그림자나 반사로 보이는 모듈입니다. 다른 시간대에 다시 촬영합니다.'}</p>
    <div class="chips">${o.modules.slice(0, 300).map(m => `<a class="mono sub" href="#/overview?m=${esc(m)}">${esc(m)}</a>`).join(' ')}${o.modules.length > 300 ? ` <span class="sub">외 ${int(o.modules.length - 300)}장 (CSV에 전부)</span>` : ''}</div></details>`;
  return `${stageStrip()}
<div class="grid cols wide">
  <div class="card">
    <div class="head wrap"><div><h2>${icon('task')}현장 작업지시</h2><p class="sub">방문 순서대로 ${field.length}건, 모듈 ${int(field.reduce((n, o) => n + o.modules.length, 0))}장. 초안은 운영자가 발행해야 현장에 나갑니다.${sm.llm_reviewed ? ` 규칙만으로는 ${int(sm.field_modules_rules_only)}장이었고, GPT가 ${int(sm.llm_reviewed)}장의 외관을 확인해 ${int(sm.ai_downgraded || 0)}장의 작업을 바꿨습니다 (검증 표본 ${int(sm.ai_audit_samples || 0)}장은 그대로 현장 유지).` : ''}</p></div>
      <div class="row wrap noprint"><button class="btn" data-act="csv" ${list.length ? '' : 'disabled'}>${icon('download')}엑셀용 CSV</button>
        <button class="btn" data-act="print" ${field.length ? '' : 'disabled'}>${icon('print')}인쇄</button></div></div>
    ${live.on ? '' : `<div class="callout warn noprint"><b>입력 내용이 이 브라우저에만 저장됩니다.</b><p class="sub">프로젝트 폴더에서 <code>python serve_console.py</code>를 실행하고 안내된 주소로 열면 이력 DB(results/history.db)에 저장되고 다음 회차로 이어집니다.</p></div>`}
    ${safety.length ? `<div class="callout crit"><b>즉시 통보: 안전 위험 모듈 ${safety.length}장</b><p class="sub">${safety.map(esc).join(', ')}</p></div>` : ''}
    <div class="row wrap" style="margin:12px 0">${WO_STATUS.map((status, i) => chip(`${status} ${byStatus[i]}`, STATUS_TONE[status] || '')).join('')}</div>
    ${field.length ? field.map(card).join('') : empty('inbox', '현장 작업지시가 없습니다', '원인 추정과 작업지시를 만들려면 python run_flight.py 를 실행하세요.')}
  </div>
  <div class="stack noprint">
    <div class="card"><div class="head"><h2>${icon('camera')}다음 촬영으로 넘기는 모듈</h2></div>${drone.length ? drone.map(droneCard).join('') : '<p class="sub">없습니다.</p>'}</div>
    <div class="card"><div class="head"><h2>${icon('flow')}환류 지표</h2><span class="sub">기획서 8절</span></div>
      <div class="stats two">
        ${metric('오경보율', done.length ? num(pct(falseAlarms, done.length), 0) + '%' : '측정 전', done.length ? `결과 ${done.length}건 중 이상 없음 ${falseAlarms}건` : '현장 결과를 입력하면 계산됩니다', done.length ? 't-pri' : 't-mute')}
        ${metric('원인 일치율', causes.length ? num(pct(matched, causes.length), 0) + '%' : '측정 전', causes.length ? `원인이 확인된 ${causes.length}건 중 1순위 일치 ${matched}건` : '현장에서 원인을 확인하면 계산됩니다', causes.length ? 't-pri' : 't-mute')}
        ${metric('주소 정확도', located.length ? num(pct(locatedOk, located.length), 0) + '%' : '측정 전', located.length ? `위치 확인 ${located.length}건 중 맞음 ${locatedOk}건` : '현장에서 위치가 맞았는지 적으면 계산됩니다', located.length ? 't-pri' : 't-mute')}
        ${metric('AI 하향 정확도', audits.length ? num(pct(auditsRight, audits.length), 0) + '%' : '측정 전', audits.length ? `검증 표본 ${audits.length}건 중 현장 점검 불필요 ${auditsRight}건` : `검증 표본 ${int(sm.ai_audit_samples || 0)}장의 현장 결과로 계산됩니다`, audits.length ? 't-pri' : 't-mute')}
        ${metric('미검출률', '측정 전', '정상 판정 모듈의 표본 검수가 필요합니다')}
      </div>
      ${note('지표는 현장 확인 결과로만 계산하고, 프로그램 판정을 정답으로 쓰지 않습니다.')}</div>
    <div class="card"><div class="head"><h2>${icon('info')}알아둘 점</h2></div>
      <ul class="sub plain"><li>작업지시는 접속반 × 작업 종류로 묶었고, 안전 → 손실 → 반복 관측 순으로 우선순위를, 가까운 접속반 순으로 방문 순서를 정했습니다.</li>
        <li>예상 손실은 정격 250W 기준의 추정치입니다. 실제 손실은 정비 전후 발전량으로 바꿀 예정입니다.</li>
        <li>주소 연결이 후보 단계라, 현장에서는 표시된 모듈의 양옆도 함께 확인하고 위치가 맞았는지 적어 주세요.</li></ul></div>
  </div>
</div>`;
}

function exportCsv() {
  const quote = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
  const res = results();
  const lines = [['방문 순서', '작업지시', '작업 종류', '상태', '인버터', '접속반', '스트링', '모듈', '모듈 판정', '추정 원인', '권장 조치', '긴급도', '예상 손실(W)', '현장 확인 원인', '조치', '위치', '확인자', '확인일', '메모', '3D 위치']];
  workOrders().forEach(o => o.modules.forEach(m => {
    const c = candidateById.get(m), d = DIAG.get(m), r = res[resultKey(o.order_id, m)] || {}, a = indexById.has(m) ? address(indexById.get(m)) : {};
    lines.push([o.route_order, o.order_id, KB.kinds[o.action_kind] || o.action_kind, o.status, a.inverter || o.inverter_id, a.jb || o.jb_id, a.string || '', m,
      c ? VERDICT[c.verdict || 'inspect'][0] : '', d?.primary || '', d?.action || '', d?.urgency || '', d?.loss_w ?? '', r.cause || '', r.action || '',
      r.location_ok === undefined || r.location_ok === null || r.location_ok === '' ? '' : Number(r.location_ok) === 1 ? '맞음' : '다름', r.inspector || '', r.inspected_on || '', r.memo || '',
      c ? new URL(viewerLink(c), location.href).href : '']);
  }));
  // BOM so Excel opens the Korean text as UTF-8.
  const url = URL.createObjectURL(new Blob(['﻿' + lines.map(line => line.map(quote).join(',')).join('\r\n')], { type: 'text/csv' }));
  Object.assign(document.createElement('a'), { href: url, download: `작업지시_${S.site.name}_${new Date().toISOString().slice(0, 10)}.csv` }).click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

// ---------- Map, render, events ----------
const PAGES = { overview, pipeline, orders };
const mapHost = Object.assign(document.createElement('div'), { className: 'map-host' });
const tooltip = Object.assign(document.createElement('div'), { className: 'tip', hidden: true });
document.body.append(tooltip);
let map = null, mapFailed = false;

function mountMap() {
  const slot = document.getElementById('map-slot');
  if (!slot) return;
  slot.append(mapHost);
  if (map || mapFailed) return;
  try {
    map = window.SiteMap.create(mapHost, M, {
      onPick: index => { if (index >= 0) select(M.ids[index], false); },
      onHover: (index, x, y) => {
        tooltip.hidden = index < 0;
        mapHost.style.cursor = index < 0 ? '' : 'pointer';
        if (index < 0) return;
        const a = address(index);
        tooltip.innerHTML = `<b class="mono">${esc(a.id)}</b><br>${esc(a.inverter)} › ${esc(a.jb)} › ${esc(a.string)}<br><span class="${MAP_STATE[a.state][1] ? 't-' + MAP_STATE[a.state][1] : ''}">${MAP_STATE[a.state][0]}</span>`;
        tooltip.style.left = Math.min(x + 14, innerWidth - 240) + 'px';
        tooltip.style.top = y + 14 + 'px';
      },
    });
    map.setTheme(state.theme);
    map.fit(observedIndices());
    if (state.module) map.select(indexById.get(state.module) ?? -1);
  } catch (error) {
    mapFailed = true;
    mapHost.innerHTML = `<div class="empty" style="margin:16px">${icon('cube')}<b>3D 지도를 표시할 수 없습니다</b><span>이 브라우저에서 WebGL을 쓸 수 없습니다. 왼쪽 목록으로 후보를 확인할 수 있습니다.</span></div>`;
    console.error(error);
  }
}
const observedIndices = () => [...M.state].flatMap((s, i) => s === '0' ? [] : [i]);

// The detailed viewer lives in one iframe that is never moved in the DOM (moving reloads it);
// it is laid over the map panel while the 현장 3D stage is shown.
const viewerHost = Object.assign(document.createElement('div'), { className: 'viewer-host', hidden: true });
document.body.append(viewerHost);
let viewerFrame = null, viewerReady = false, viewerPending = null;
function sendToViewer(id) {
  const candidate = candidateById.get(id);
  viewerPending = id ? { type: 'aerosolar:select', module: id, at: candidate?.observations[0]?.time || '' } : null;
  if (viewerReady && viewerPending) viewerFrame.contentWindow.postMessage(viewerPending, '*');
}
function placeViewer() {
  const slot = document.getElementById('map-slot');
  const show = state.stage === '3d' && route().page === 'overview' && !!slot;
  viewerHost.hidden = !show;
  if (!show) return;
  if (!viewerFrame) {
    viewerFrame = Object.assign(document.createElement('iframe'), { title: '현장 3D', allow: 'fullscreen' });
    viewerFrame.src = 'viewer/Shinan3_Viewer.html?embed=1&view=overview';
    viewerHost.append(viewerFrame);
    sendToViewer(state.module);
  }
  const rect = slot.getBoundingClientRect();
  Object.assign(viewerHost.style, { left: rect.left + scrollX + 'px', top: rect.top + scrollY + 'px', width: rect.width + 'px', height: rect.height + 'px' });
}
addEventListener('message', event => {
  const message = event.data;
  if (!viewerFrame || event.source !== viewerFrame.contentWindow || !message) return;
  if (message.type === 'aerosolar:ready') { viewerReady = true; if (viewerPending) viewerFrame.contentWindow.postMessage(viewerPending, '*'); }
  if (message.type === 'aerosolar:selected' && message.module !== state.module && indexById.has(message.module)) select(message.module, false, false);
});
addEventListener('resize', placeViewer);

function render() {
  document.documentElement.dataset.theme = state.theme;
  const scrollers = ['#list', '#detail .pane-body'], keep = scrollers.map(selector => document.querySelector(selector)?.scrollTop);
  const { page, params } = route();
  mapHost.remove();
  app.innerHTML = shell(page, PAGES[page](params));
  if (state.stage === 'map') mountMap();
  placeViewer();
  scrollers.forEach((selector, i) => { const element = document.querySelector(selector); if (element && keep[i]) element.scrollTop = keep[i]; });
}

function select(id, focus = true, toViewer = true) {
  const changed = id !== state.module;
  state.module = id;
  if (changed) { state.obs = 0; state.zoom = 1; }
  if (!id) state.lightbox = false;
  if (route().page !== 'overview') { location.hash = '#/overview'; }
  render();
  map?.select(id ? indexById.get(id) ?? -1 : -1, { focus });
  if (toViewer && state.stage === '3d') sendToViewer(id);
  if (changed) document.querySelector('#detail .pane-body')?.scrollTo(0, 0);
  document.querySelector('#list .item.sel')?.scrollIntoView({ block: 'nearest' });
}

function toast(message) {
  document.querySelector('.toast')?.remove();
  const element = Object.assign(document.createElement('div'), { className: 'toast', textContent: message });
  element.setAttribute('role', 'status');
  document.body.append(element);
  setTimeout(() => element.remove(), 2600);
}

function stepCandidate(direction) {
  const visible = S.candidates.filter(matches);
  if (!visible.length) return;
  const position = visible.findIndex(c => c.id === state.module);
  const next = visible[Math.max(0, Math.min(visible.length - 1, position < 0 ? 0 : position + direction))];
  select(next.id);
}

document.addEventListener('click', event => {
  const target = event.target.closest('[data-act]');
  if (!target) return;
  const { act, id } = target.dataset;
  if (act === 'module') return select(id);
  if (act === 'close') return select(null);
  if (act === 'step') return stepCandidate(Number(id));
  if (act === 'fit') return map?.fit(id === 'observed' ? observedIndices() : null);
  if (act === 'view') return map?.view(id);
  if (act === 'mapzoom') return map?.zoom(Number(id));
  if (act === 'csv') return exportCsv();
  if (act === 'print') return print();
  if (act === 'string') { state.query = id; state.filter = 'all'; map?.fit(M.string.flatMap((s, i) => M.strings[s][0] === id ? [i] : [])); }
  if (act === 'inverter') {
    state.query = id; state.filter = 'all';
    map?.fit(M.string.flatMap((s, i) => M.strings[s][2] === id ? [i] : []));
  }
  if (act === 'theme') { state.theme = state.theme === 'dark' ? 'light' : 'dark'; store.set('theme', state.theme); map?.setTheme(state.theme); }
  if (act === 'layer') { state.layer = id; map?.setLayer(id); }
  if (act === 'stage') { state.stage = id; store.set('stage', id); if (id === '3d') sendToViewer(state.module); }
  if (act === 'filter') state.filter = id;
  if (act === 'obs') state.obs = Number(id);
  if (act === 'zoom') state.zoom = Number(id);
  if (act === 'review') { if (id) state.reviews[state.module] = id; else delete state.reviews[state.module]; saveReviews(); }
  if (act === 'lightbox') state.lightbox = !state.lightbox;
  if (act === 'issue') return setStatus(id, '발행');
  if (act === 'manual') { toast('작업지시에 추가합니다.'); return addManual(id); }
  if (act === 'remove') return removeModule(target.dataset.o, target.dataset.m);
  render();
});
document.addEventListener('input', event => {
  if (event.target.id === 'q') { state.query = event.target.value; document.getElementById('list').innerHTML = listItems(); }
});
document.addEventListener('change', event => {
  const { res, o, m, status } = event.target.dataset;
  if (status) return setStatus(status, event.target.value);
  if (!res) return;
  const value = res === 'location_ok' ? (event.target.value === '' ? null : Number(event.target.value)) : event.target.value;
  saveResult(o, m, res, value);
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    if (state.lightbox) { state.lightbox = false; return render(); }
    if (event.target.id === 'q') return event.target.blur();
    if (state.module && route().page === 'overview') return select(null);
  }
  if (event.target.matches('input, select, textarea') || event.ctrlKey || event.metaKey || event.altKey || route().page !== 'overview') return;
  const key = event.key.toLowerCase();
  if (key === '/') { event.preventDefault(); document.getElementById('q')?.focus(); }
  if (key === 'j' || event.key === 'ArrowDown') { event.preventDefault(); stepCandidate(1); }
  if (key === 'k' || event.key === 'ArrowUp') { event.preventDefault(); stepCandidate(-1); }
  if (key === 'a' && candidateById.has(state.module) && !fieldOrder(state.module)) { toast('작업지시에 추가합니다.'); addManual(state.module); }
});
window.addEventListener('hashchange', () => { tooltip.hidden = true; render(); if (state.module) map?.select(indexById.get(state.module) ?? -1); });
render();
connect().then(() => { if (live.on) { orderIndex = null; render(); } });
})();
