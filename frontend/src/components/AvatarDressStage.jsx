import React, {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const BODY_COLORS = {
  porcelain: 0xe8ded2,
  graphite: 0x343b45,
  warm: 0xc99572,
  studio: 0xb8c1cc,
};

const GARMENT_PRESETS = {
  tee: { label: "短袖 T 恤", layer: "upper" },
  jacket: { label: "廓形外套", layer: "upper" },
  hoodie: { label: "连帽卫衣", layer: "upper" },
  dress: { label: "连衣裙", layer: "full" },
  pants: { label: "直筒长裤", layer: "lower" },
};

function makeMat({ color, material, opacity = 1, roughness = 0.58 }) {
  const mat = new THREE.MeshStandardMaterial({
    color,
    roughness,
    metalness: 0.02,
    transparent: opacity < 1,
    opacity,
    side: THREE.DoubleSide,
  });
  if (material === "satin") {
    mat.roughness = 0.28;
    mat.metalness = 0.08;
  } else if (material === "denim") {
    mat.roughness = 0.86;
    mat.metalness = 0.0;
  } else if (material === "technical") {
    mat.roughness = 0.42;
    mat.metalness = 0.18;
  }
  return mat;
}

function capsule(radius, length, material, position, rotation = [0, 0, 0], scale = [1, 1, 1]) {
  const mesh = new THREE.Mesh(new THREE.CapsuleGeometry(radius, length, 16, 24), material);
  mesh.position.set(...position);
  mesh.rotation.set(...rotation);
  mesh.scale.set(...scale);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function cylinder(radiusTop, radiusBottom, height, material, position, radial = 48) {
  const mesh = new THREE.Mesh(
    new THREE.CylinderGeometry(radiusTop, radiusBottom, height, radial, 1, false),
    material,
  );
  mesh.position.set(...position);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function box(size, material, position, rotation = [0, 0, 0]) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
  mesh.position.set(...position);
  mesh.rotation.set(...rotation);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function sphere(radius, material, position, scale = [1, 1, 1]) {
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, 32, 24), material);
  mesh.position.set(...position);
  mesh.scale.set(...scale);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function latheBody(points, material, position, scale = [1, 1, 1]) {
  const geom = new THREE.LatheGeometry(
    points.map(([radius, y]) => new THREE.Vector2(radius, y)),
    64,
  );
  const mesh = new THREE.Mesh(geom, material);
  mesh.position.set(...position);
  mesh.scale.set(...scale);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function addSeam(group, from, to, color = 0xf8fafc) {
  const geom = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(...from),
    new THREE.Vector3(...to),
  ]);
  const line = new THREE.Line(
    geom,
    new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.62 }),
  );
  group.add(line);
}

function disposeObject(root) {
  if (!root) return;
  root.traverse((obj) => {
    if (obj.geometry) obj.geometry.dispose?.();
    if (obj.material) {
      if (Array.isArray(obj.material)) {
        obj.material.forEach((m) => m.dispose?.());
      } else {
        obj.material.dispose?.();
      }
    }
  });
}

