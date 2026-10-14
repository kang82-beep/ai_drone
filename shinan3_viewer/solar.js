// NOAA fractional-year approximation. Azimuth: clockwise from true north.
// https://gml.noaa.gov/grad/solcalc/solareqns.PDF
const RAD=Math.PI/180,DEG=180/Math.PI;
export const DEFAULT_SITE={latitude:34.774478824204735,longitude:126.15865191106542,northBearing:0};
export function solarPosition(date,minutes,latitude,longitude){
  const midnight=Date.parse(date+'T00:00:00Z'),year=new Date(midnight).getUTCFullYear();
  if(!Number.isFinite(midnight)||!Number.isFinite(minutes)||!Number.isFinite(latitude)||!Number.isFinite(longitude)||Math.abs(latitude)>90||Math.abs(longitude)>180)throw Error('Invalid solar inputs');
  const days=(Date.UTC(year+1,0,1)-Date.UTC(year,0,1))/86400000,day=(midnight-Date.UTC(year,0,1))/86400000+1;
  const gamma=2*Math.PI/days*(day-1+(minutes/60-12)/24);
  const equation=229.18*(.000075+.001868*Math.cos(gamma)-.032077*Math.sin(gamma)-.014615*Math.cos(2*gamma)-.040849*Math.sin(2*gamma));
  const decl=.006918-.399912*Math.cos(gamma)+.070257*Math.sin(gamma)-.006758*Math.cos(2*gamma)+.000907*Math.sin(2*gamma)-.002697*Math.cos(3*gamma)+.00148*Math.sin(3*gamma);
  const hourAngle=(minutes+equation+4*longitude-540)/4-180,ha=hourAngle*RAD,lat=latitude*RAD;
  const elevation=Math.asin(Math.max(-1,Math.min(1,Math.sin(lat)*Math.sin(decl)+Math.cos(lat)*Math.cos(decl)*Math.cos(ha))))*DEG;
  const azimuth=((Math.atan2(Math.sin(ha),Math.cos(ha)*Math.sin(lat)-Math.tan(decl)*Math.cos(lat))*DEG+180)%360+360)%360;
  return {elevation,azimuth,equation,declination:decl*DEG,hourAngle};
}
export function solarDay(date,latitude,longitude){
  const f=m=>solarPosition(date,m,latitude,longitude).elevation+.833;
  let sunrise=null,sunset=null;
  for(let m=10;m<=1440;m+=10){const a=f(m-10),b=f(m);if((a<0&&b>=0)||(a>=0&&b<0)){let lo=m-10,hi=m;for(let i=0;i<24;i++){const mid=(lo+hi)/2;if((f(mid)>=0)===(a>=0))lo=mid;else hi=mid;}if(a<0)sunrise=(lo+hi)/2;else sunset=(lo+hi)/2;}}
  let noon=720-4*longitude+540;for(let i=0;i<4;i++)noon=720-4*longitude+540-solarPosition(date,noon,latitude,longitude).equation;
  return {sunrise,sunset,noon:Math.max(0,Math.min(1440,noon)),polar:sunrise===null&&sunset===null?(f(720)>0?'day':'night'):null};
}
export function sunDirection(elevation,azimuth,northBearing=0){const e=elevation*RAD,a=(azimuth-northBearing)*RAD;return [Math.sin(a)*Math.cos(e),Math.sin(e),-Math.cos(a)*Math.cos(e)];}
export function clockText(minutes){if(minutes===null)return '없음';const n=Math.max(0,Math.min(1439,Math.round(minutes)));return String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0');}

export function createSolarControls(onChange){
  const $=id=>document.getElementById(id),today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  let settings={...DEFAULT_SITE,date:today,minutes:720},events,playing=false,accum=0;
  try{const old=JSON.parse(localStorage.getItem('shinan3-solar-v1'));if(old&&valid(old))settings=old;}catch{}
  function valid(s){return /^\d{4}-\d{2}-\d{2}$/.test(s.date)&&Number.isFinite(Date.parse(s.date))&&s.date>='2000-01-01'&&s.date<='2100-12-31'&&Number.isFinite(s.latitude)&&Math.abs(s.latitude)<=89&&Number.isFinite(s.longitude)&&Math.abs(s.longitude)<=180&&Number.isFinite(s.northBearing)&&Math.abs(s.northBearing)<=180&&Number.isFinite(s.minutes);}
  function save(){try{localStorage.setItem('shinan3-solar-v1',JSON.stringify(settings));}catch{}}
  function publish(){const p=solarPosition(settings.date,settings.minutes,settings.latitude,settings.longitude);$('sun').value=settings.minutes;$('sunlabel').value=clockText(settings.minutes);$('solar-time').value=clockText(settings.minutes);$('solar-position').textContent=`방위각 ${p.azimuth.toFixed(1)}° · 고도 ${p.elevation.toFixed(1)}°`;$('solar-status').textContent=p.elevation<=0?'태양 중심이 지평선 아래입니다. 직사 그림자는 표시하지 않습니다.':p.elevation<5?'낮은 태양: 긴 그림자의 끝은 화면·그림자 표시 범위에서 잘릴 수 있습니다.':'맑은 날의 직사광 기준 · 구름 및 실측 지형 차폐 미반영';onChange({...p,...settings,direction:sunDirection(p.elevation,p.azimuth,settings.northBearing)});}
  function stop(){playing=false;$('solar-play').textContent='▶ 하루 재생';$('solar-play').setAttribute('aria-pressed','false');}
  function refresh(){events=solarDay(settings.date,settings.latitude,settings.longitude);const continuous=events.sunrise!==null&&events.sunset!==null&&events.sunrise<events.sunset;$('sun').min=continuous?Math.floor(events.sunrise):0;$('sun').max=continuous?Math.ceil(events.sunset):1439;settings.minutes=Math.max(Number($('sun').min),Math.min(Number($('sun').max),settings.minutes));for(const key of ['sunrise','noon','sunset']){$('solar-'+key).textContent=({sunrise:'일출',noon:'남중',sunset:'일몰'})[key]+' '+clockText(events[key]);$('solar-'+key).disabled=events[key]===null;}publish();save();}
  function sync(){for(const [id,key] of [['solar-date','date'],['solar-lat','latitude'],['solar-lon','longitude'],['solar-north','northBearing']])$(id).value=['latitude','longitude'].includes(key)?settings[key].toFixed(6):settings[key];}
  $('solar-settings').onclick=()=>{$('solar-panel').hidden=!$('solar-panel').hidden;$('solar-settings').setAttribute('aria-expanded',String(!$('solar-panel').hidden));};
  $('solar-close').onclick=()=>{$('solar-panel').hidden=true;$('solar-settings').setAttribute('aria-expanded','false');};
  $('solar-form').onsubmit=e=>{e.preventDefault();const next={...settings,date:$('solar-date').value,latitude:Number($('solar-lat').value),longitude:Number($('solar-lon').value),northBearing:Number($('solar-north').value)};if(!valid(next)){$('solar-error').textContent='날짜·위도·경도의 입력 범위를 확인하세요.';return;}$('solar-error').textContent='';stop();settings=next;refresh();};
  $('sun').oninput=e=>{stop();settings.minutes=Number(e.target.value);publish();};$('sun').onchange=save;
  $('solar-time').onchange=e=>{const match=/^(\d{2}):(\d{2})$/.exec(e.target.value);if(!match)return;stop();settings.minutes=Number(match[1])*60+Number(match[2]);settings.minutes=Math.max(Number($('sun').min),Math.min(Number($('sun').max),settings.minutes));publish();save();};
  for(const key of ['sunrise','noon','sunset'])$('solar-'+key).onclick=()=>{stop();settings.minutes=events[key];publish();save();};
  $('solar-reset').onclick=()=>{stop();settings={...DEFAULT_SITE,date:today,minutes:720};sync();refresh();};
  $('solar-play').onclick=()=>{if(playing){stop();save();return;}if(settings.minutes>=Number($('sun').max)-1)settings.minutes=Number($('sun').min);playing=true;$('solar-play').textContent='Ⅱ 일시 정지';$('solar-play').setAttribute('aria-pressed','true');};
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});sync();refresh();
  // Used by console_link.js to show the sun of a capture time; minutes are KST like the slider.
  function setTime(date,minutes){const next={...settings,date,minutes};if(!valid(next))return false;stop();settings=next;sync();refresh();return true;}
  return {setTime,tick(dt){if(!playing)return;accum+=dt;if(accum<.12)return;settings.minutes=Math.min(Number($('sun').max),settings.minutes+accum*(Number($('sun').max)-Number($('sun').min))/60);accum=0;publish();if(settings.minutes>=Number($('sun').max)){stop();save();}},inspect:()=>({...settings,...events,playing,...solarPosition(settings.date,settings.minutes,settings.latitude,settings.longitude)})};
}
