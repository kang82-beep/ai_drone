"""PV inspection: reports."""
from __future__ import annotations
from . import config
from typing import List, Dict, Tuple, Optional
import os, re, json, time, math, shutil, subprocess, io
import pandas as pd
from .files import ensure_dir

def build_satellite_map_js(
    df: pd.DataFrame, map_html_path: str, map_geojson_path: str,
    image_status: Dict[str, Dict[str, bool]], image_gps: Dict[str, Tuple[Optional[float], Optional[float]]],
    thermal_path_by_id: Dict[str, str], rgb_path_by_id: Dict[str, str], overlay_dir: str,
    row_info: Optional[Dict[str, Dict[str, float]]] = None, zones_js: Optional[List[Dict]] = None,
    image_zone: Optional[Dict[str, str]] = None, rotation_by_id: Optional[Dict[str, str]] = None,
    # ▼ 옵션
    ortho_tif_path: Optional[str] = None, use_ortho_tif: bool = False,
    summary: Optional[Dict[str, int]] = None,
    attention_count_th: int = 10,
    # (NEW) 스냅 포인트 GeoJSON 상대경로
    snapped_rel: str = "",
    show_snapped: bool = False,
):
    if not config.MAKE_MAP_HTML: return

    overlay_map = {}
    if df is not None and not df.empty:
        for image_id in df["image_id"].unique():
            ov = os.path.join(overlay_dir, f"{image_id}_overlay.jpg")
            if os.path.exists(ov): overlay_map[image_id] = ov

    points = []
    base_dir_for_rel = os.path.dirname(map_html_path)
    def relify(path):
        return os.path.relpath(path, start=base_dir_for_rel).replace("\\", "/") if path and os.path.exists(path) else ""

    for image_id, (lat, lon) in image_gps.items():
        if lat is None or lon is None: continue
        st = image_status.get(image_id, {"has_attention": False, "has_abnormal": False, "attention_count": 0})
        has_abn = bool(st.get("has_abnormal"))
        att_cnt = int(st.get("attention_count", 0))

        if has_abn:
            color = "red"
        elif config.MAP_INCLUDE_ATTENTION and (att_cnt >= attention_count_th):
            color = "orange"
        else:
            color = "white"

        info = row_info.get(image_id, {}) if row_info else {}
        row_id = int(info.get("row_id", 0))
        rot_class = (rotation_by_id or {}).get(image_id, "rot-0")
        ir_show  = overlay_map.get(image_id) or ""
        rgb_show = rgb_path_by_id.get(image_id, "")
        zone_name = image_zone.get(image_id, config.ZONE_UNASSIGNED_NAME) if image_zone else config.ZONE_UNASSIGNED_NAME
        points.append({
            "image_id": image_id, "lat": float(lat), "lon": float(lon),
            "color": color, "row_id": row_id, "rot": rot_class,
            "ir_rel":  relify(ir_show), "rgb_rel": relify(rgb_show), "zone": zone_name,
        })

    if points:
        min_lat = min(p["lat"] for p in points); max_lat = max(p["lat"] for p in points)
        min_lon = min(p["lon"] for p in points); max_lon = max(p["lon"] for p in points)
        center_lat = (min_lat + max_lat)/2.0; center_lon = (min_lon + max_lon)/2.0
    else:
        center_lat, center_lon = 36.5, 127.9

    ensure_dir(os.path.dirname(map_geojson_path))
    with open(map_geojson_path, 'w', encoding='utf-8') as f:
        json.dump({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"image_id": p["image_id"], "color": p["color"]},
                "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]}
            } for p in points]
        }, f, ensure_ascii=False)

    # (NEW) 스냅 포인트 레이어 스위치
    snapped_layer_script = ""
    if show_snapped and snapped_rel:
        snapped_layer_script = f"""
  try {{
    fetch("{snapped_rel}").then(r => r.json()).then(gj => {{
      const feats = (gj && gj.features) ? gj.features : [];
      feats.forEach(ft => {{
        const c = ft.geometry && ft.geometry.coordinates;
        if (!c || c.length < 2) return;
        const lon = c[0], lat = c[1];
        const p = ft.properties || {{}};
        let color = '#00c853'; // green for snapped
        if ((p.final||'').toLowerCase() === 'abnormal') color = 'red';
        else if ((p.final||'').toLowerCase() === 'attention') color = 'orange';
        const marker = L.circleMarker([lat, lon], {{
          radius: 6, color: color, weight: 2, fillColor: color, fillOpacity: 0.55
        }}).addTo(map);
        let html = `<b>Snapped</b>`;
        if (p.image_id) html += `<div>Frame: ${{p.image_id}} #${{p.module_id||'-'}}</div>`;
        if (p.snap_mid !== undefined) html += `<div>ModuleID: ${{p.snap_mid}}</div>`;
        if (p.delta_temp !== undefined && p.delta_temp !== null) html += `<div>ΔT: ${{Number(p.delta_temp).toFixed(1)}}°C</div>`;
        if (p.final) html += `<div>상태: <b>${{p.final}}</b></div>`;
        marker.bindPopup(html, {{maxWidth: 320}});
      }});
    }}).catch(e => console.warn('snap layer load error', e));
  }} catch(e) {{ console.warn('snap layer error', e); }}
"""
    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>PV Map (vWorld JS)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