function buildMannequin(settings) {
  const {
    bodyColor,
    heightScale,
    shoulderScale,
    waistScale,
    ghostBody,
    pose,
  } = settings;
  const group = new THREE.Group();
  group.name = "mannequin";
  group.scale.set(1, heightScale, 1);

  const bodyMat = makeMat({
    color: BODY_COLORS[bodyColor] || BODY_COLORS.porcelain,
    material: "matte",
    opacity: ghostBody ? 0.48 : 1,
    roughness: 0.72,
  });

  const shoulder = shoulderScale;
  const waist = waistScale;
  const armTilt = pose === "a" ? 0.48 : pose === "relaxed" ? 0.28 : 0.18;
  const legSpread = pose === "runway" ? 0.11 : 0.17;
  const hipWidth = 0.38 * waist;
  const torsoProfile = [
    [0.16, 0.00],
    [0.28, 0.08],
    [0.34, 0.22],
    [0.29, 0.48],
    [0.34, 0.76],
    [0.42, 0.98],
    [0.31, 1.12],
    [0.13, 1.22],
  ];

  group.add(latheBody(torsoProfile, bodyMat, [0, 1.28, 0], [shoulder, 1, 0.62]));
  group.add(sphere(0.31, bodyMat, [0, 1.28, 0], [waist * 1.32, 0.58, 0.82]));
  group.add(capsule(0.07, 0.18, bodyMat, [0, 2.53, 0], [0, 0, 0]));
  group.add(sphere(0.22, bodyMat, [0, 2.79, 0], [0.78, 1.12, 0.9]));

  group.add(capsule(0.095, 0.55, bodyMat, [-0.46 * shoulder, 2.08, 0], [0, 0, armTilt]));
  group.add(capsule(0.095, 0.55, bodyMat, [0.46 * shoulder, 2.08, 0], [0, 0, -armTilt]));
  group.add(capsule(0.072, 0.58, bodyMat, [-0.63 * shoulder, 1.54, 0], [0, 0, armTilt * 0.72]));
  group.add(capsule(0.072, 0.58, bodyMat, [0.63 * shoulder, 1.54, 0], [0, 0, -armTilt * 0.72]));
  group.add(sphere(0.072, bodyMat, [-0.74 * shoulder, 1.12, 0], [0.78, 1.08, 0.7]));
  group.add(sphere(0.072, bodyMat, [0.74 * shoulder, 1.12, 0], [0.78, 1.08, 0.7]));

  group.add(capsule(0.12, 0.58, bodyMat, [-legSpread, 0.98, 0], [0, 0, -0.03], [0.9, 1, 0.86]));
  group.add(capsule(0.12, 0.58, bodyMat, [legSpread, 0.98, 0], [0, 0, 0.03], [0.9, 1, 0.86]));
  group.add(capsule(0.085, 0.62, bodyMat, [-legSpread * 0.96, 0.37, 0], [0, 0, -0.02], [0.82, 1, 0.78]));
  group.add(capsule(0.085, 0.62, bodyMat, [legSpread * 0.96, 0.37, 0], [0, 0, 0.02], [0.82, 1, 0.78]));
  group.add(sphere(0.095, bodyMat, [-legSpread * 0.95, 0.05, 0.05], [1.45, 0.44, 1.9]));
  group.add(sphere(0.095, bodyMat, [legSpread * 0.95, 0.05, 0.05], [1.45, 0.44, 1.9]));
  group.add(sphere(0.06, bodyMat, [-hipWidth, 1.85, 0], [1, 1, 1]));
  group.add(sphere(0.06, bodyMat, [hipWidth, 1.85, 0], [1, 1, 1]));

  const base = cylinder(0.42, 0.5, 0.08, makeMat({ color: 0x1f2937, material: "matte" }), [0, 0.02, 0], 64);
  base.receiveShadow = true;
  group.add(base);
  return group;
}

function sleeve(group, side, mat, shoulderScale, color) {
  const x = side * 0.51 * shoulderScale;
  const rot = side > 0 ? -0.36 : 0.36;
  group.add(capsule(0.105, 0.6, mat, [x, 1.98, 0], [0, 0, rot]));
  addSeam(group, [side * 0.38 * shoulderScale, 2.23, 0.08], [side * 0.66 * shoulderScale, 1.7, 0.08], color);
}

