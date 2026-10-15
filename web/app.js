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
  orders: JSON.parse(store.get('orders') || '{}'),
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
const NAV = [['overview', '현황', 'map'], ['pipeline', '파이프라인', 'flow'], ['orders', '점검 목록', 'task']];
const ORDER_STATUS = ['점검 대기', '점검 완료', '조치 완료', '종결'];
const CAUSES = ['오염에 의한 부분 음영', '셀 균열·셀 불량', '바이패스 다이오드 고장', '커넥터 불량·모듈 개방', '스트링 단선·퓨즈 용단', '식생·구조물 음영', '태양 반사', '이상 없음', '원인 판별 어려움'];
const ACTIONS = ['조치 없음', '청소', '제초', '모듈 교체 접수', '커넥터·퓨즈 교체', '재촬영 필요'];
// 과제_기획서.md 2절의 구성요소별 현재 상태.
const COMPONENTS = [
  ['촬영 조건 확인 (일사, 속도)', '규칙', 'part', '일사 기준만 구현'], ['방사온도 추출', 'DJI SDK', 'done', ''],
  ['모듈 검출·분할', 'Mask R-CNN', 'done', '정확도 미측정'], ['열화상–가시광 정합', '고정 변환 (M4T 짐벌)', 'part', S.rgb_alignment ? `오차 중앙값 ${num(S.rgb_alignment.offset_from_fixed_px_median, 0)}px · 프레임별 미세 조정 없음` : ''],
  ['설비 주소 연결', 'RTK 투영 + 카메라 보정 + 비행 줄 연결', 'part', S.registration.lines ? `비행 줄 ${S.registration.lines.resolved}/${S.registration.lines.total} 결정 · 측량 검증 전` : '한 칸 어긋남 미해결'], ['다중 촬영 통합', '규칙', 'done', '다수결 판정, 가장자리 관측 제외'],
  ['주변 대비 온도차', '규칙', 'done', ''], ['접속반·인버터 단위 비교', '규칙', 'part', '반경 6m 이웃·스트링 비교, 인버터 단위는 전체 분석 후'],
  ['이상 탐지', '규칙 + EfficientNet-B3', 'done', '표시 영상 기반'], ['이상 유형 분류', '형상 규칙 (온도 배열)', 'part', '1차 규칙 · 현장 검증 전'],
  ['원인 추정', 'AI 에이전트', 'none', ''], ['손실·우선순위 산정', '규칙', 'none', ''],
  ['작업지시 생성', 'AI 에이전트', 'none', '지금은 사람이 점검 목록에 담음'], ['점검 결과 환류', '머신러닝 운영', 'part', '결과 입력·오경보율만'],
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
const orderCount = () => Object.keys(state.orders).length;
const saveOrders = () => store.set('orders', JSON.stringify(state.orders));
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
  <nav class="tabs">${NAV.map(([id, label, ic]) => `<a href="#/${id}" class="${id === page ? 'on' : ''}">${icon(ic)}<span>${label}</span>${id === 'orders' && orderCount() ? `<em>${orderCount()}</em>` : ''}</a>`).join('')}</nav>
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
    ['AI 원인 추정', '연결 전', '증거 묶음만 표시', 'none', '#/pipeline'],
    ['점검·환류', `${orderCount()}건`, '점검 목록에 담긴 모듈', orderCount() ? 'part' : 'none', '#/orders'],
  ];
  return `<nav class="strip" aria-label="점검 단계">${steps.map(([title, value, sub, tone, href], i) => `<a class="step ${tone}" href="${href}">
    <span class="n">${i + 1}</span><span class="body"><span class="label">${title}</span><b>${value}</b><small>${sub}</small></span></a>`).join('')}</nav>`;
}

// ---------- Overview: queue + 3D map + detail ----------
function matches(candidate) {
  const text = state.query.trim().toLowerCase();
  return (state.filter === 'all' || (candidate.verdict || 'inspect') === state.filter || (state.filter === 'picked' && state.orders[candidate.id])
      || (state.filter === 'shadow' && candidate.shadow))
    && (!text || [candidate.id, candidate.string, candidate.jb, candidate.inverter].some(v => v.toLowerCase().includes(text)));
}

