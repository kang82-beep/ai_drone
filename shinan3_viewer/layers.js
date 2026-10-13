// Visibility controls share the actual render objects; no duplicate model data.
export function createLayers(entries,onChange){
  const host=document.getElementById('layer-list');
  let isolated=null,previous=null;
  const state=()=>Object.fromEntries(entries.map(e=>[e.id,e.objects.every(o=>o.visible)]));
  const apply=values=>{for(const e of entries)for(const o of e.objects)o.visible=values[e.id]!==false;sync();onChange();};
  function sync(){
    const values=state();
    for(const e of entries){e.input.checked=values[e.id];e.solo.setAttribute('aria-pressed',String(isolated===e.id));e.solo.textContent=isolated===e.id?'돌아가기':'단독';}
    document.getElementById('layer-count').textContent=`${Object.values(values).filter(Boolean).length} / ${entries.length}`;
  }
  function set(id,visible){if(!entries.some(e=>e.id===id))return;isolated=null;previous=null;apply({...state(),[id]:visible});}
  function all(){isolated=null;previous=null;apply(Object.fromEntries(entries.map(e=>[e.id,true])));}
  function solo(id){
    if(!entries.some(e=>e.id===id))return;
    if(isolated===id){const restore=previous;isolated=null;previous=null;apply(restore);return;}
    if(!isolated)previous=state();isolated=id;
    apply(Object.fromEntries(entries.map(e=>[e.id,e.id===id])));
  }
  function setMany(ids,visible){isolated=null;previous=null;apply({...state(),...Object.fromEntries(ids.map(id=>[id,visible]))});}
  let section='';
  for(const e of entries){
    if(e.section!==section){section=e.section;const h=document.createElement('h3');h.textContent=section;host.append(h);}
    const row=document.createElement('div');row.className='layer-row';
    const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.dataset.layer=e.id;input.checked=true;input.onchange=()=>set(e.id,input.checked);
    label.append(input,document.createTextNode(e.label));
    const button=document.createElement('button');button.type='button';button.dataset.solo=e.id;button.setAttribute('aria-label',e.label+' 단독 보기 또는 복원');button.onclick=()=>solo(e.id);
    row.append(label,button);host.append(row);e.input=input;e.solo=button;
  }
  document.getElementById('layers-all').onclick=all;
  const panel=document.getElementById('layer-panel'),toggle=document.getElementById('layers-toggle');
  function open(value){panel.hidden=!value;toggle.setAttribute('aria-expanded',String(value));if(value){const cables=document.getElementById('cable-panel');if(cables)cables.hidden=true;document.getElementById('cables-toggle')?.setAttribute('aria-expanded','false');document.getElementById('layers-close').focus();}else toggle.focus();}
  toggle.onclick=()=>open(panel.hidden);document.getElementById('layers-close').onclick=()=>open(false);
  panel.addEventListener('keydown',e=>{if(e.key==='Escape'){e.stopPropagation();open(false);}});
  sync();
  return {state,set,solo,all,setMany,inspect:()=>entries.map(e=>({id:e.id,visible:e.objects.every(o=>o.visible),objects:e.objects.length}))};
}
