import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const mount = document.getElementById('viewport');
const status = document.getElementById('viewer-status');
const data = document.getElementById('glb-data');
const assemblyData = document.getElementById('assembly-glb-data');
const assemblyConfig = document.getElementById('assembly-config');

function say(message) {
  status.textContent = message;
}

function decodeBase64(value) {
  const bytes = new Uint8Array(value.length * 3 / 4);
  let position = 0;
  for (let offset = 0; offset < value.length; offset += 32768) {
    const chunk = atob(value.slice(offset, offset + 32768));
    for (let index = 0; index < chunk.length; index += 1) {
      bytes[position++] = chunk.charCodeAt(index);
    }
  }
  return bytes.slice(0, position).buffer;
}

try {
  const configuration = assemblyConfig ? JSON.parse(assemblyConfig.textContent) : {};
  const unitScale = (unit) => unit === 'm' ? 1000 : 1;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0xf3f7fa);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.domElement.setAttribute('tabindex', '0');
  renderer.domElement.setAttribute('aria-label', 'Interactive board model; use arrow keys to orbit, plus and minus to zoom, F to fit');
  mount.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x647580, 2.2));
  const light = new THREE.DirectionalLight(0xffffff, 2.2);
  light.position.set(5, 8, 10);
  scene.add(light);
  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 10000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.screenSpacePanning = true;

  let center = new THREE.Vector3();
  let radius = 1;
  const orientations = {
    fit: [1, 0.8, 1], top: [0, 1, 0.001], bottom: [0, -1, -0.001],
    front: [0, 0, 1], back: [0, 0, -1], left: [-1, 0, 0], right: [1, 0, 0],
  };
  function orient(name) {
    const direction = new THREE.Vector3(...orientations[name]).normalize();
    camera.up.set(0, 1, 0);
    if (name === 'top') camera.up.set(0, 0, -1);
    if (name === 'bottom') camera.up.set(0, 0, 1);
    const fov = THREE.MathUtils.degToRad(camera.fov);
    const distance = radius / Math.sin(fov / 2) * 1.35;
    camera.position.copy(center).addScaledVector(direction, distance);
    camera.near = Math.max(distance / 1000, 0.001);
    camera.far = Math.max(distance * 100, 100);
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();
    say(`${name === 'fit' ? 'Fitted' : name + ' view'}; drag to rotate, Shift-drag or right-drag to pan, scroll to zoom.`);
  }
  function resize() {
    const width = Math.max(mount.clientWidth, 1);
    const height = Math.max(mount.clientHeight, 1);
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(mount);
  resize();

  document.querySelectorAll('[data-view]').forEach((button) => {
    button.addEventListener('click', () => orient(button.dataset.view));
  });
  function action(name) {
    if (name.startsWith('zoom')) {
      camera.position.sub(controls.target).multiplyScalar(name === 'zoom-in' ? 0.8 : 1.25).add(controls.target);
    } else {
      camera.updateMatrix();
      const axis = new THREE.Vector3().setFromMatrixColumn(camera.matrix, name.endsWith('left') || name.endsWith('right') ? 0 : 1);
      const sign = name.endsWith('left') || name.endsWith('down') ? -1 : 1;
      const offset = axis.multiplyScalar(sign * radius * 0.15);
      camera.position.add(offset);
      controls.target.add(offset);
    }
    controls.update();
    say(`${name.replace('-', ' ')}; use Fit to return to the visible models.`);
  }
  document.querySelectorAll('[data-action]').forEach((button) => {
    button.addEventListener('click', () => action(button.dataset.action));
  });
  renderer.domElement.addEventListener('keydown', (event) => {
    if (event.key === 'f' || event.key === 'F') orient('fit');
    else if (event.key === '+' || event.key === '=') action('zoom-in');
    else if (event.key === '-') action('zoom-out');
    else if (event.key.startsWith('Arrow')) {
      if (event.shiftKey) {
        action(`pan-${event.key.replace('Arrow', '').toLowerCase()}`);
        event.preventDefault();
        return;
      }
      const step = Math.PI / 18;
      const spherical = new THREE.Spherical().setFromVector3(camera.position.clone().sub(controls.target));
      if (event.key === 'ArrowLeft') spherical.theta += step;
      if (event.key === 'ArrowRight') spherical.theta -= step;
      if (event.key === 'ArrowUp') spherical.phi -= step;
      if (event.key === 'ArrowDown') spherical.phi += step;
      spherical.makeSafe();
      camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));
    } else return;
    event.preventDefault();
    controls.update();
  });

  const models = {};
  function fitModels() {
    const bounds = new THREE.Box3();
    for (const group of Object.values(models)) {
      if (group.visible) bounds.expandByObject(group);
    }
    if (bounds.isEmpty()) {
      say('No visible model geometry is available. Inspect the retained GLBs and model coverage.');
      return;
    }
    center = bounds.getCenter(new THREE.Vector3());
    radius = Math.max(bounds.getBoundingSphere(new THREE.Sphere()).radius, 0.001);
    orient('fit');
  }
  document.querySelectorAll('[data-model]').forEach((button) => {
    button.addEventListener('click', () => {
      const group = models[button.dataset.model];
      if (!group) return;
      group.visible = !group.visible;
      button.setAttribute('aria-pressed', String(group.visible));
      button.textContent = `${button.dataset.model === 'board' ? 'Board' : 'Enclosure'} ${group.visible ? 'visible' : 'hidden'}`;
      fitModels();
    });
  });
  say('Loading retained board model…');
  new GLTFLoader().parse(
    decodeBase64(data.textContent.trim()),
    '',
    (gltf) => {
      const board = new THREE.Group();
      board.scale.setScalar(unitScale(configuration.board_unit));
      board.add(gltf.scene);
      if (new THREE.Box3().setFromObject(board).isEmpty()) {
        say('The GLB has no visible geometry. Inspect the original export and model coverage.');
        return;
      }
      models.board = board;
      scene.add(board);
      if (!assemblyData) {
        fitModels();
        return;
      }
      say('Loading retained enclosure model…');
      new GLTFLoader().parse(
        decodeBase64(assemblyData.textContent.trim()),
        '',
        (enclosureGltf) => {
          const enclosure = new THREE.Group();
          enclosure.scale.setScalar(unitScale(configuration.enclosure_unit));
          enclosure.position.fromArray(configuration.translation_mm);
          enclosure.quaternion.fromArray(configuration.rotation_xyzw);
          enclosure.add(enclosureGltf.scene);
          if (new THREE.Box3().setFromObject(enclosure).isEmpty()) {
            say('The enclosure GLB has no visible geometry. Inspect the project model.');
            return;
          }
          models.enclosure = enclosure;
          scene.add(enclosure);
          fitModels();
        },
        (error) => say(`The retained enclosure GLB could not be rendered: ${error.message || error}`),
      );
    },
    (error) => say(`The retained GLB could not be rendered: ${error.message || error}`),
  );
  function frame() {
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  frame();
} catch (error) {
  say(`3D rendering is unavailable in this browser: ${error.message || error}`);
}
