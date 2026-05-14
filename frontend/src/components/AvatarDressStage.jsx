import React, {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";

/**
 * 3D 试穿舞台。
 *
 * 与旧版差异：
 * - 旧版用 LatheGeometry + CapsuleGeometry 拼一个"假人台"，手臂只是两根胶囊，看着完全不像人。
 *   新版改成加载真实的 rigged GLB（默认是 three.js 官方的 Xbot.glb，带 mixamorig 骨骼），
 *   通过 `scripts/fetch_avatar.py` 拉到 data/samples/avatars/mannequin.glb。
 * - 移除了 GARMENT_PRESETS 内置服装；舞台只渲染上传 / 选中的 GLB。
 * - 服装 GLB 不再要求用户手动调一堆位置滑块：根据 bbox 比例自动判定上装 / 下装 / 全身，
 *   并对齐到 mannequin 的肩部 / 腰部 / 全身锚点。用户保留的滑块只是微调。
 *
 * Props:
 *   - settings.mannequinUrl       string  默认 /static/samples/avatars/mannequin.glb，可被用户上传覆盖
 *   - settings.bodyColor          string  body 着色键（porcelain / graphite / warm / studio）
 *   - settings.ghostBody          bool    人台半透明
 *   - settings.showGrid           bool    是否显示地面参考线
 *   - settings.slotTransforms     每个槽位的缩放 / 位移 / 旋转微调
 *   - garments                    { upper, lower, full, shoes } 四个可同时叠加的 GLB
 */

const GARMENT_SLOTS = ["upper", "lower", "full", "shoes"];
const DRACO_DECODER_PATH = "/draco/gltf/";
const BODY_COLORS = {
  porcelain: 0xe8ded2,
  graphite: 0x343b45,
  warm: 0xc99572,
  studio: 0xb8c1cc,
};

const DEFAULT_MANNEQUIN_URL = "/static/samples/avatars/mannequin.glb";
const TARGET_BODY_HEIGHT = 1.75; // 单位：米
let sharedDracoLoader = null;

function createGltfLoader() {
  const loader = new GLTFLoader();
  if (!sharedDracoLoader) {
    sharedDracoLoader = new DRACOLoader();
    sharedDracoLoader.setDecoderPath(DRACO_DECODER_PATH);
    sharedDracoLoader.setDecoderConfig({ type: "wasm" });
  }
  loader.setDRACOLoader(sharedDracoLoader);
  return loader;
}

// mannequin 解剖锚点（占身高百分比）。Xbot.glb 大致符合，真人 GLB 偏差也不大。
const ANCHOR_RATIOS = {
  foot: 0.0,
  knee: 0.26,
  hip: 0.51,
  waist: 0.58,
  shoulder: 0.82,
  neck: 0.86,
  head: 0.94,
  top: 1.0,
};

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

function applyBodyTint(model, color, ghost) {
  const target = new THREE.Color(color);
  model.traverse((obj) => {
    if (!obj.isMesh || !obj.material) return;
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    mats.forEach((m) => {
      if (!m) return;
      if (!m.userData.__origColor) {
        m.userData.__origColor = m.color ? m.color.clone() : new THREE.Color(0xffffff);
      }
      // 仅微调主色调，避免完全覆盖贴图
      if (m.color) m.color.copy(target).lerp(m.userData.__origColor, 0.55);
      m.transparent = ghost;
      m.opacity = ghost ? 0.55 : 1.0;
      m.needsUpdate = true;
    });
  });
}

function fitMannequin(model) {
  // 先 reset
  model.position.set(0, 0, 0);
  model.rotation.set(0, 0, 0);
  model.scale.set(1, 1, 1);

  const box0 = new THREE.Box3().setFromObject(model);
  const size = box0.getSize(new THREE.Vector3());
  const scale = TARGET_BODY_HEIGHT / Math.max(size.y, 1e-4);
  model.scale.setScalar(scale);

  // 重新算缩放后 bbox，再做"脚贴地 + XZ 居中"
  const box1 = new THREE.Box3().setFromObject(model);
  const center1 = box1.getCenter(new THREE.Vector3());
  model.position.x -= center1.x;
  model.position.z -= center1.z;
  model.position.y -= box1.min.y;

  const height = TARGET_BODY_HEIGHT;
  return {
    height,
    footY: 0,
    kneeY: height * ANCHOR_RATIOS.knee,
    hipY: height * ANCHOR_RATIOS.hip,
    waistY: height * ANCHOR_RATIOS.waist,
    shoulderY: height * ANCHOR_RATIOS.shoulder,
    neckY: height * ANCHOR_RATIOS.neck,
    headY: height * ANCHOR_RATIOS.head,
    topY: height * ANCHOR_RATIOS.top,
  };
}

/** 根据 bbox 推测服装类别。简单启发式，足够大多数 demo 场景。 */
function inferGarmentLayer(size) {
  const h = size.y;
  const w = Math.max(size.x, size.z);
  const ratio = h / Math.max(w, 1e-4);
  // 又高又窄：连衣裙 / 大衣 / 全身
  if (ratio > 1.6) return "full";
  // 又矮又胖：上装（外套展开、T 恤）
  if (ratio < 0.85) return "upper";
  // 高度比宽度略大：可能是裤子（细长但成对）也可能是上装
  // 用绝对尺寸辅助：相对身高 < 0.45 偏上装；> 0.6 偏下装
  if (h < 0.55) return "upper";
  if (h > 0.7) return "lower";
  return "upper";
}

function getSlotTransform(settings, slot) {
  const t = settings.slotTransforms?.[slot] || {};
  return {
    customScale: t.customScale ?? 1,
    customYOffset: t.customYOffset ?? 0,
    customXOffset: t.customXOffset ?? 0,
    customZOffset: t.customZOffset ?? 0,
    customRotationY: t.customRotationY ?? 0,
  };
}

/**
 * 服装 GLB 自动锚定：
 *   - 四个槽位分别用不同的人体锚点：上装 / 下装 / 连衣裙 / 鞋子
 *   - 缩放到匹配身体宽度（不超出肩宽 / 腰宽）
 *   - 上装锚定到 shoulder 高度（顶端贴近肩膀）
 *   - 下装锚定到 waist 高度（顶端贴近腰部）
 *   - 全身锚定到 shoulder，往下垂
 *   - 鞋子锚定到地面，默认略向前，避免被脚踝遮住
 *
 * 然后叠加用户的 X/Y/Z/Scale/Rot 微调。
 */
function autoFitGarment(model, anchors, settings, slot = "upper") {
  model.position.set(0, 0, 0);
  model.rotation.set(0, 0, 0);
  model.scale.set(1, 1, 1);

  const box0 = new THREE.Box3().setFromObject(model);
  const size = box0.getSize(new THREE.Vector3());

  const layer = GARMENT_SLOTS.includes(slot) ? slot : inferGarmentLayer(size);
  const transform = getSlotTransform(settings, layer);

  // 目标宽度（约等于肩宽 / 腰宽，单位米）和顶端锚 Y
  let targetWidth, anchorY, maxHeight, groundAlign, defaultZ;
  if (layer === "upper") {
    targetWidth = 0.46;
    anchorY = anchors.shoulderY + 0.04;
    maxHeight = 0.85;
    groundAlign = false;
    defaultZ = 0;
  } else if (layer === "lower") {
    targetWidth = 0.4;
    anchorY = anchors.waistY + 0.02;
    maxHeight = 1.1;
    groundAlign = false;
    defaultZ = 0;
  } else if (layer === "shoes") {
    targetWidth = 0.32;
    anchorY = anchors.footY;
    maxHeight = 0.22;
    groundAlign = true;
    defaultZ = 0.08;
  } else {
    targetWidth = 0.46;
    anchorY = anchors.shoulderY + 0.04;
    maxHeight = 1.48;
    groundAlign = false;
    defaultZ = 0;
  }

  // 用 max(x, z) 当作"前视宽度"
  const planarW = Math.max(size.x, size.z, 1e-4);
  const baseScale = targetWidth / planarW;

  // 控制垂直长度，避免小物件被放大到遮住整个人台。
  const maxScaleByH = maxHeight / Math.max(size.y, 1e-4);
  const fitScale = Math.min(baseScale, maxScaleByH);

  const scale = fitScale * transform.customScale;
  model.scale.setScalar(scale);
  model.rotation.y = transform.customRotationY;

  // 缩放完再算 bbox
  const box1 = new THREE.Box3().setFromObject(model);
  const center1 = box1.getCenter(new THREE.Vector3());

  model.position.x = -center1.x + transform.customXOffset;
  model.position.z = -center1.z + defaultZ + transform.customZOffset;
  model.position.y = groundAlign
    ? anchorY - box1.min.y + transform.customYOffset
    : anchorY - box1.max.y + transform.customYOffset;

  model.userData.__autoFit = {
    layer,
    anchorY,
    scale,
    bbox: box1.clone(),
  };
}

const AvatarDressStage = forwardRef(function AvatarDressStage(
  { settings, garments = {}, customModelUrl },
  ref,
) {
  const mountRef = useRef(null);
  const rendererRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const controlsRef = useRef(null);
  const mannequinRef = useRef(null); // { group, anchors }
  const garmentRefs = useRef({});    // slot -> { wrapper, model }
  const gridRef = useRef(null);
  const [mannequinError, setMannequinError] = useState(null);
  const [garmentErrors, setGarmentErrors] = useState({});

  useImperativeHandle(
    ref,
    () => ({
      snapshot() {
        const renderer = rendererRef.current;
        if (!renderer) return null;
        return renderer.domElement.toDataURL("image/png");
      },
    }),
    [],
  );

  // ---- 初始化 three.js 场景（仅一次） ----
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fafc);
    scene.fog = new THREE.Fog(0xf8fafc, 8, 18);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(38, 1, 0.05, 100);
    camera.position.set(2.4, 1.7, 3.2);
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
    controls.target.set(0, 1.0, 0);
    controls.minDistance = 1.4;
    controls.maxDistance = 7.0;
    controlsRef.current = controls;

    scene.add(new THREE.HemisphereLight(0xffffff, 0xb7c2ce, 1.6));
    const key = new THREE.DirectionalLight(0xffffff, 2.4);
    key.position.set(3, 4, 3);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.near = 0.5;
    key.shadow.camera.far = 10;
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xdbeafe, 1.0);
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
      if (renderer.domElement.parentElement === mount) {
        mount.removeChild(renderer.domElement);
      }
      scene.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose?.();
        if (obj.material) {
          if (Array.isArray(obj.material)) {
            obj.material.forEach((m) => m.dispose?.());
          } else {
            obj.material.dispose?.();
          }
        }
      });
    };
  }, []);

  // ---- 加载 mannequin GLB ----
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return undefined;
    const url = settings.mannequinUrl || DEFAULT_MANNEQUIN_URL;

    if (mannequinRef.current) {
      scene.remove(mannequinRef.current.group);
      disposeObject(mannequinRef.current.group);
      mannequinRef.current = null;
    }

    let cancelled = false;
    setMannequinError(null);

    const loader = createGltfLoader();
    loader.load(
      url,
      (gltf) => {
        if (cancelled) return;
        const model = gltf.scene;
        model.traverse((obj) => {
          if (obj.isMesh) {
            obj.castShadow = true;
            obj.receiveShadow = true;
          }
        });
        const anchors = fitMannequin(model);
        applyBodyTint(
          model,
          BODY_COLORS[settings.bodyColor] || BODY_COLORS.porcelain,
          !!settings.ghostBody,
        );
        scene.add(model);
        mannequinRef.current = { group: model, anchors };

        // mannequin 一加载就重新对齐已有服装
        Object.entries(garmentRefs.current).forEach(([slot, item]) => {
          autoFitGarment(item.model, anchors, settings, slot);
        });
      },
      undefined,
      (err) => {
        if (cancelled) return;
        const msg = err?.message || String(err);
        setMannequinError(
          msg.includes("404") || msg.includes("HTTP")
            ? "找不到 mannequin GLB。请运行：python scripts/fetch_avatar.py"
            : `mannequin 加载失败：${msg}`,
        );
      },
    );

    return () => {
      cancelled = true;
    };
  }, [settings.mannequinUrl]);

  // ---- 更新 mannequin 着色 / 半透明（不重载 GLB） ----
  useEffect(() => {
    if (!mannequinRef.current) return;
    applyBodyTint(
      mannequinRef.current.group,
      BODY_COLORS[settings.bodyColor] || BODY_COLORS.porcelain,
      !!settings.ghostBody,
    );
  }, [settings.bodyColor, settings.ghostBody]);

  useEffect(() => {
    if (gridRef.current) gridRef.current.visible = !!settings.showGrid;
  }, [settings.showGrid]);

  // ---- 加载 / 切换 服装 GLB（四个槽位可同时存在） ----
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return undefined;

    Object.values(garmentRefs.current).forEach((item) => {
      scene.remove(item.wrapper);
      disposeObject(item.wrapper);
    });
    garmentRefs.current = {};
    setGarmentErrors({});

    let cancelled = false;
    const entries = Object.entries(garments || {}).filter(([, garment]) => garment?.url);
    if (!entries.length && customModelUrl) {
      entries.push(["upper", { url: customModelUrl, label: "服装 GLB" }]);
    }
    if (!entries.length) return undefined;

    entries.forEach(([slot, garment]) => {
      const loader = createGltfLoader();
      loader.load(
        garment.url,
        (gltf) => {
          if (cancelled) return;
          const wrapper = new THREE.Group();
          wrapper.name = `garment-${slot}`;
          const model = gltf.scene;
          model.traverse((obj) => {
            if (obj.isMesh) {
              obj.castShadow = true;
              obj.receiveShadow = true;
            }
          });
          wrapper.add(model);
          garmentRefs.current[slot] = { wrapper, model };
          if (mannequinRef.current) {
            autoFitGarment(model, mannequinRef.current.anchors, settings, slot);
          }
          scene.add(wrapper);
        },
        undefined,
        (err) => {
          if (cancelled) return;
          const msg = err?.message || String(err);
          setGarmentErrors((prev) => ({
            ...prev,
            [slot]: `${garment.label || "服装"} 加载失败：${msg}`,
          }));
        },
      );
    });

    return () => {
      cancelled = true;
      Object.values(garmentRefs.current).forEach((item) => {
        scene.remove(item.wrapper);
        disposeObject(item.wrapper);
      });
      garmentRefs.current = {};
    };
  }, [garments, customModelUrl]);

  // ---- 服装微调（不重载 GLB） ----
  useEffect(() => {
    if (!mannequinRef.current) return;
    Object.entries(garmentRefs.current).forEach(([slot, item]) => {
      autoFitGarment(item.model, mannequinRef.current.anchors, settings, slot);
    });
  }, [settings.slotTransforms]);

  return (
    <div className="avatar-stage" ref={mountRef}>
      {mannequinError && (
        <div className="avatar-stage-overlay">
          <strong>3D 人台不可用</strong>
          <p>{mannequinError}</p>
          <p className="hint">
            下载完成后刷新页面。也可以把任意 rigged GLB 放到{" "}
            <code>data/samples/avatars/mannequin.glb</code> 替换。
          </p>
        </div>
      )}
      {Object.keys(garmentErrors).length > 0 && (
        <div className="avatar-stage-toast">
          {Object.entries(garmentErrors).map(([slot, msg]) => (
            <div key={slot}>{msg}</div>
          ))}
        </div>
      )}
    </div>
  );
});

export default AvatarDressStage;
