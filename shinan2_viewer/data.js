// Source: C:\3d\신안군 태양광 발전단지 2차 (5MW) 조성공사.pdf, pages 10–14.
// Scan-derived placement, not surveyed/CAD coordinates. +X east, -Z north; metres.
export const SITE = Object.freeze({
  name: '신안2호기', latitude: 34.7947649798, longitude: 126.1279209376,
  latitudeDeg: 34.7947649798, longitudeDeg: 126.1279209376,
  timezone: 9, moduleCount: 20420, groupCount: 1021, capacityKW: 5002.9,
  modulePowerW: 245, moduleWidth: 1.001, moduleLength: 1.675,
  moduleThickness: 0.034, moduleGap: 0.025, tilt: 22, tiltDeg: 22,
  groupWidth: 10.235, groupDepth: 3.10606751, groupPitch: 10.335,
  rowPitch: 5.37002, columns: [0, 86.58, 175.16, 261.74],
  coordinateStatus: '도면 스캔 기반 근사 배치. 실측·CAD 좌표 미검증.',
  idStatus: '뷰어 형상 ID. 실물 모듈·전기회로 ID와 미대조.',
  sourcePages: [10,11,12,14],
  inverterStrings: { A:204, B:205, C:208, D:208, E:196 },
  ortho: { west:237032.38919458748, east:237420.9071945875,
    south:3853881.189086972, north:3854206.3854869716,
    originE:237057.3, originN:3853897.5, crs:'EPSG:32652', alignment:'approximate' }
});

// Drawing raster coordinates refer to a 1863 × 1312 reference preview.
export const sections = [
  [[315,1,4,4],[331,7,8,0],[451,12,4,4],[655,8,4,4],[789,1,3,5],[805,5,2,6]],
  [[235,2,4,4],[267,11,8,0],[451,12,8,0],[655,8,8,0],[789,14,8,0]],
  [[187,1,4,4],[203,15,8,0],[451,12,8,0],[657,4,4,4],[721,4,8,0],[789,12,8,0],[983,2,4,0]],
  [[133,2,4,4],[165,7,8,0],[278,4,4,0],[550,6,4,0],[658,6,4,0]]
];
const pixelsPerMetre = 1017 / 344.320;
export const groups = [];
export const rows = [];
for (let column=0; column<sections.length; column++) {
  for (const [drawingY,count,width,start] of sections[column]) {
    for (let row=0; row<count; row++) {
      const z=-(1005-drawingY)/pixelsPerMetre+row*SITE.rowPitch;
      rows.push({column,z,x:SITE.columns[column]+start*SITE.groupPitch,width:width*SITE.groupPitch-0.1,groups:width});
      for (let slot=0;slot<width;slot++) {
        const number=groups.length+1;
        groups.push({id:`S2-G${String(number).padStart(4,'0')}`,number,column,
          x:SITE.columns[column]+(start+slot)*SITE.groupPitch+SITE.groupWidth/2,z});
      }
    }
  }
}
if(groups.length!==1021) throw new Error('Shinan 2 source count mismatch');
export const layout = groups;
export const buildings = [
  {id:'S2-ER1',name:'제1 전기실',x:(530-503)/pixelsPerMetre,z:-(1005-574)/pixelsPerMetre,length:20.5,width:9.6,rotation:-Math.PI/2},
  {id:'S2-ER2',name:'제2 전기실',x:(1081-503)/pixelsPerMetre,z:-(1005-687)/pixelsPerMetre,length:18,width:9.6,rotation:0}
];
export default groups;
