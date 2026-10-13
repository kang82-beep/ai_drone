import fs from 'node:fs';
import {layout,SITE} from './data.js';
const out='results/shinan2_cables';
const slots=[];
function pair(column,row,slot,jb,upper){slots.push({column,row,slot,jb,upper,lower:upper-1});}
function block(column,startRow,slot,jb,n,reverse=false){for(let r=0;r<n;r++){const a=(n-r)*4;pair(column,startRow+r,slot,jb,reverse?a:a-2);pair(column,startRow+r,slot+2,jb,reverse?a-2:a);}}
// Each entry was visually transcribed from SA-E-11320/30/40 (PDF22/23/24).
pair(0,0,4,'A42',12);pair(0,0,6,'A42',10);
for(let p=0;p<4;p++)pair(0,1,p*2,'A42',8-p*2);
for(let r=0;r<2;r++)for(let p=0;p<4;p++)pair(0,2+r,p*2,'A41',16-r*8-p*2);
block(0,4,0,'A13',4);block(0,4,4,'A12',4,true);block(0,8,4,'A11',4);
pair(1,0,4,'A43',16);pair(1,0,6,'A43',14);pair(1,1,4,'A43',12);pair(1,1,6,'A43',10);
for(let r=0;r<2;r++){pair(1,2+r,0,'A42',18-r*4);pair(1,2+r,2,'A42',20-r*4);pair(1,2+r,4,'A43',8-r*4);pair(1,2+r,6,'A43',6-r*4);}
block(1,4,0,'A23',4);block(1,4,4,'A33',4,true);block(1,8,0,'A22',4);block(1,8,4,'A32',4,true);block(1,12,0,'A21',5);block(1,12,4,'A31',5,true);
block(0,12,4,'B11',4);block(0,16,4,'B12',4);block(0,20,4,'B13',5);block(0,25,4,'B41',3,true);
pair(0,28,6,'B42',12);for(let r=0;r<5;r++)pair(0,29+r,6,'B42',10-r*2);
block(1,17,0,'B21',4);block(1,17,4,'B31',4,true);block(1,21,0,'B22',4);block(1,21,4,'B32',4,true);block(1,25,0,'B23',5);block(1,25,4,'B33',5,true);
for(let p=0;p<4;p++)pair(1,30,p*2,'B43',10+p*2);
pair(1,31,0,'B41',18);pair(1,31,2,'B41',20);pair(1,31,4,'B43',6);pair(1,31,6,'B43',8);
pair(1,32,0,'B41',14);pair(1,32,2,'B41',16);pair(1,32,4,'B43',2);pair(1,32,6,'B43',4);
block(1,33,0,'C41',5);block(1,33,4,'C31',5,true);block(1,38,0,'C42',4);block(1,38,4,'C32',4,true);block(1,42,0,'C43',4);block(1,42,4,'C33',4,true);
for(let p=0;p<4;p++)pair(1,46,p*2,'C23',2+p*2);
for(let r=0;r<2;r++)for(let p=0;p<4;p++)pair(2,37+r,p*2,'C11',20-r*8-p*2);
pair(2,39,0,'C21',18);pair(2,39,2,'C21',20);pair(2,39,4,'C11',4);pair(2,39,6,'C11',2);
block(2,40,0,'C21',4);block(2,40,4,'C12',4,true);block(2,44,0,'C22',4);block(2,44,4,'C13',4,true);
pair(2,48,0,'C23',14);pair(2,48,2,'C23',16);pair(2,49,0,'C23',10);pair(2,49,2,'C23',12);
fs.writeFileSync(out+'/abc_string_slots.json',JSON.stringify(slots,null,2));
if(fs.existsSync(out+'/de_string_slots.json')){const de=JSON.parse(fs.readFileSync(out+'/de_string_slots.json'));slots.push(...(Array.isArray(de)?de:de.slots).map(s=>({...s,jb:s.jb.replace(/^JB-/,''),upper:Number(String(s.upper).slice(-2)),lower:Number(String(s.lower).slice(-2))})));}
const bySlot=new Map(),columnRows=[];
for(let c=0;c<4;c++){const zs=[...new Set(layout.filter(g=>g.column===c).map(g=>g.z))].sort((a,b)=>a-b);columnRows.push(zs);for(const g of layout.filter(g=>g.column===c)){const row=zs.indexOf(g.z),slot=Math.round((g.x-SITE.columns[c]-SITE.groupWidth/2)/SITE.groupPitch);bySlot.set(`${c}/${row}/${slot}`,g);}}
const strings=[],used=new Set();
function addString(record,num,physicalRow,special=false){const groups=special?[bySlot.get(`${record.column}/${record.row}/${record.slot}`)]:[bySlot.get(`${record.column}/${record.row}/${record.slot}`),bySlot.get(`${record.column}/${record.row}/${record.slot+1}`)];if(groups.some(g=>!g))throw Error('Missing group '+JSON.stringify(record));const mods=[];for(let i=0;i<20;i++){const g=special?groups[0]:groups[Math.floor(i/10)];const r=special?(i<10?0:1):physicalRow;const m=special&&i>=10?19-i:i%10;const index=(g.number-1)*20+r*10+m;if(used.has(index))throw Error('Duplicate module '+index);used.add(index);mods.push(index);}
strings.push({id:`SM-${record.jb}${String(num).padStart(2,'0')}`,jb:'JB-'+record.jb,inverter:record.jb[0],page:22+'ABCDE'.indexOf(record.jb[0]),column:record.column,row:record.row,slot:record.slot,moduleIndices:mods,topology:special?'10+10 U return':'20 horizontal in series',sourceStatus:'drawing_transcribed',physicalSerials:'not supplied'});}
for(const s of slots){addString(s,s.upper,0);addString(s,s.lower,1);}
addString({column:0,row:28,slot:5,jb:'B42'},13,0,true);
const counts={};for(const s of strings)counts[s.inverter]=(counts[s.inverter]||0)+1;
const ids=new Set(strings.map(s=>s.id));if(ids.size!==strings.length)throw Error('Duplicate string IDs');
const schedule=JSON.parse(fs.readFileSync(out+'/source_connections.json')).junction_box_schedule;
for(const j of schedule){const actual=strings.filter(s=>s.jb===j.jb).length;if(actual!==j.parallel_strings)throw Error(j.jb+' schedule mismatch '+actual+' / '+j.parallel_strings);}
const complete=strings.length===1021&&used.size===20420&&Object.entries(SITE.inverterStrings).every(([k,n])=>counts[k]===n);
const report={strings:strings.length,modules:used.size,counts,complete,missingModules:20420-used.size,method:'Manual visual transcription of PDF22–26 registered to PDF14 row geometry. Individual serial numbers not supplied.',special:'SM-B4213: 2x10 U-return per PDF21',polarity:'P/N terminal labels preserved; PDF21 note reverses usual P/N polarity naming, so +/- is not inferred.'};
fs.writeFileSync(out+'/circuit_map.json',JSON.stringify({report,strings},null,2));
console.log(JSON.stringify(report));
