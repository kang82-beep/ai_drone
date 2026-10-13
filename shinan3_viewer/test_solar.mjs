import assert from 'node:assert/strict';
import fs from 'node:fs';
import {solarPosition,solarDay,sunDirection,DEFAULT_SITE} from './solar.js';
const {latitude:lat,longitude:lon}=DEFAULT_SITE;
const days=['2026-03-20','2026-06-21','2026-09-23','2026-12-21','2028-02-29'].map(date=>{
  const day=solarDay(date,lat,lon);assert(day.sunrise>240&&day.sunrise<500);assert(day.sunset>1000&&day.sunset<1250);
  assert(day.sunrise<day.noon&&day.noon<day.sunset);
  for(const m of [day.sunrise,day.sunset])assert(Math.abs(solarPosition(date,m,lat,lon).elevation+.833)<.00001);
  const noon=solarPosition(date,day.noon,lat,lon);assert(Math.abs(noon.azimuth-180)<.01);
  assert(solarPosition(date,day.sunrise+60,lat,lon).azimuth<180);assert(solarPosition(date,day.sunset-60,lat,lon).azimuth>180);
  return {date,...day,noonElevation:noon.elevation};
});
assert(days[1].sunset-days[1].sunrise>days[3].sunset-days[3].sunrise);
assert(days[1].noonElevation>days[3].noonElevation+40);
assert(sunDirection(30,90)[0]>.8);assert(sunDirection(30,270)[0]<-.8);assert(sunDirection(30,180)[2]>.8);
assert(Math.abs(sunDirection(30,90,90)[0])<1e-10);assert(sunDirection(30,90,90)[2]<-.8);
assert.equal(solarDay('2026-06-21',89,126).polar,'day');assert.equal(solarDay('2026-12-21',89,126).polar,'night');
// NREL SPA published example: 2003-10-17 12:30:30 UTC-7 = Oct 18 04:30:30 KST.
// NOAA's low-order approximation is deliberately not claimed to have SPA accuracy.
const ref=solarPosition('2003-10-18',270.5,39.742476,-105.1786);
assert(Math.abs(ref.azimuth-194.34024)<1);assert(Math.abs(ref.elevation-(90-50.11162))<1);
const result={passed:true,days,reference:{computed:ref,azimuth:194.34024,elevation:39.88838,toleranceDegrees:1},convention:'KST UTC+9; clockwise true-north azimuth; Three +X east, -Z model north'};
fs.writeFileSync(new URL('../results/shinan3_review/solar_math_validation.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
