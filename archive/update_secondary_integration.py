from pathlib import Path
p=Path('shinan2_viewer/cables.js')
s=p.read_text(encoding='utf-8')
s=s.replace("import circuitData", "import {addSurveillance,addGridManholes,addSecondaryCircuits} from './secondary_cables.js';\nimport circuitData",1)
s=s.replace("const groups={strings:","const groups={cctv:new THREE.Group(),lighting:new THREE.Group(),ground:new THREE.Group(),lightning:new THREE.Group(),strings:",1)
s=s.replace("kind==='PV_series'?'strings':", "kind==='cctv'?'cctv':kind==='lightning'?'lightning':kind.includes('earth')?'ground':kind.includes('lighting')||kind==='outlet'||kind==='panel_membership'?'lighting':kind==='PV_series'?'strings':",1)
s=s.replace("  for(const [id,b] of batches)","  const secondary=addSecondaryCircuits({node,link,nodes,groups,wp});\n  const surveillance=addSurveillance({node,link,nodes,groups,wp});\n  const grid=addGridManholes({edges,link,node});\n  for(const [id,b] of batches)",1)
s=s.replace("const titles={strings:","const titles={lighting:'조명·전열',ground:'접지',lightning:'피뢰',cctv:'CCTV',strings:",1)
start=s.index('  function trace(id)')
end=s.index('  function clearSelected()',start)
s=s[:start]+'''  function trace(id,system='main'){
    const result=[],seen=new Set();
    const allowed=e=>system==='ground'?e.kind.includes('earth'):system==='lightning'?e.kind==='lightning':system==='cctv'?e.kind==='cctv':system==='secondary'?e.secondary&&!e.kind.includes('earth')&&e.kind!=='lightning':!e.secondary&&e.kind!=='cctv'&&e.kind!=='communication'&&!e.kind.includes('aux')&&!e.kind.includes('service')&&!e.kind.includes('measurement')&&!e.kind.includes('rectifier');
    function visit(n){if(seen.has(n))return;seen.add(n);for(const e of edges.filter(e=>allowed(e)&&(e.source===n||(system==='ground'&&e.target===n)))){if(!result.includes(e))result.push(e);visit(e.source===n?e.target:e.source);}}
    visit(id);return result;
  }
''' +s[end:]
s=s.replace("function select(id,focus=false){", "function select(id,focus=false,system=null){",1)
s=s.replace("const path=trace(id),branch=", "const selectedSystem=system||(/^ETT-|^ER[12]-E|^ARRAY-.*EARTH|^ARRAY-.*GROUND/.test(id)?'ground':/^LIGHTNING-/.test(id)?'lightning':/CAMERA-|VIDEO-SERVER|KT-MODEM|NETWORK-ROUTER|HUB-24PORT/.test(id)?'cctv':/L-E[12]|ROOM[12]-LIGHT|ROOM[12]-OUTLET/.test(id)?'secondary':'main');const path=trace(id,selectedSystem),branch=",1)
s=s.replace("${chain.join(' → ')}", "${path.length?path.map(e=>e.source+' → '+e.target).join('<br>'):id+' · 연결 경로 미확인'}",1)
s=s.replace("    if(jb){const aux=", "    const modes=document.createElement('div');for(const [mode,title] of [['main','주전력'],['ground','접지'],['secondary','조명·보조'],['cctv','CCTV'],['lightning','피뢰']]){const b=document.createElement('button');b.textContent=title;b.onclick=()=>select(id,false,mode);modes.append(b);}card.insertBefore(modes,card.querySelector('.wirepath'));\n    if(path.some(e=>!e.points)){const note=document.createElement('p');note.className='wirefoot';note.textContent='일부 연결은 도면 회로표로만 표시합니다. 위치가 확인되지 않은 경로는 3D 선을 만들지 않았습니다.';card.append(note);}\n    if(jb){const aux=",1)
s=s.replace("routeData,get current", "routeData,secondary,surveillance,grid,get current",1)
s=s.replace("counts:circuitData.report.counts", "counts:circuitData.report.counts,secondary,surveillance,grid",1)
# A second picker makes non-JB circuits discoverable without memorizing IDs.
anchor="  const card=document.createElement('div');"
picker="""  const secondaryPicker=document.createElement('select');secondaryPicker.id='secondary-select';secondaryPicker.innerHTML='<option value="">조명·접지·CCTV·피뢰 선택</option>'+[...nodes.keys()].filter(id=>/^L-E[12]$|^ETT-|^CAMERA-|^LIGHTNING-ROD-|^MH/.test(id)).map(id=>'<option>'+id+'</option>').join('');secondaryPicker.onchange=e=>{if(e.target.value)select(e.target.value,true);};section.append(secondaryPicker);
"""
s=s.replace(anchor,picker+anchor,1)
p.write_text(s,encoding='utf-8')