html, body, #map {{ height:100%; margin:0; padding:0; }}
.leaflet-popup-content-wrapper {{ max-width: 360px; }}
.leaflet-popup-content {{ max-height: 65vh; overflow:auto; }}
.imgbox {{ width:300px; height:220px; display:flex; align-items:center; justify-content:center; overflow:hidden; background:#111; border:1px solid #333; border-radius:6px; margin:6px 0; }}
.img-rot {{ display:block; transform-origin:center center; max-width:none; max-height:none; }}
.rot-0 {{ width:100%; height:auto; transform:rotate(0deg); }}
.rot-90 {{ height:100%; width:auto; transform:rotate(90deg); }}
.rot--90 {{ height:100%; width:auto; transform:rotate(-90deg); }}
.legend {{ position:absolute; bottom:14px; left:14px; background:#fff; padding:8px 10px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,0.15); font:13px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
.legend .item {{ display:flex; align-items:center; gap:8px; margin:2px 0; }}
.legend .swatch {{ width:12px; height:12px; border-radius:50%; border:1px solid #222; }}
.swatch.white {{ background:#fff; }} .swatch.orange {{ background:orange; }} .swatch.red {{ background:red; }}
</style></head>
<body>
<div id="map"></div>
<div class="legend">
  <div class="item"><span class="swatch white"></span>정상/주의(기본)</div>
  <div class="item"><span class="swatch orange"></span>주의(이미지 내 주의 ≥ {attention_count_th})</div>
  <div class="item"><span class="swatch red"></span>이상</div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const vworldKey = {json.dumps(config.VWORLD_API_KEY)};
const tiles = L.tileLayer(
  `https://api.vworld.kr/req/wmts/1.0.0/${{vworldKey}}/Satellite/{{z}}/{{y}}/{{x}}.jpeg`,
  {{ attribution: "© vWorld/NGII", maxNativeZoom: 19, maxZoom: 22, tileSize: 256 }}
);
const map = L.map('map', {{ center: [{center_lat:.7f}, {center_lon:.7f}], zoom: 7, maxZoom: 22, preferCanvas: true }});
tiles.addTo(map);
const points = {json.dumps(points, ensure_ascii=False)};
if (points && points.length > 0) {{
  const latlngs = points.map(p => [p.lat, p.lon]);
  const bounds = L.latLngBounds(latlngs);
  map.fitBounds(bounds, {{ padding: [30, 30] }});
}}
(points || []).forEach(p => {{
  const stroke = (p.color === "white") ? "#222" : p.color;
  const marker = L.circleMarker([p.lat, p.lon], {{ radius:8, color:stroke, weight:2, fillColor:p.color, fillOpacity:0.5 }}).addTo(map);
  if (marker.bringToFront) marker.bringToFront();
  const rotClass = p.rot || "rot-0";
  let html = `<b>${{p.image_id}}</b>`;
  if (p.zone) {{ html += `<div><small>Zone: <b>${{p.zone}}</b></small></div>`; }}
  html += `<div><small>위치: ${{p.lat.toFixed(6)}}, ${{p.lon.toFixed(6)}}</small></div>`;
  if (p.ir_rel) {{
    const irName = p.ir_rel.split('/').pop();
    html += `<div style="margin-top:6px"><b>IR(Overlay)</b> — <a href="${{p.ir_rel}}" target="_blank">${{irName}}</a></div>`;
    html += `<div class="imgbox"><img class="img-rot ${{rotClass}}" src="${{p.ir_rel}}" alt="IR"></div>`;
  }}
  if (p.rgb_rel) {{
    const rgbName = p.rgb_rel.split('/').pop();
    html += `<div style="margin-top:4px"><b>RGB</b> — <a href="${{p.rgb_rel}}" target="_blank">${{rgbName}}</a></div>`;
    html += `<div class="imgbox"><img class="img-rot ${{rotClass}}" src="${{p.rgb_rel}}" alt="RGB"></div>`;
  }}
  marker.bindPopup(html, {{ maxWidth: 340 }});
}});
{snapped_layer_script}
</script></body></html>
"""
    with open(map_html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[지도(JS)] 저장 완료: {map_html_path}  (포인트 수: {len(points)})")


def build_results_dashboard_html(
    map_html_path: str,
    points: List[Dict],
    zones_js: Optional[List[Dict]],
    center_lat: float,
    center_lon: float,
    use_ortho_tif: bool,
    ortho_rel: str,
    attention_count_th: int,
    summary: Dict[str, int],
    summary_meta: Dict[str, str],  # {"shoot_date": "..."}
    # 기존: 디듑
    modules_dedup_rel: str = "",
    show_dedup: bool = False,
    # (NEW): 스냅 레이어
    modules_snapped_rel: str = "",
    show_snapped: bool = False,
):
    ensure_dir(os.path.dirname(map_html_path))
    # (NEW) 스냅 레이어 스크립트
    snapped_layer_script = ""
    if show_snapped and modules_snapped_rel:
        snapped_layer_script = f"""
  try {{
    fetch("{modules_snapped_rel}").then(r => r.json()).then(gj => {{
      const feats = (gj && gj.features) ? gj.features : [];
      feats.forEach(ft => {{
        const c = ft.geometry && ft.geometry.coordinates;
        if (!c || c.length < 2) return;
        const lon = c[0], lat = c[1];
        const p = ft.properties || {{}};
        let color = '#00c853';
        if ((p.final||'').toLowerCase() === 'abnormal') color = 'red';
        else if ((p.final||'').toLowerCase() === 'attention') color = 'orange';
        const marker = L.circleMarker([lat, lon], {{
          radius: 6, color: color, weight: 2, fillColor: color, fillOpacity: 0.6
        }}).addTo(map);
        let html = `<b>Snapped</b>`;
        if (p.image_id) html += `<div>Frame: ${{p.image_id}} #${{p.module_id||'-'}}</div>`;
        if (p.snap_mid !== undefined) html += `<div>ModuleID: ${{p.snap_mid}}</div>`;
        if (p.delta_temp !== undefined && p.delta_temp !== null) html += `<div>ΔT: ${{Number(p.delta_temp).toFixed(1)}}°C</div>`;
        if (p.final) html += `<div>상태: <b>${{p.final}}</b></div>`;
        marker.bindPopup(html, {{maxWidth: 320}});
      }});
    }}).catch(e => console.warn('snap layer load error', e));
  }} catch(e) {{ console.warn('snap layer error', e); }}
"""
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>PV 결과 대시보드</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  html, body {{ height:100%; margin:0; }}
  body {{ display:flex; flex-direction:column; }}
  header {{
    flex: 0 0 auto;
    background: #fff; border-bottom:1px solid #eee;
    padding: 12px 16px;
    font: 14px/1.5 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  }}
  .wrap {{ display:flex; gap:12px; flex-wrap:wrap; align-items:center; }}
  .title {{ font-size:16px; font-weight:600; margin-right:auto; }}
  .card {{
    background:#fafafa; border:1px solid #eee; border-radius:10px;
    padding:10px 12px; min-width:160px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  }}
  .card .k {{ color:#666; font-size:12px; }}
  .card .v {{ font-size:18px; font-weight:700; margin-top:2px; }}
  main {{ flex: 1 1 auto; min-height:0; }}
  #map {{ width:100%; height:100%; }}
  .leaflet-popup-content-wrapper {{ max-width: 360px; }}
  .leaflet-popup-content {{ max-height: 65vh; overflow:auto; }}
  .imgbox {{
    width: 320px; height: 240px; display:flex; align-items:center; justify-content:center;
    overflow:hidden; background:#111; border:1px solid #333; border-radius:6px; margin:6px 0;
  }}
  .img-rot {{ display:block; transform-origin:center center; max-width:none; max-height:none; }}
  .rot-0  {{ width: 100%; height: auto; transform: rotate(0deg);  }}
  .rot-90 {{ height: 100%; width: auto; transform: rotate(90deg);  }}
  .rot--90{{ height: 100%; width: auto; transform: rotate(-90deg); }}
  .legend {{
    position: absolute; bottom: 14px; left: 14px; background:#fff; padding:8px 10px; border-radius:8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.15); font: 13px/1.4 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
  }}
  .legend .item {{ display:flex; align-items:center; gap:8px; margin:2px 0; }}
  .legend .swatch {{ width:12px; height:12px; border-radius:50%; border:1px solid #222; }}
  .swatch.white {{ background:#fff; }}
  .swatch.orange {{ background:orange; }}
  .swatch.red {{ background:red; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="title">PV 결과 대시보드</div>
    <div class="card"><div class="k">촬영일자</div><div class="v" id="shootDate">-</div></div>
    <div class="card"><div class="k">입력 이미지 수(전체)</div><div class="v" id="sumInput">-</div></div>
    <div class="card"><div class="k">열화상 이미지 수</div><div class="v" id="sumThermal">-</div></div>
    <div class="card"><div class="k">RGB 이미지 수</div><div class="v" id="sumRGB">-</div></div>
    <div class="card"><div class="k">모듈 수(전체)</div><div class="v" id="sumModules">-</div></div>
    <div class="card"><div class="k">이상 모듈 수</div><div class="v" id="sumAbn">-</div></div>
    <div class="card"><div class="k">정상 모듈 수</div><div class="v" id="sumNor">-</div></div>
    <div class="card"><div class="k">주의 모듈 수</div><div class="v" id="sumAtt">-</div></div>
  </div>
</header>
<main>
  <div id="map"></div>
  <div class="legend">
    <div class="item"><span class="swatch white"></span>정상/주의(기본)</div>
    <div class="item"><span class="swatch orange"></span>주의(이미지 내 주의 ≥ {attention_count_th})</div>
    <div class="item"><span class="swatch red"></span>이상</div>
  </div>
</main>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/georaster@1.6.3/dist/georaster.browser.min.js"></script>
<script src="https://unpkg.com/georaster-layer-for-leaflet@3.10.0/dist/georaster-layer-for-leaflet.min.js"></script>

<script>
  const points   = {json.dumps(points, ensure_ascii=False)};
  const zones    = {json.dumps(zones_js or [], ensure_ascii=False)};
  const useOrtho = {str(bool(use_ortho_tif)).lower()};
  const orthoRel = {json.dumps(ortho_rel)};
  const summary  = {json.dumps(summary or {}, ensure_ascii=False)};
  const meta     = {json.dumps(summary_meta or {}, ensure_ascii=False)};
  const showDedup = {str(bool(show_dedup)).lower()};
  const modulesDedupRel = {json.dumps(modules_dedup_rel)};
  const showSnap = {str(bool(show_snapped)).lower()};
  const modulesSnapRel = {json.dumps(modules_snapped_rel)};

  const map = L.map('map', {{
    center: [{center_lat:.7f}, {center_lon:.7f}],
    zoom: 7, maxZoom: 22, preferCanvas: true
  }});
  const tiles = L.tileLayer(
    "https://api.vworld.kr/req/wmts/1.0.0/" + {json.dumps(config.VWORLD_API_KEY)} + "/Satellite/{{z}}/{{y}}/{{x}}.jpeg",
    {{ attribution:"© vWorld/NGII", maxNativeZoom:19, maxZoom:22, tileSize:256 }}
  ).addTo(map);

  // GeoTIFF 배경 (옵션)
  (async () => {{
    try {{
      if (useOrtho && orthoRel) {{
        const response = await fetch(orthoRel);
        const arrayBuffer = await response.arrayBuffer();
        const georaster = await parseGeoraster(arrayBuffer);
        const layer = new GeoRasterLayer({{ georaster, opacity: 0.95, resolution: 256 }});
        layer.addTo(map);
        try {{ map.fitBounds(layer.getBounds(), {{ padding:[30,30] }}); }} catch(e) {{}}
      }}
    }} catch(e) {{ console.warn("GeoTIFF 로드 실패:", e); }}
  }})();

  // Zone 폴리곤
  function lonlatRingsToLatlng(rings) {{ return rings.map(pt => [pt[1], pt[0]]); }}
  (zones || []).forEach(z => {{
    (z.coords || []).forEach(poly => {{
      const outer = lonlatRingsToLatlng(poly[0] || []);
      const holes = (poly.slice(1) || []).map(r => lonlatRingsToLatlng(r));
      if (outer.length >= 3) {{
        L.polygon([outer, ...holes], {{ color:"#1e90ff", weight:2, fillColor:"#1e90ff", fillOpacity:0.08 }})
        .bindTooltip(String(z.name)).addTo(map);
      }}
    }});
  }});

  // 프레임 포인트(열화상)
  (points || []).forEach(p => {{
    const stroke = (p.color === "white") ? "#222" : p.color;
    const marker = L.circleMarker([p.lat, p.lon], {{
      radius: 8, color: stroke, weight: 2, fillColor: p.color, fillOpacity: 0.5
    }}).addTo(map);
    if (marker.bringToFront) marker.bringToFront();
    const rotClass = p.rot || "rot-0";
    let html = `<b>${{p.image_id}}</b>`;
    if (p.zone) html += `<div><small>Zone: <b>${{p.zone}}</b></small></div>`;
    html += `<div><small>위치: ${{p.lat.toFixed(6)}}, ${{p.lon.toFixed(6)}}</small></div>`;
    if (p.ir_rel) {{
      const nm = p.ir_rel.split('/').pop();
      html += `<div style="margin-top:6px"><b>IR</b> — <a href="${{p.ir_rel}}" target="_blank">${{nm}}</a></div>`;
      html += `<div class="imgbox"><img class="img-rot ${{rotClass}}" src="${{p.ir_rel}}" alt="IR"></div>`;
    }}
    if (p.rgb_rel) {{
      const nm = p.rgb_rel.split('/').pop();
      html += `<div style="margin-top:4px"><b>RGB</b> — <a href="${{p.rgb_rel}}" target="_blank">${{nm}}</a></div>`;
      html += `<div class="imgbox"><img class="img-rot ${{rotClass}}" src="${{p.rgb_rel}}" alt="RGB"></div>`;
    }}
    marker.bindPopup(html, {{maxWidth: 360}});
  }});

  // 디듑 레이어
  try {{
    if (showDedup && modulesDedupRel) {{
      fetch(modulesDedupRel).then(r => r.json()).then(gj => {{
        const feats = (gj && gj.features) ? gj.features : [];
        feats.forEach(ft => {{
          const c = ft.geometry && ft.geometry.coordinates;
          if (!c || c.length < 2) return;
          const lon = c[0], lat = c[1];
          const p = ft.properties || {{}};
          let color = '#ffffff';
          if ((p.final||'').toLowerCase() === 'abnormal') color = 'red';
          else if ((p.final||'').toLowerCase() === 'attention') color = 'orange';
          const marker = L.circleMarker([lat, lon], {{
            radius: 6, color: color, weight: 2, fillColor: color, fillOpacity: 0.6
          }}).addTo(map);
          const cid = (p.cluster_id !== undefined && p.cluster_id !== null) ? p.cluster_id : '-';
          let html = `<b>Module# ${{cid}}</b>`;
          html += `<div>상태: <b>${{p.final || '-'}}</b></div>`;
          if (p.delta_temp !== undefined && p.delta_temp !== null) {{
            html += `<div>ΔT: ${{Number(p.delta_temp).toFixed(1)}}°C</div>`;
          }}
          if (p.image_id) html += `<div>대표 프레임: ${{p.image_id}}</div>`;
          marker.bindPopup(html, {{maxWidth: 300}});
        }});
      }}).catch(e => console.warn('dedup geojson load error', e));
    }}
  }} catch(e) {{ console.warn('dedup layer error', e); }}

  // (NEW) 스냅 레이어
  try {{
    if (showSnap && modulesSnapRel) {{
      fetch(modulesSnapRel).then(r => r.json()).then(gj => {{
        const feats = (gj && gj.features) ? gj.features : [];
        feats.forEach(ft => {{
          const c = ft.geometry && ft.geometry.coordinates;
          if (!c || c.length < 2) return;
          const lon = c[0], lat = c[1];
          const p = ft.properties || {{}};
          let color = '#00c853';
          if ((p.final||'').toLowerCase() === 'abnormal') color = 'red';
          else if ((p.final||'').toLowerCase() === 'attention') color = 'orange';
          const marker = L.circleMarker([lat, lon], {{
            radius: 6, color: color, weight: 2, fillColor: color, fillOpacity: 0.6
          }}).addTo(map);
          let html = `<b>Snapped</b>`;
          if (p.image_id) html += `<div>Frame: ${{p.image_id}} #${{p.module_id||'-'}}</div>`;
          if (p.snap_mid !== undefined) html += `<div>ModuleID: ${{p.snap_mid}}</div>`;
          if (p.delta_temp !== undefined && p.delta_temp !== null) html += `<div>ΔT: ${{Number(p.delta_temp).toFixed(1)}}°C</div>`;
          if (p.final) html += `<div>상태: <b>${{p.final}}</b></div>`;
          marker.bindPopup(html, {{maxWidth: 300}});
        }});
      }}).catch(e => console.warn('snap geojson load error', e));
    }}
  }} catch(e) {{ console.warn('snap layer error', e); }}

  // 상단 카드 채우기
  const get = (o,k,d='-') => (o && k in o) ? o[k] : d;
  document.getElementById('shootDate').textContent = get(meta,'shoot_date','-');
  document.getElementById('sumInput').textContent  = get(summary,'num_input_images','-');
  document.getElementById('sumThermal').textContent= get(summary,'num_thermal_images','-');
  document.getElementById('sumRGB').textContent    = get(summary,'num_rgb_images','-');
  document.getElementById('sumModules').textContent= get(summary,'num_modules_total','-');
  document.getElementById('sumAbn').textContent    = get(summary,'num_abnormal','-');
  document.getElementById('sumNor').textContent    = get(summary,'num_normal','-');
  document.getElementById('sumAtt').textContent    = get(summary,'num_attention','-');
</script>
</body>
</html>
"""
    with open(map_html_path, "w", encoding="utf-8") as f:
        f.write(html)

