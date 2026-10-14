// 3D site map for the console: 30,000 modules as one instanced mesh, coloured by inspection state.
// Built into web/vendor/map3d.js (see build_web.py) so the console opens from file:// without a server.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const PALETTE = {
  light: { background: 0xeaf0f7, ground: 0xdde5ef, field: 0xcfd9e6, idle: 0xa9b7c9, normal: 0x2fb38a, attention: 0xf59e0b, abnormal: 0xe11d48, building: 0x8494ab, halo: 0x0284c7 },
  dark: { background: 0x0a101a, ground: 0x0e1726, field: 0x142033, idle: 0x2b3b54, normal: 0x16a37b, attention: 0xf5a524, abnormal: 0xff4d6d, building: 0x40536f, halo: 0x38bdf8 },
};
const STATE = ['idle', 'normal', 'attention', 'abnormal'];
const DELTA_STOPS = [[-2, 0x3b82f6], [0, 0x2fb38a], [2, 0xf59e0b], [4, 0xe11d48]];

function deltaColor(value, color) {
  const stops = DELTA_STOPS;
  if (value <= stops[0][0]) return color.setHex(stops[0][1]);
  for (let i = 1; i < stops.length; i++) {
    if (value <= stops[i][0]) {
      const t = (value - stops[i - 1][0]) / (stops[i][0] - stops[i - 1][0]);
      return color.setHex(stops[i - 1][1]).lerp(new THREE.Color(stops[i][1]), t);
    }
  }
  return color.setHex(stops[stops.length - 1][1]);
}

function dotTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 64;
  const context = canvas.getContext('2d');
  context.beginPath(); context.arc(32, 32, 26, 0, Math.PI * 2);
  context.fillStyle = '#fff'; context.fill();
  context.lineWidth = 8; context.strokeStyle = 'rgba(15,23,42,.85)'; context.stroke();
  return new THREE.CanvasTexture(canvas);
}

