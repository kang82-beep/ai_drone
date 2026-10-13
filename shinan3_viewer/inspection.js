// Local files only. Imported analysis is evidence, never a field-confirmed ID.
export function createInspection({modules,sourceHash,selectID}){
  let records=[],selectedID=null,urls=[],index=new Map();
  const root=document.createElement('div');root.id='inspection-controls';
  root.style.cssText='position:fixed;right:18px;top:85px;z-index:25';
  const open=document.createElement('button');open.textContent='열화상 점검 결과';root.append(open);document.body.append(root);
  const dialog=document.createElement('dialog');dialog.style.cssText='width:min(850px,90vw);max-height:85vh;overflow:auto;background:#142735;color:#edf4f5;border:1px solid #71939c;padding:24px';document.body.append(dialog);
  const title=document.createElement('h2');title.textContent='열화상·RGB 점검 결과';dialog.append(title);
  const close=document.createElement('button');close.textContent='닫기';close.onclick=()=>dialog.close();dialog.append(close);
  const note=document.createElement('p');note.textContent='결과 폴더를 선택하세요. 주황색 연결 후보는 현장 확인 전입니다. 결과 없음은 정상 판정이 아닙니다.';dialog.append(note);
  const input=document.createElement('input');input.type='file';input.multiple=true;input.setAttribute('webkitdirectory','');dialog.append(input);
  const status=document.createElement('p');status.setAttribute('role','status');dialog.append(status);
  const select=document.createElement('select');select.style.maxWidth='100%';dialog.append(select);
  const body=document.createElement('div');dialog.append(body);
  const text=(tag,value,parent=body)=>{const el=document.createElement(tag);el.textContent=value;parent.append(el);return el;};
  const validIDs=new Set(modules.map(m=>m.id));
  let assets=new Map();
  function render(){
    body.replaceChildren();
    const filtered=selectedID?records.filter(r=>r.drawing_module_id===selectedID||r.candidates?.some(c=>c.id===selectedID)):records;
    text('h3',selectedID||'전체 관측');
    text('p',filtered.length?`${filtered.length}개 관측 · 자동 확정 없음`:'점검 결과 없음 또는 위치 미연결');
    for(const r of filtered.slice(0,100)){
      const box=text('section','');box.style.cssText='border-top:1px solid #57717d;padding:12px 0';
      text('h4',`${r.observation_id} · ${r.drawing_module_id||'ID 미연결'}`,box);
      const decisions={normal:'정상',attention:'주의',abnormal:'이상',unknown:'판정 없음'};
      text('p',`모델 판정: ${decisions[r.decision]||r.decision} / ${r.link_status==='candidate'?'위치 연결 후보':'위치 판별 보류'}`,box);
      text('p',`최고 ${r.temperature?.max_temp??'미확인'} °C · 평균 ${r.temperature?.mean_temp??'미확인'} °C · ΔT ${r.temperature?.delta_temp??'미확인'} °C (동일 모듈 최고−평균)`,box);
      text('small',`위치 근거: ${r.geo_status||'미확인'} · ${r.reason||''}`,box);
      for(const candidate of r.candidates||[]){const button=text('button',`${candidate.id} (${Number(candidate.distance_m).toFixed(2)}m)`,box);button.onclick=()=>{dialog.close();selectID(candidate.id);};}
      for(const [kind,path] of Object.entries(r.images||{})){
        const file=assets.get(path);if(!file)continue;
        const figure=text('figure','',box);figure.style.display='inline-block';figure.style.margin='10px';
        text('figcaption',({thermal:'원본 열화상',rgb:'동일 촬영 RGB (픽셀 정합 전)',crop:'검출 모듈 크롭'})[kind]||kind,figure);
        const url=URL.createObjectURL(file);urls.push(url);const img=document.createElement('img');img.src=url;img.style.cssText='max-width:330px;max-height:260px;object-fit:contain';figure.append(img);
      }
    }
    if(filtered.length>100)text('p','최대 100개 표시합니다. 모듈을 선택하여 범위를 좁히세요.');
  }
  function show(id){selectedID=id;for(const url of urls)URL.revokeObjectURL(url);urls=[];render();}
  open.onclick=()=>{show(selectedID);dialog.showModal();};
  select.onchange=()=>show(select.value||null);
  input.onchange=async()=>{
    try{
      const files=[...input.files],jsons=files.filter(f=>f.name==='inspection_results.json');
      if(jsons.length!==1)throw Error('inspection_results.json이 하나 포함된 내보내기 폴더를 선택하세요.');
      const data=JSON.parse(await jsons[0].text());
      if(data.schema!=='pv-inspector-threejs-v1'||data.site_id!=='shinan3'||data.layout_source_sha256!==sourceHash)throw Error('신안3호기 도면과 일치하지 않는 결과입니다.');
      if(!Array.isArray(data.records)||data.records.length>200000)throw Error('관측 목록 형식 또는 크기가 유효하지 않습니다.');
      const seen=new Set();
      for(const r of data.records){
        if(typeof r.observation_id!=='string'||seen.has(r.observation_id))throw Error('관측 ID가 없거나 중복됩니다.');seen.add(r.observation_id);
        if(!['candidate','unmatched'].includes(r.link_status))throw Error('지원하지 않는 연결 상태입니다.');
        if(r.drawing_module_id&&!validIDs.has(r.drawing_module_id))throw Error('모형에 없는 모듈 ID입니다.');
        if(!Array.isArray(r.candidates)||r.candidates.some(c=>!validIDs.has(c.id)||!Number.isFinite(c.distance_m)))throw Error('연결 후보 목록이 유효하지 않습니다.');
      }
      const prefix=jsons[0].webkitRelativePath.slice(0,-jsons[0].name.length);
      assets=new Map(files.filter(f=>f.webkitRelativePath.startsWith(prefix)&&/\.(jpe?g|png|webp)$/i.test(f.name)).map(f=>[f.webkitRelativePath.slice(prefix.length),f]));
      records=data.records;index=new Map();for(const r of records)if(r.drawing_module_id)index.set(r.drawing_module_id,true);
      select.replaceChildren();const all=document.createElement('option');all.value='';all.textContent='전체 관측 / 미연결 포함';select.append(all);
      for(const id of [...index.keys()].sort()){const option=document.createElement('option');option.value=id;option.textContent=id+' · 후보';select.append(option);}
      status.textContent=`${records.length}개 관측 · 후보 연결 모듈 ${index.size}개 · 기준점 상태: ${data.registration?.status||'미확인'}`;show(null);
    }catch(error){status.textContent='불러오기 실패: '+error.message;}
  };
  return {selectModule(id){show(id);open.textContent=index.has(id)?'열화상 점검 결과 · 연결 후보':'열화상 점검 결과 · 조회';},inspect:()=>({observations:records.length,candidateModules:index.size,confirmed:0})};
}
