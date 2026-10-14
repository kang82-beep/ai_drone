// Link to the AeroSolar OPS console (web/index.html). Reads window.SITE written by
// export_web_data.py when the viewer is built into web/viewer/; without it this does nothing.
//   ?module=S3-G0009-R1-M09   fly to that module and open its inspection card
//   &at=2025-10-30T09:12:07   set the sun to that capture time (KST) to check for shadows
//   &embed=1                  inside the console's map panel: no own card or sidebar; selection is
//                             exchanged with the console by postMessage (aerosolar:select / selected / ready)
import * as THREE from 'three';

const VERDICT = {inspect: ['점검 대상', 0xe11d48, '#e11d48'], recheck: ['재확인', 0xf59e0b, '#f59e0b']};
const TYPE = {single_cell: '단일 셀 핫스팟', multi_cell: '다중 셀 핫스팟', diode: '다이오드 의심 (1/3 띠)', whole_module: '모듈 전체 발열',
  low_edge_band: '하단 띠 (낮은 쪽)', high_edge_band: '상단 띠 (높은 쪽)', linear_streak: '선형 띠', partial_shade: '부분 그늘',
  none: '뚜렷한 형상 없음', unreadable: '형상 판독 불가'};

export function createConsoleLink({scene, modules, index, slope, tilt, length, select, solar}) {
  const site = window.SITE;
  if (!site || !Array.isArray(site.candidates)) return {onSelect() {}, start() {}};
  const params = new URLSearchParams(location.search);
  const byId = new Map(site.candidates.map(c => [c.id, c]));
  const embedded = params.has('embed');
  let fromConsole = false;
  if (embedded) {
    const style = document.createElement('style');
    style.textContent = 'header,.sidebar,#inspection-controls,#console-card{display:none!important}';
    document.head.append(style);
  }

  // Verdict markers: a coloured sheet just above each candidate panel plus a tall beacon,
  // so candidates stand out both close up and from the overview.
  const placed = site.candidates.filter(c => index.has(c.id));
  const sheet = new THREE.InstancedMesh(new THREE.BoxGeometry(1.0, .02, length + .02), new THREE.MeshBasicMaterial({transparent: true, opacity: .55, depthWrite: false}), placed.length);
  const beacon = new THREE.InstancedMesh(new THREE.CylinderGeometry(.035, .035, 4, 6), new THREE.MeshBasicMaterial({transparent: true, opacity: .6}), placed.length);
  const o = new THREE.Object3D(), colour = new THREE.Color();
  placed.forEach((c, i) => {
    const m = modules[index.get(c.id)];
    o.position.set(m.x, m.y + .04, -m.n); o.rotation.set(tilt, 0, 0); o.scale.set(1, 1, 1); o.updateMatrix(); sheet.setMatrixAt(i, o.matrix);
    o.position.set(m.x, m.y + 2.4, -m.n); o.rotation.set(0, 0, 0); o.updateMatrix(); beacon.setMatrixAt(i, o.matrix);
    colour.setHex((VERDICT[c.verdict] || VERDICT.inspect)[1]); sheet.setColorAt(i, colour); beacon.setColorAt(i, colour);
  });
  for (const mesh of [sheet, beacon]) { mesh.instanceMatrix.needsUpdate = true; mesh.computeBoundingSphere(); mesh.renderOrder = 2; scene.add(mesh); }

  const card = document.createElement('section');
  card.id = 'console-card';
  card.hidden = true;
  card.style.cssText = 'position:absolute;z-index:6;left:28px;top:118px;width:300px;max-height:calc(100vh - 250px);overflow:auto;padding:18px;background:#111f28f2;border:1px solid #c4d4d240;border-radius:8px;box-shadow:0 16px 45px #08101855;backdrop-filter:blur(16px);font-size:13px;line-height:1.5';
  document.body.append(card);
  const toggle = document.createElement('button');
  toggle.textContent = '점검 판정 표시 켜짐';
  toggle.setAttribute('aria-pressed', 'true');
  toggle.style.cssText = 'position:absolute;z-index:6;left:28px;bottom:150px;padding:8px 12px;border-radius:6px;border:1px solid #c4d4d240;background:#111f28e8;color:#f0f4f0;cursor:pointer';
  toggle.onclick = () => { const on = !sheet.visible; sheet.visible = beacon.visible = on; toggle.textContent = '점검 판정 표시 ' + (on ? '켜짐' : '꺼짐'); toggle.setAttribute('aria-pressed', String(on)); };
  document.body.append(toggle);
  const sidebar = document.querySelector('.sidebar');
  const esc = v => String(v ?? '').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
  const num = (v, d = 1) => v == null ? '–' : Number(v).toFixed(d);
  const signed = v => v == null ? '–' : (v > 0 ? '+' : '') + Number(v).toFixed(1);
  const img = (src, alt) => src ? `<img src="../${esc(src)}" alt="${esc(alt)}" style="width:100%;aspect-ratio:4/3;object-fit:contain;background:#000;border-radius:6px;image-rendering:pixelated">` : '';
  const button = 'padding:6px 10px;border-radius:6px;border:1px solid #c4d4d250;background:#1d3240;color:#f0f4f0;cursor:pointer';

  function setSunTo(iso) {
    const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/.exec(iso || '');
    if (match) solar.setTime(match[1], Number(match[2]) * 60 + Number(match[3]));
  }
  function render(id) {
    const c = byId.get(id);
    if (!c) { card.hidden = true; if (sidebar) sidebar.hidden = false; return; }
    const obs = c.observations[0] || {}, [label, , css] = VERDICT[c.verdict] || VERDICT.inspect;
    card.innerHTML = `<div style="display:flex;justify-content:space-between;gap:8px;align-items:center">
        <b style="font-family:Consolas,monospace">${esc(c.id)}</b><button data-act="close" aria-label="점검 카드 닫기" style="${button}">✕</button></div>
      <p style="margin:6px 0"><span style="color:${css};font-weight:700">● ${label}</span> · ${esc(TYPE[c.type] || '')}${c.shadow ? ' · <span style="color:#f7c56b">그림자 의심</span>' : ''}</p>
      <p style="margin:0 0 8px;color:#a9bcc4">${esc(c.inverter)} › ${esc(c.jb)} › ${esc(c.string)}<br>${esc(c.verdict_reason || '')}</p>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">${img(obs.crop, '열화상 모듈 크롭')}${img(obs.rgb_crop, '가시광 모듈 크롭')}</div>
      <p style="margin:8px 0;color:#a9bcc4">최고 ${num(obs.max_temp)}℃ · 주변 대비 ${signed(obs.neighbor_delta_mean)}℃ · 촬영 ${esc((obs.time || '').replace('T', ' '))}</p>
      ${c.shadow ? '<p style="margin:0 0 8px;color:#f7c56b">촬영 시각의 해로 바꿔 이 모듈에 그림자가 드리우는지 확인하세요. 도면에 없는 기둥·수목·풀은 재현되지 않습니다.</p>' : ''}
      <div style="display:flex;flex-wrap:wrap;gap:6px">
        <button data-act="sun" style="${button}">촬영 시각의 해로</button>
        <a href="../index.html#/overview?m=${encodeURIComponent(c.id)}" style="${button};text-decoration:none">관제 화면에서 보기</a></div>`;
    card.hidden = false;
    if (sidebar) sidebar.hidden = true;
  }
  card.addEventListener('click', e => {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'close') { card.hidden = true; if (sidebar) sidebar.hidden = false; }
    if (act === 'sun') setSunTo(byId.get(card.dataset.id)?.observations[0]?.time);
  });

  if (embedded) {
    addEventListener('message', event => {
      const message = event.data;
      if (!message || message.type !== 'aerosolar:select') return;
      if (index.has(message.module)) { fromConsole = true; select(index.get(message.module), true); fromConsole = false; }
      if (message.at) setSunTo(message.at);
    });
  }

  return {
    onSelect(id) {
      card.dataset.id = id;
      if (!embedded) return render(id);
      if (!fromConsole) parent.postMessage({type: 'aerosolar:selected', module: id}, '*');
    },
    start() {
      const id = params.get('module');
      if (id && index.has(id)) select(index.get(id), true);
      if (params.has('at')) setSunTo(params.get('at'));
      if (embedded) parent.postMessage({type: 'aerosolar:ready'}, '*');
    },
  };
}