function buildGarment(settings) {
  const {
    garment,
    garmentColor,
    garmentMaterial,
    shoulderScale,
    waistScale,
    heightScale,
    showSeams,
  } = settings;
  const group = new THREE.Group();
  group.name = "garment";
  group.scale.set(1, heightScale, 1);

  const mat = makeMat({ color: garmentColor, material: garmentMaterial });
  const dark = new THREE.Color(garmentColor).multiplyScalar(0.72).getHex();
  const seam = 0xffffff;
  const shoulder = shoulderScale;
  const waist = waistScale;

  if (garment === "tee") {
    group.add(cylinder(0.46 * shoulder, 0.36 * waist, 0.86, mat, [0, 1.92, 0], 64));
    sleeve(group, -1, mat, shoulder, seam);
    sleeve(group, 1, mat, shoulder, seam);
    group.add(cylinder(0.23, 0.25, 0.035, makeMat({ color: dark, material: garmentMaterial }), [0, 2.39, 0], 48));
    if (showSeams) {
      addSeam(group, [-0.35 * shoulder, 2.31, 0.12], [-0.26 * waist, 1.5, 0.12], seam);
      addSeam(group, [0.35 * shoulder, 2.31, 0.12], [0.26 * waist, 1.5, 0.12], seam);
    }
  }

  if (garment === "jacket") {
    group.add(cylinder(0.52 * shoulder, 0.42 * waist, 1.06, mat, [0, 1.88, 0], 64));
    group.add(capsule(0.12, 0.84, mat, [-0.56 * shoulder, 1.88, 0], [0, 0, 0.26]));
    group.add(capsule(0.12, 0.84, mat, [0.56 * shoulder, 1.88, 0], [0, 0, -0.26]));
    group.add(box([0.18, 0.62, 0.035], makeMat({ color: dark, material: garmentMaterial }), [-0.11, 1.92, 0.36], [0, 0, -0.18]));
    group.add(box([0.18, 0.62, 0.035], makeMat({ color: dark, material: garmentMaterial }), [0.11, 1.92, 0.36], [0, 0, 0.18]));
    if (showSeams) {
      addSeam(group, [0, 2.38, 0.39], [0, 1.35, 0.39], seam);
      addSeam(group, [-0.44 * shoulder, 2.28, 0.1], [0.44 * shoulder, 2.28, 0.1], seam);
    }
  }

  if (garment === "hoodie") {
    group.add(cylinder(0.5 * shoulder, 0.43 * waist, 1.02, mat, [0, 1.86, 0], 64));
    group.add(capsule(0.12, 0.78, mat, [-0.55 * shoulder, 1.86, 0], [0, 0, 0.28]));
    group.add(capsule(0.12, 0.78, mat, [0.55 * shoulder, 1.86, 0], [0, 0, -0.28]));
    const hood = new THREE.Mesh(
      new THREE.TorusGeometry(0.27, 0.07, 16, 48),
      mat,
    );
    hood.position.set(0, 2.54, -0.09);
    hood.rotation.x = Math.PI / 2;
    hood.castShadow = true;
    group.add(hood);
    group.add(box([0.34, 0.18, 0.05], makeMat({ color: dark, material: garmentMaterial }), [0, 1.68, 0.39]));
    if (showSeams) addSeam(group, [0, 2.28, 0.4], [0, 1.34, 0.4], seam);
  }

  if (garment === "dress") {
    group.add(cylinder(0.42 * shoulder, 0.32 * waist, 0.58, mat, [0, 2.12, 0], 64));
    group.add(cylinder(0.32 * waist, 0.68, 1.08, mat, [0, 1.36, 0], 64));
    sleeve(group, -1, mat, shoulder, seam);
    sleeve(group, 1, mat, shoulder, seam);
    group.add(cylinder(0.68, 0.7, 0.035, makeMat({ color: dark, material: garmentMaterial }), [0, 0.82, 0], 64));
    if (showSeams) {
      addSeam(group, [-0.18, 1.85, 0.42], [-0.52, 0.84, 0.42], seam);
      addSeam(group, [0.18, 1.85, 0.42], [0.52, 0.84, 0.42], seam);
    }
  }

  if (garment === "pants") {
    group.add(cylinder(0.32 * waist, 0.33 * waist, 0.18, mat, [0, 1.25, 0], 48));
    group.add(capsule(0.17, 1.12, mat, [-0.16, 0.67, 0], [0, 0, -0.02]));
    group.add(capsule(0.17, 1.12, mat, [0.16, 0.67, 0], [0, 0, 0.02]));
    group.add(cylinder(0.18, 0.18, 0.04, makeMat({ color: dark, material: garmentMaterial }), [-0.16, 0.06, 0], 36));
    group.add(cylinder(0.18, 0.18, 0.04, makeMat({ color: dark, material: garmentMaterial }), [0.16, 0.06, 0], 36));
    if (showSeams) {
      addSeam(group, [0, 1.25, 0.2], [0, 0.12, 0.2], seam);
      addSeam(group, [-0.27, 1.08, 0.12], [-0.24, 0.15, 0.12], seam);
      addSeam(group, [0.27, 1.08, 0.12], [0.24, 0.15, 0.12], seam);
    }
  }

  const preset = GARMENT_PRESETS[garment] || GARMENT_PRESETS.tee;
  group.userData.layer = preset.layer;
  return group;
}

function fitCustomModel(model, settings) {
  const box = model.userData.fitBox || new THREE.Box3().setFromObject(model);
  const size = model.userData.fitSize || new THREE.Vector3();
  const center = model.userData.fitCenter || new THREE.Vector3();
  if (!model.userData.fitBox) {
    box.getSize(size);
    box.getCenter(center);
    model.userData.fitBox = box.clone();
    model.userData.fitSize = size.clone();
    model.userData.fitCenter = center.clone();
  }
  const maxDim = Math.max(size.x, size.y, size.z) || 1;
  const scale = (1.2 / maxDim) * settings.customScale;
  model.scale.setScalar(scale);
  model.rotation.set(0, settings.customRotationY, 0);
  model.position.set(
    settings.customXOffset - center.x * scale,
    -box.min.y * scale + 1.05 + settings.customYOffset,
    settings.customZOffset - center.z * scale,
  );
}