function listItems() {
  const items = S.candidates.filter(matches);
  if (!items.length) return empty('search', '조건에 맞는 후보가 없습니다', '검색어나 구분을 바꿔 보세요.');
  return items.map(c => `<button class="item ${VERDICT[c.verdict || 'inspect'][1]} ${c.id === state.module ? 'sel' : ''}" data-act="module" data-id="${esc(c.id)}">
    <span class="between"><b class="mono">${esc(c.id)}</b><span class="delta">${signed(c.max_neighbor_delta)}℃</span></span>
    <span class="between sub"><span>${esc(c.jb)} · ${esc(c.string)}</span><span>${state.orders[c.id] ? `<span class="t-pri">담김 · </span>` : ''}후보 ${c.flagged_count}/${c.observation_count}회</span></span>
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
  const picked = state.orders[candidate.id];
  const stringMates = S.candidates.filter(c => c.string === candidate.string);
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
      <button class="btn ${picked ? 'on' : 'primary'}" style="flex:1" data-act="pick" data-id="${esc(candidate.id)}">${icon(picked ? 'check' : 'plus')}${picked ? '점검 목록에 담김' : '점검 목록에 담기'}</button>
      ${stringMates.length > 1 ? `<button class="btn" data-act="pick-string" data-id="${esc(candidate.string)}" title="같은 스트링의 후보 ${stringMates.length}건을 함께 담습니다">스트링 후보 ${stringMates.length}건 담기</button>` : ''}</div>
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
    <section><div class="between"><h3>${icon('bot')}AI 원인 추정</h3>${chip('연결 전')}</div>
      <p class="sub">원인 추정 에이전트가 연결되면 원인 후보·근거·권장 조치가 여기에 나옵니다. 지금은 에이전트에 넘길 증거 묶음만 보여 줍니다.</p>
      ${evidence(candidate, o)}
      <details class="kb"><summary>원인 판단 기준표 (기획서 4.4절)</summary><ul>${KNOWLEDGE.map(([seen, why, act]) => `<li><b>${seen}</b><br>${why} → ${act}</li>`).join('')}</ul></details></section>
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
  const picked = S.candidates.filter(c => state.orders[c.id]).length;
  return `${stageStrip()}
<div class="work ${state.module ? 'open' : ''}">
  <aside class="pane queue">
    <div class="pane-head"><h2>이상 후보</h2><span class="sub">${S.candidates.filter(matches).length} / ${S.candidates.length}건</span></div>
    <div class="queue-tools"><div class="seg">${[['all', '전체'], ['inspect', `점검 ${inspectCount}`], ['recheck', `재확인 ${recheckCount}`], ['shadow', `그림자 ${S.candidates.filter(c => c.shadow).length}`], ['picked', `담김 ${picked}`]]
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

// ---------- Orders: inspection list, field results, feedback metrics ----------
const orderRows = () => S.candidates.filter(c => state.orders[c.id]).map(c => ({ c, o: state.orders[c.id] }));

function orders() {
  const rows = orderRows();
  const groups = {};
  rows.forEach(row => ((groups[`${row.c.inverter} › ${row.c.jb}`] ||= {})[row.c.string] ||= []).push(row));
  const byStatus = ORDER_STATUS.map(status => rows.filter(r => r.o.status === status).length);
  const judged = rows.filter(r => r.o.status !== ORDER_STATUS[0] && r.o.cause), falseAlarms = judged.filter(r => r.o.cause === '이상 없음').length;
  const options = (list, value, blank) => `<option value="">${blank}</option>` + list.map(v => `<option ${v === value ? 'selected' : ''}>${v}</option>`).join('');
  const metric = (label, value, hint, tone = 't-mute') => `<div class="stat"><span class="label">${label}</span><b class="${tone}">${value}</b><span class="sub">${hint}</span></div>`;
  return `${stageStrip()}
<div class="grid cols wide">
  <div class="card">
    <div class="head wrap"><div><h2>${icon('task')}점검 목록</h2><p class="sub">인버터 › 접속반 › 스트링 순으로 묶었습니다. 현장에서 확인한 결과를 바로 적을 수 있습니다.</p></div>
      <div class="row wrap noprint"><button class="btn" data-act="pick-final" data-id="inspect">${icon('plus')}점검 대상 ${inspectCount}건 담기</button>
        <button class="btn" data-act="pick-final" data-id="all">${icon('plus')}재확인 포함 전부 담기</button>
        <button class="btn" data-act="csv" ${rows.length ? '' : 'disabled'}>${icon('download')}엑셀용 CSV</button>
        <button class="btn" data-act="print" ${rows.length ? '' : 'disabled'}>${icon('print')}인쇄</button>
        <button class="btn danger" data-act="clear" ${rows.length ? '' : 'disabled'}>${icon('trash')}비우기</button></div></div>
    ${rows.length ? `<div class="row wrap" style="margin-bottom:12px">${ORDER_STATUS.map((status, i) => chip(`${status} ${byStatus[i]}`, ['warn', 'info', 'ok', ''][i])).join('')}</div>` : ''}
    ${rows.length ? Object.entries(groups).map(([group, strings]) => `<div class="group"><h3>${icon('pin')}${esc(group)}</h3>
      ${Object.entries(strings).map(([string, items]) => `<div class="table-box"><table class="orders"><thead><tr><th>${esc(string)} · ${items.length}장</th><th>판정</th><th class="num">주변 대비</th><th>상태</th><th>현장 확인 원인</th><th>조치</th><th>확인자 · 메모</th><th class="noprint"></th></tr></thead>
        <tbody>${items.map(({ c, o }) => `<tr><td><a class="mono" href="#/overview?m=${esc(c.id)}">${esc(c.id)}</a></td><td>${finalChip(c.final)}</td><td class="num mono">${signed(c.max_neighbor_delta)}℃</td>
          <td><select data-field="status" data-id="${esc(c.id)}" aria-label="상태">${ORDER_STATUS.map(v => `<option ${v === o.status ? 'selected' : ''}>${v}</option>`).join('')}</select></td>
          <td><select data-field="cause" data-id="${esc(c.id)}" aria-label="현장 확인 원인">${options(CAUSES, o.cause, '미입력')}</select></td>
          <td><select data-field="action" data-id="${esc(c.id)}" aria-label="조치">${options(ACTIONS, o.action, '미입력')}</select></td>
          <td><input data-field="memo" data-id="${esc(c.id)}" value="${esc(o.memo)}" placeholder="확인자, 특이사항" aria-label="확인자와 메모"></td>
          <td class="noprint"><button class="btn icon" data-act="pick" data-id="${esc(c.id)}" title="목록에서 빼기" aria-label="목록에서 빼기">${icon('close')}</button></td></tr>`).join('')}</tbody></table></div>`).join('')}</div>`).join('')
      : empty('inbox', '점검 목록이 비어 있습니다', '현황 화면에서 이상 후보를 살펴보고 “점검 목록에 담기”를 누르거나, 위 버튼으로 한 번에 담으세요.')}
  </div>
  <div class="stack noprint">
    <div class="card"><div class="head"><h2>${icon('flow')}환류 지표</h2><span class="sub">기획서 8절</span></div>
      <div class="stats two">
        ${metric('오경보율', judged.length ? num(pct(falseAlarms, judged.length), 0) + '%' : '측정 전', judged.length ? `결과 입력 ${judged.length}건 중 이상 없음 ${falseAlarms}건` : '현장 결과를 입력하면 계산됩니다', judged.length ? 't-pri' : 't-mute')}
        ${metric('미검출률', '측정 전', '정상 판정 모듈의 표본 검수가 필요합니다')}
        ${metric('원인 일치율', '측정 전', '원인 추정 에이전트 연결 후 계산됩니다')}
        ${metric('주소 연결률', num(pct(R.linked, R.observations)) + '%', `후보 기준 · ${R.frames}장`, 't-pri')}
      </div>
      ${note('지표는 현장 확인 결과로만 계산하고, 프로그램 판정을 정답으로 쓰지 않습니다.')}</div>
    <div class="card"><div class="head"><h2>${icon('info')}알아둘 점</h2></div>
      <ul class="sub plain"><li>목록과 입력 내용은 <b>이 PC의 이 브라우저에만</b> 저장됩니다. CSV로 내보내 보관하세요.</li>
        <li>추정 원인·예상 손실·방문 순서는 원인 추정과 점검 생성 에이전트가 연결된 뒤 채워집니다.</li>
        <li>주소 연결이 후보 단계라, 현장에서는 표시된 모듈의 양옆 모듈도 함께 확인하세요.</li></ul></div>
  </div>
</div>`;
}

function exportCsv() {
  const quote = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
  const lines = [['인버터', '접속반', '스트링', '모듈', '모듈 판정', '판정 사유', '관측 판정', '주변 대비(℃)', '최고 온도(℃)', '후보 횟수', '관측 횟수', '판정 근거', '형상', '그림자 의심', '상태', '현장 확인 원인', '조치', '확인자·메모', '3D 위치']];
  orderRows().forEach(({ c, o }) => lines.push([c.inverter, c.jb, c.string, c.id, VERDICT[c.verdict || 'inspect'][0], c.verdict_reason || '', FINAL[c.final][0], num(c.max_neighbor_delta), num(c.observations[0].max_temp), c.flagged_count, c.observation_count,
    c.observations[0].reasons.map(r => REASON[r]).join(' / ') || '분류 모델', TYPE[c.type] || '', c.shadow ? (SHADOW_REVIEW[state.reviews[c.id]] || ['확인 필요'])[0] : '', o.status, o.cause, o.action, o.memo, new URL(viewerLink(c), location.href).href]));
  // BOM so Excel opens the Korean text as UTF-8.
  const url = URL.createObjectURL(new Blob(['﻿' + lines.map(line => line.map(quote).join(',')).join('\r\n')], { type: 'text/csv' }));
  Object.assign(document.createElement('a'), { href: url, download: `점검목록_${S.site.name}_${new Date().toISOString().slice(0, 10)}.csv` }).click();
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

function toggleOrder(ids, force) {
  ids.forEach(id => {
    if (force ?? !state.orders[id]) state.orders[id] ||= { status: ORDER_STATUS[0], cause: '', action: '', memo: '' };
    else delete state.orders[id];
  });
  saveOrders();
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
  if (act === 'pick') { toggleOrder([id]); toast(state.orders[id] ? '점검 목록에 담았습니다.' : '점검 목록에서 뺐습니다.'); }
  if (act === 'pick-string') { const ids = S.candidates.filter(c => c.string === id).map(c => c.id); toggleOrder(ids, true); toast(`${id} 후보 ${ids.length}건을 담았습니다.`); }
  if (act === 'pick-final') { const ids = S.candidates.filter(c => id === 'all' || (c.verdict || 'inspect') === id).map(c => c.id); toggleOrder(ids, true); toast(`${ids.length}건을 담았습니다.`); }
  if (act === 'clear') { if (!confirm('점검 목록과 입력한 현장 결과를 모두 지울까요?')) return; state.orders = {}; saveOrders(); }
  render();
});
document.addEventListener('input', event => {
  if (event.target.id === 'q') { state.query = event.target.value; document.getElementById('list').innerHTML = listItems(); }
  const { field, id } = event.target.dataset;
  if (field === 'memo' && state.orders[id]) { state.orders[id].memo = event.target.value; saveOrders(); }
});
document.addEventListener('change', event => {
  const { field, id } = event.target.dataset;
  if (!field || field === 'memo' || !state.orders[id]) return;
  state.orders[id][field] = event.target.value;
  // Entering a result means the module was inspected.
  if (field === 'cause' && event.target.value && state.orders[id].status === ORDER_STATUS[0]) state.orders[id].status = ORDER_STATUS[1];
  saveOrders();
  render();
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
  if (key === 'a' && candidateById.has(state.module)) { toggleOrder([state.module]); toast(state.orders[state.module] ? '점검 목록에 담았습니다.' : '점검 목록에서 뺐습니다.'); render(); }
});
window.addEventListener('hashchange', () => { tooltip.hidden = true; render(); if (state.module) map?.select(indexById.get(state.module) ?? -1); });
render();
})();
