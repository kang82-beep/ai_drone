from pathlib import Path
p=Path(__file__).resolve().parent/'shinan2_viewer/cables.js'
s=p.read_text(encoding='utf-8')
s=s.replace("'+str.topology+'</p>'", "+(str.topology==='10+10 U return'?'10+10장 U자 연결':'가로 20장 직렬')+'</p>'") if False else s
old="document.getElementById('wire-close').onclick=()=>{card.hidden=true;clearSelected();current=null;};return true;}"
new="""document.getElementById('wire-close').onclick=()=>{card.hidden=true;clearSelected();current=null;};
    if(jb){const aux=edges.find(e=>e.target===jb.jb&&e.kind==='aux_load_membership');const communication=edges.filter(e=>e.kind==='communication'&&(e.source===jb.jb||e.target===jb.jb));const details=document.createElement('details');details.innerHTML='<summary>보조전원·통신 연결</summary>'+(aux?'<p>보조전원 회로 소속: P-'+jb.jb[3]+' → '+aux.source+'<br><small>개별 케이블 순서는 미확정'+(aux.conflict?' · 원도면 E4 명칭 불일치':'')+'</small></p>':'')+'<p>'+communication.map(e=>e.source+' ↔ '+e.target).join('<br>')+'</p><a href="../References/Shinan2_Electrical_Drawings.pdf#page=13" target="_blank">보조전원 p13</a> · <a href="../References/Shinan2_Electrical_Drawings.pdf#page=64" target="_blank">통신 p64</a>';card.insertBefore(details,card.lastElementChild);}
    return true;}"""
if old in s:s=s.replace(old,new)
s=s.replace("'+str.topology+'</p>'", "+(str.topology==='10+10 U return'?'10+10장 U자 연결':'가로 20장 직렬')+'</p>'") if False else s
# Replace just the expression inside the existing template-safe concatenation.
s=s.replace("+str.topology+", "+(str.topology==='10+10 U return'?'10+10장 U자 연결':'가로 20장 직렬')+")
p.write_text(s,encoding='utf-8')
