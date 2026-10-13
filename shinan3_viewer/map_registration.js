import registration from '../results/shinan3_map_alignment/alignment.json';
export function mapCandidate(x,n,sourceHash){
  // Drawing digest is checked in the registration artifact; the source identity
  // is retained separately to avoid silently reusing this on another drawing.
  if(registration.layout_source_sha256!==sourceHash)return null;
  const t=registration.transform_xn_to_pixel,m=registration.imagery.mosaics[0];
  const px=t.a*x+t.b*n+t.tx,py=t.b*x-t.a*n+t.ty,w=256*2**m.zoom;
  return {lat:Math.atan(Math.sinh(Math.PI*(1-2*(m.tile_y0*256+py)/w)))*180/Math.PI,
    lon:(m.tile_x0*256+px)/w*360-180,status:'지도 기반 추정 · 실측 미확인'};
}