const AvatarDressStage = forwardRef(function AvatarDressStage({
  settings,
  customModelUrl,
}, ref) {
  const mountRef = useRef(null);
  const rendererRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const controlsRef = useRef(null);
  const avatarRef = useRef(null);
  const garmentRef = useRef(null);
  const customRef = useRef(null);
  const gridRef = useRef(null);

  useImperativeHandle(ref, () => ({
    snapshot() {
      const renderer = rendererRef.current;
      if (!renderer) return null;
      return renderer.domElement.toDataURL("image/png");
    },
  }), []);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fafc);
    scene.fog = new THREE.Fog(0xf8fafc, 7, 14);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    camera.position.set(3.4, 2.35, 4.2);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: true,
    });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    mount.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(0, 1.45, 0);
    controls.minDistance = 2.4;
    controls.maxDistance = 7.2;
    controlsRef.current = controls;

    scene.add(new THREE.HemisphereLight(0xffffff, 0xb7c2ce, 1.8));
    const key = new THREE.DirectionalLight(0xffffff, 2.6);
    key.position.set(4, 5, 3);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xdbeafe, 1.2);
    rim.position.set(-3, 2.4, -4);
    scene.add(rim);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(2.2, 80),
      new THREE.MeshStandardMaterial({ color: 0xeef2f7, roughness: 0.82 }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    const grid = new THREE.GridHelper(4.4, 18, 0xaeb8c5, 0xd5dce5);
    grid.position.y = 0.006;
    gridRef.current = grid;
    scene.add(grid);

    const resize = () => {
      const rect = mount.getBoundingClientRect();
      const width = Math.max(320, rect.width || 320);
      const height = Math.max(420, rect.height || 520);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(mount);

    let raf = 0;
    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      scene.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose?.();
        if (obj.material) {
          if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose?.());
          else obj.material.dispose?.();
        }
      });
    };
  }, []);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    if (avatarRef.current) {
      scene.remove(avatarRef.current);
      disposeObject(avatarRef.current);
    }
    if (garmentRef.current) {
      scene.remove(garmentRef.current);
      disposeObject(garmentRef.current);
    }

    avatarRef.current = buildMannequin(settings);
    garmentRef.current = buildGarment(settings);
    scene.add(avatarRef.current);
    scene.add(garmentRef.current);
  }, [settings]);

  useEffect(() => {
    if (gridRef.current) gridRef.current.visible = settings.showGrid;
  }, [settings.showGrid]);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return undefined;
    if (customRef.current) {
      scene.remove(customRef.current);
      disposeObject(customRef.current);
      customRef.current = null;
    }
    if (!customModelUrl) return undefined;

    let cancelled = false;
    const loader = new GLTFLoader();
    loader.load(
      customModelUrl,
      (gltf) => {
        if (cancelled) return;
        const wrapper = new THREE.Group();
        const model = gltf.scene;
        const fitBox = new THREE.Box3().setFromObject(model);
        const fitSize = new THREE.Vector3();
        const fitCenter = new THREE.Vector3();
        fitBox.getSize(fitSize);
        fitBox.getCenter(fitCenter);
        model.userData.fitBox = fitBox;
        model.userData.fitSize = fitSize;
        model.userData.fitCenter = fitCenter;
        fitCustomModel(model, settings);
        model.traverse((obj) => {
          if (obj.isMesh) {
            obj.castShadow = true;
            obj.receiveShadow = true;
          }
        });
        wrapper.add(model);
        wrapper.userData.model = model;
        customRef.current = wrapper;
        scene.add(wrapper);
      },
      undefined,
      () => {
        // Experimental user assets should not break the whole stage.
      },
    );

    return () => {
      cancelled = true;
      if (customRef.current) {
        scene.remove(customRef.current);
        disposeObject(customRef.current);
        customRef.current = null;
      }
    };
  }, [customModelUrl]);

  useEffect(() => {
    const model = customRef.current?.userData?.model;
    if (model) fitCustomModel(model, settings);
  }, [
    settings.customScale,
    settings.customYOffset,
    settings.customXOffset,
    settings.customZOffset,
    settings.customRotationY,
  ]);

  return <div className="avatar-stage" ref={mountRef} />;
});

export { GARMENT_PRESETS };
export default AvatarDressStage;