export function create(container, data, { onPick = () => {}, onHover = () => {} } = {}) {
  const count = data.x.length;
  const tilt = THREE.MathUtils.degToRad(data.spec.tilt_deg);
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  container.append(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 1, 6000);
  const controls = new OrbitControls(camera, renderer.domElement);
  Object.assign(controls, { enableDamping: true, dampingFactor: .12, maxPolarAngle: THREE.MathUtils.degToRad(82), minDistance: 6, maxDistance: 1600, zoomToCursor: true, screenSpacePanning: false });
  controls.mouseButtons = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };
  controls.touches = { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_ROTATE };
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 2.2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(-200, 400, 300);
  scene.add(sun);

  // Drawing coordinates are east/north metres; the scene uses x = east, z = -north.
  const position = index => new THREE.Vector3(data.x[index], 0, -data.y[index]);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(4000, 4000).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial());
  ground.position.y = -.05;
  const shape = new THREE.Shape(data.boundary.map(([east, north]) => new THREE.Vector2(east, north)));
  const field = new THREE.Mesh(new THREE.ShapeGeometry(shape).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial());
  scene.add(ground, field);
  const buildings = new THREE.Group();
  for (const b of data.buildings) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(b.length, 4.5, b.width), new THREE.MeshLambertMaterial());
    mesh.position.set(b.center[0], 2.25, -b.center[1]);
    mesh.rotation.y = b.rotation;
    buildings.add(mesh);
  }
  scene.add(buildings);

  const modules = new THREE.InstancedMesh(new THREE.BoxGeometry(data.spec.module_width_m * .94, .05, data.spec.module_length_m * .96), new THREE.MeshLambertMaterial(), count);
  const halo = new THREE.InstancedMesh(new THREE.BoxGeometry(data.spec.module_width_m * 1.02, .05, data.spec.module_length_m * 1.22), new THREE.MeshBasicMaterial(), 64);
  const matrix = new THREE.Matrix4(), rotation = new THREE.Quaternion().setFromEuler(new THREE.Euler(tilt, 0, 0)), one = new THREE.Vector3(1, 1, 1);
  const place = (index, lift) => matrix.compose(position(index).setY(1.2 + lift), rotation, one);
  for (let i = 0; i < count; i++) modules.setMatrixAt(i, place(i, 0));
  modules.instanceMatrix.needsUpdate = true;
  modules.computeBoundingSphere();
  halo.count = 0;
  halo.frustumCulled = false;
  scene.add(halo, modules);

  // Screen-sized dots keep the few flagged modules visible when the whole site is in view.
  const flagged = [...data.state].map((s, i) => [Number(s), i]).filter(([s]) => s >= 2);
  const dotGeometry = new THREE.BufferGeometry();
  dotGeometry.setAttribute('position', new THREE.Float32BufferAttribute(flagged.flatMap(([, i]) => [data.x[i], 3, -data.y[i]]), 3));
  dotGeometry.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(flagged.length * 3), 3));
  const dots = new THREE.Points(dotGeometry, new THREE.PointsMaterial({ size: 11, sizeAttenuation: false, vertexColors: true, map: dotTexture(), alphaTest: .5, depthTest: false }));
  dots.renderOrder = 2;
  scene.add(dots);
  const pin = new THREE.Mesh(new THREE.RingGeometry(1.15, 1.5, 40).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true }));
  pin.renderOrder = 3;
  pin.visible = false;
  scene.add(pin);

  let palette = PALETTE.light, layer = 'final', dirty = true, selected = -1, flight = null, disposed = false;
  const color = new THREE.Color();
  function paint() {
    scene.background = new THREE.Color(palette.background);
    ground.material.color.setHex(palette.ground);
    field.material.color.setHex(palette.field);
    buildings.children.forEach(mesh => mesh.material.color.setHex(palette.building));
    halo.material.color.setHex(palette.halo);
    for (let i = 0; i < count; i++) {
      const state = Number(data.state[i]);
      if (layer === 'delta' && state && data.delta[i] != null) deltaColor(data.delta[i], color);
      else color.setHex(palette[STATE[state]]);
      modules.setColorAt(i, color);
    }
    modules.instanceColor.needsUpdate = true;
    const colors = dotGeometry.getAttribute('color');
    flagged.forEach(([state], n) => { color.setHex(palette[STATE[state]]); colors.setXYZ(n, color.r, color.g, color.b); });
    colors.needsUpdate = true;
    dirty = true;
  }

  function frame(indices) {
    const box = new THREE.Box3();
    for (const i of indices) box.expandByPoint(position(i));
    const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
    const span = Math.max(size.x / camera.aspect, size.z, 14);
    return { center, distance: span / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.25 };
  }
  function fly(center, distance, polar) {
    const offset = camera.position.clone().sub(controls.target);
    const spherical = new THREE.Spherical().setFromVector3(offset);
    flight = { start: performance.now(), fromTarget: controls.target.clone(), toTarget: center, from: spherical.clone(),
      to: new THREE.Spherical(distance ?? spherical.radius, polar ?? spherical.phi, spherical.theta) };
  }
  function step(now) {
    if (disposed) return;
    requestAnimationFrame(step);
    if (!renderer.domElement.isConnected) return;
    if (flight) {
      const t = Math.min(1, (now - flight.start) / 520), ease = 1 - Math.pow(1 - t, 3);
      controls.target.lerpVectors(flight.fromTarget, flight.toTarget, ease);
      const spherical = new THREE.Spherical(THREE.MathUtils.lerp(flight.from.radius, flight.to.radius, ease), THREE.MathUtils.lerp(flight.from.phi, flight.to.phi, ease), flight.from.theta);
      camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));
      if (t === 1) flight = null;
      dirty = true;
    }
    if (controls.update() || dirty) {
      if (pin.visible) pin.scale.setScalar(Math.max(1, camera.position.distanceTo(pin.position) / 110));
      renderer.render(scene, camera);
      dirty = false;
    }
  }

  const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
  function hit(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    const found = raycaster.intersectObject(modules)[0];
    return found ? found.instanceId : -1;
  }
  let down = null, hoverQueued = null;
  renderer.domElement.addEventListener('pointerdown', event => { down = [event.clientX, event.clientY]; });
  renderer.domElement.addEventListener('pointerup', event => {
    if (down && Math.hypot(event.clientX - down[0], event.clientY - down[1]) < 5 && event.button === 0) onPick(hit(event));
    down = null;
  });
  renderer.domElement.addEventListener('pointermove', event => {
    if (event.buttons) return onHover(-1);
    if (hoverQueued) { hoverQueued = event; return; }
    hoverQueued = event;
    requestAnimationFrame(() => { const e = hoverQueued; hoverQueued = null; onHover(hit(e), e.clientX, e.clientY); });
  });
  renderer.domElement.addEventListener('pointerleave', () => onHover(-1));
  renderer.domElement.addEventListener('contextmenu', event => event.preventDefault());

  function resize() {
    const width = container.clientWidth, height = container.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    dirty = true;
  }
  const observer = new ResizeObserver(resize);
  observer.observe(container);
  renderer.domElement.style.cssText = 'width:100%;height:100%;display:block;touch-action:none';
  resize();
  const all = Array.from({ length: count }, (_, i) => i);
  const home = frame(all);
  controls.target.copy(home.center);
  camera.position.copy(home.center).add(new THREE.Vector3().setFromSpherical(new THREE.Spherical(home.distance, THREE.MathUtils.degToRad(38), 0)));
  paint();
  requestAnimationFrame(step);

  return {
    setTheme(name) { palette = PALETTE[name] || PALETTE.light; paint(); },
    setLayer(name) { layer = name; paint(); },
    // Highlights the selected module and the string it belongs to (links are string-level reliable).
    select(index, { focus = true } = {}) {
      selected = index;
      pin.visible = index >= 0;
      halo.count = 0;
      if (index >= 0) {
        pin.position.copy(position(index)).setY(2.2);
        const string = data.string[index];
        let n = 0;
        for (let i = 0; i < count && n < 64; i++) if (data.string[i] === string) halo.setMatrixAt(n++, place(i, -.12));
        halo.count = n;
        halo.instanceMatrix.needsUpdate = true;
        if (focus) fly(position(index), Math.min(camera.position.distanceTo(controls.target), 70));
      }
      dirty = true;
    },
    fit(indices) { const target = frame(indices && indices.length ? indices : all); fly(target.center, target.distance); },
    view(name) { fly(controls.target.clone(), undefined, THREE.MathUtils.degToRad(name === 'top' ? 2 : 55)); },
    zoom(factor) { fly(controls.target.clone(), camera.position.distanceTo(controls.target) * factor); },
    get selected() { return selected; },
    element: container,
    dispose() { disposed = true; observer.disconnect(); controls.dispose(); renderer.dispose(); },
  };
}
