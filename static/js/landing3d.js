// Cascade Sentinel: 3D scroll story. Three.js + bloom; GSAP/ScrollTrigger + Lenis for scroll.
// The scene is a stylised copy of the real FalkorDB corridor (node ids match the seed graph).
// Every number shown on the page comes from the project's own synthetic backtest output.

const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const isMobile = matchMedia("(max-width: 768px), (pointer: coarse)").matches;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const smooth = (t) => t * t * (3 - 2 * t);
const ramp = (s, a, b) => smooth(clamp((s - a) / (b - a)));
const bell = (s, a, b, c, d) => ramp(s, a, b) * (1 - ramp(s, c, d));
const lerp = (a, b, t) => a + (b - a) * t;

/* ------------------------------------------------------------------ DOM chrome */
function splitWords() {
  $$(".split").forEach((el) => {
    const walk = (node) => {
      [...node.childNodes].forEach((n) => {
        if (n.nodeType === 3) {
          const frag = document.createDocumentFragment();
          n.textContent.split(/(\s+)/).forEach((part) => {
            if (!part) return;
            if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(part)); return; }
            const w = document.createElement("span"); w.className = "w";
            const i = document.createElement("span"); i.textContent = part;
            w.appendChild(i); frag.appendChild(w);
          });
          n.replaceWith(frag);
        } else if (n.nodeType === 1 && n.tagName !== "CODE") {
          walk(n);
        } else if (n.nodeType === 1) {
          const w = document.createElement("span"); w.className = "w";
          n.replaceWith(w); const i = document.createElement("span"); i.appendChild(n); w.appendChild(i);
        }
      });
    };
    walk(el);
  });
}

function chrome() {
  const nav = $("#nav");
  const bar = $("#progressBar");
  const rail = $$(".chapter-rail li");
  const chapters = $$(".chapter");
  const onScroll = () => {
    const y = scrollY;
    nav.classList.toggle("scrolled", y > 40);
    const max = document.documentElement.scrollHeight - innerHeight;
    bar.style.transform = `scaleX(${max > 0 ? y / max : 0})`;
    const mid = y + innerHeight * 0.5;
    let cur = 0;
    chapters.forEach((c, i) => { if (c.offsetTop <= mid) cur = i; });
    rail.forEach((li, i) => li.classList.toggle("on", i === cur));
  };
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  $$("[data-copy]").forEach((btn) => btn.addEventListener("click", async () => {
    const pre = btn.closest("pre");
    const text = pre ? pre.innerText.replace(/^Copy\s*/, "").trim() : "";
    try { await navigator.clipboard.writeText(text); btn.textContent = "Copied"; }
    catch { btn.textContent = "Select + copy"; }
    setTimeout(() => (btn.textContent = "Copy"), 1400);
  }));
}

function fmt(v, dec) { return Number(v).toFixed(dec); }

function motionText() {
  const gsap = window.gsap, ST = window.ScrollTrigger;
  const tweens = $$(".tw");
  if (!gsap || !ST || reduceMotion) {
    tweens.forEach((el) => { const [, b] = el.dataset.tween.split(":"); el.textContent = fmt(b, el.dataset.dec ?? 2); });
    return null;
  }
  gsap.registerPlugin(ST);
  let lenis = null;
  if (window.Lenis) {
    lenis = new window.Lenis({ lerp: 0.085, smoothWheel: true });
    lenis.on("scroll", ST.update);
    gsap.ticker.add((t) => lenis.raf(t * 1000));
    gsap.ticker.lagSmoothing(0);
    $$('a[href^="#"]').forEach((a) => a.addEventListener("click", (e) => {
      const id = a.getAttribute("href");
      if (id.length > 1 && $(id)) { e.preventDefault(); lenis.scrollTo($(id), { offset: id === "#proof" ? -40 : 0, duration: 1.6 }); }
    }));
  }
  // hero intro
  gsap.from(".hero .display .w > span", { yPercent: 115, duration: 1.2, ease: "expo.out", stagger: 0.045, delay: 0.35 });
  gsap.from([".hero .eyebrow", ".hero .pitch", ".hero .cta-row", ".hero-meta"], { y: 24, opacity: 0, duration: 1, ease: "expo.out", stagger: 0.1, delay: 0.8 });
  // chapter panels
  $$(".chapter:not(.hero)").forEach((sec) => {
    const words = $$(".split .w > span", sec);
    const tl = gsap.timeline({ scrollTrigger: { trigger: sec, start: "top 70%", toggleActions: "play none none reverse" } });
    tl.from($$(".panel, .finale-inner > .kicker", sec), { y: 40, opacity: 0, duration: 0.9, ease: "expo.out" })
      .from(words, { yPercent: 110, duration: 0.9, ease: "expo.out", stagger: 0.025 }, "<0.1")
      .from($$(".hops li, .agent, .mcard, .legend li, .track, .refusal, .formula", sec), { y: 16, opacity: 0, duration: 0.6, ease: "power3.out", stagger: 0.05 }, "<0.25");
  });
  // number tweens (memory write-back)
  tweens.forEach((el) => {
    const [a, b] = el.dataset.tween.split(":").map(Number);
    const dec = Number(el.dataset.dec ?? 2);
    const o = { v: a };
    gsap.to(o, { v: b, duration: 1.6, ease: "power2.inOut", onUpdate: () => (el.textContent = fmt(o.v, dec)),
      scrollTrigger: { trigger: el.closest(".chapter"), start: "top 35%", toggleActions: "play none none reverse" } });
  });
  gsap.from(".stat", { y: 30, opacity: 0, duration: 0.8, stagger: 0.06, ease: "expo.out", scrollTrigger: { trigger: ".stats", start: "top 85%" } });
  return lenis;
}

/* ------------------------------------------------------------------ 3D */
const NODES = {
  heatwave: [-7.2, 1.2, -2.0],
  fodder_jowar_vegetative: [-3.6, 0.2, 0.0],
  fodder: [-1.0, 1.0, 0.8],
  mandi_fodder: [1.6, -0.2, 0.2],
  farm_laborers: [4.0, 0.6, -0.4],
  heat_stress_illness: [6.8, -0.4, 0.4],
  wheat_grainfill: [-3.4, 3.0, -2.4],
  wheat_grain: [-0.6, 3.6, -2.8],
  mandi_wheat: [2.2, 2.8, -2.3],
  dairy_cattle: [-3.8, -2.5, 1.6],
  milk: [-1.0, -3.1, 2.1],
  dairy_collection: [1.8, -2.9, 1.8],
  dairy_households: [4.5, -2.5, 1.8],
  waterborne_diarrhoea: [6.4, 2.0, -1.5],
  worksite_cool_shelters: [5.6, -1.7, -1.6],
};
// [from, to, group]
const EDGES = [
  ["heatwave", "fodder_jowar_vegetative", "main"],
  ["fodder_jowar_vegetative", "fodder", "main"],
  ["fodder", "mandi_fodder", "main"],
  ["mandi_fodder", "farm_laborers", "main"],
  ["farm_laborers", "heat_stress_illness", "main"],
  ["heatwave", "wheat_grainfill", "wheat"],
  ["wheat_grainfill", "wheat_grain", "wheat"],
  ["wheat_grain", "mandi_wheat", "wheat"],
  ["mandi_wheat", "farm_laborers", "wheat"],
  ["heatwave", "dairy_cattle", "dairy"],
  ["dairy_cattle", "milk", "dairy"],
  ["milk", "dairy_collection", "dairy"],
  ["dairy_collection", "dairy_households", "dairy"],
  ["farm_laborers", "waterborne_diarrhoea", "water"],
  ["heatwave", "farm_laborers", "direct"],
  ["worksite_cool_shelters", "farm_laborers", "shelter"],
];
const LABELS = [
  { id: "heatwave", text: "heatwave · Tmax forecast", cls: "big", show: (s) => s > 0.05 && s < 1.85, mobile: true },
  { id: "fodder_jowar_vegetative", text: "fodder_jowar_vegetative", show: (s) => bell(s, 0.7, 0.9, 1.9, 2.05) },
  { id: "fodder", text: "fodder", show: (s) => bell(s, 0.7, 0.9, 1.9, 2.05) },
  { id: "mandi_fodder", text: "mandi_fodder · price shock", show: (s) => bell(s, 0.7, 0.9, 1.9, 2.05), mobile: true },
  { id: "farm_laborers", text: "farm_laborers", show: (s) => bell(s, 0.8, 1.0, 3.6, 3.75), mobile: true },
  { id: "heat_stress_illness", text: "heat_stress_illness · +21 d", cls: "big", show: (s) => bell(s, 1.0, 1.2, 1.95, 2.05), mobile: true },
  { id: "wheat_grain", text: "agronomy: wheat path", show: (s) => bell(s, 1.85, 2.05, 2.95, 3.1), mobile: true, defeatAt: 2.6 },
  { id: "worksite_cool_shelters", text: "worksite_cool_shelters · P 0.27 → 0.50 · act", cls: "okl", show: (s) => bell(s, 2.95, 3.1, 3.8, 3.95), mobile: true },
  { id: "dairy_cattle", text: "dairy branch · no precedent", cls: "grey", show: (s) => bell(s, 3.85, 4.0, 4.75, 4.9) },
  { id: "milk", text: "UNPRECEDENTED → escalate", cls: "stamp", show: (s) => bell(s, 4.05, 4.15, 4.75, 4.9), mobile: true },
];
// camera keyframes along the story index s (0 = hero, 1..5 chapters)
const KF = [
  { s: 0.0, p: [-0.8, 0.9, 14.5], t: [-1.6, 0.4, 0] },
  { s: 1.0, p: [-6.5, 1.6, 6.2], t: [-2.6, 0.5, 0] },
  { s: 1.75, p: [3.2, 1.1, 6.6], t: [3.4, 0.2, 0] },
  { s: 2.35, p: [-1.0, 6.0, 7.2], t: [-0.2, 2.6, -1.6] },
  { s: 3.4, p: [7.6, 0.2, 6.4], t: [4.4, -0.4, -0.6] },
  { s: 4.45, p: [2.6, -5.2, 8.8], t: [2.4, -2.5, 1.2] },
  { s: 5.2, p: [0.0, 1.4, 17.5], t: [0, 0, 0] },
];

const NOISE = /* glsl */ `
vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-.85373472095314*r;}
float snoise(vec3 v){const vec2 C=vec2(1./6.,1./3.);const vec4 D=vec4(0.,.5,1.,2.);vec3 i=floor(v+dot(v,C.yyy));vec3 x0=v-i+dot(i,C.xxx);
vec3 g=step(x0.yzx,x0.xyz);vec3 l=1.-g;vec3 i1=min(g.xyz,l.zxy);vec3 i2=max(g.xyz,l.zxy);vec3 x1=x0-i1+C.xxx;vec3 x2=x0-i2+C.yyy;vec3 x3=x0-D.yyy;
i=mod289(i);vec4 p=permute(permute(permute(i.z+vec4(0.,i1.z,i2.z,1.))+i.y+vec4(0.,i1.y,i2.y,1.))+i.x+vec4(0.,i1.x,i2.x,1.));
float n_=.142857142857;vec3 ns=n_*D.wyz-D.xzx;vec4 j=p-49.*floor(p*ns.z*ns.z);vec4 x_=floor(j*ns.z);vec4 y_=floor(j-7.*x_);
vec4 x=x_*ns.x+ns.yyyy;vec4 y=y_*ns.x+ns.yyyy;vec4 h=1.-abs(x)-abs(y);vec4 b0=vec4(x.xy,y.xy);vec4 b1=vec4(x.zw,y.zw);
vec4 s0=floor(b0)*2.+1.;vec4 s1=floor(b1)*2.+1.;vec4 sh=-step(h,vec4(0.));vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
vec3 p0=vec3(a0.xy,h.x);vec3 p1=vec3(a0.zw,h.y);vec3 p2=vec3(a1.xy,h.z);vec3 p3=vec3(a1.zw,h.w);
vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.);m=m*m;return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));}
`;

async function scene3d(getStoryIndex) {
  const canvas = $("#scene");
  let THREE, EffectComposer, RenderPass, UnrealBloomPass, OutputPass;
  try {
    THREE = await import("three");
    ({ EffectComposer } = await import("three/addons/postprocessing/EffectComposer.js"));
    ({ RenderPass } = await import("three/addons/postprocessing/RenderPass.js"));
    ({ UnrealBloomPass } = await import("three/addons/postprocessing/UnrealBloomPass.js"));
    ({ OutputPass } = await import("three/addons/postprocessing/OutputPass.js"));
  } catch (e) {
    console.warn("three.js failed to load; static fallback", e);
    return false;
  }
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: !isMobile, alpha: false, powerPreference: "high-performance" });
  } catch (e) {
    return false;
  }
  let dpr = Math.min(devicePixelRatio || 1, isMobile ? 1.5 : 2);
  renderer.setPixelRatio(dpr);
  renderer.setSize(innerWidth, innerHeight, false);
  renderer.setClearColor(0x05070b, 1);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x05070b, 0.035);
  const camera = new THREE.PerspectiveCamera(isMobile ? 62 : 45, innerWidth / innerHeight, 0.1, 200);
  camera.position.set(...KF[0].p);
  const world = new THREE.Group();
  scene.add(world);
  const V = (a) => new THREE.Vector3(...a);
  const C = (h) => new THREE.Color(h);

  /* ---------------- heat orb */
  const orbU = { uTime: { value: 0 }, uHeat: { value: 1 } };
  const orb = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1.25, isMobile ? 24 : 48),
    new THREE.ShaderMaterial({
      uniforms: orbU,
      vertexShader: NOISE + /* glsl */ `
        uniform float uTime; varying vec3 vN; varying vec3 vV; varying float vD;
        void main(){
          float d = snoise(normal*1.6 + vec3(uTime*0.35)) * 0.16 + snoise(normal*4.0 - vec3(uTime*0.6))*0.05;
          vD = d;
          vec3 p = position + normal * d;
          vec4 mv = modelViewMatrix * vec4(p,1.0);
          vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz);
          gl_Position = projectionMatrix * mv;
        }`,
      fragmentShader: /* glsl */ `
        uniform float uHeat; varying vec3 vN; varying vec3 vV; varying float vD;
        void main(){
          float f = pow(1.0 - max(dot(vN, vV), 0.0), 2.2);
          vec3 core = vec3(1.0, 0.86, 0.45);
          vec3 mid = vec3(1.0, 0.45, 0.08);
          vec3 rim = vec3(0.95, 0.16, 0.10);
          vec3 c = mix(core, mid, smoothstep(-0.1, 0.18, vD) );
          c = mix(c, rim, f);
          gl_FragColor = vec4(c * (1.25 + f*1.6) * uHeat, 1.0);
        }`,
    })
  );
  orb.position.copy(V(NODES.heatwave));
  world.add(orb);
  // halo sprite
  const haloTex = (() => {
    const c = document.createElement("canvas"); c.width = c.height = 256;
    const g = c.getContext("2d"); const gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    gr.addColorStop(0, "rgba(255,170,60,0.9)"); gr.addColorStop(0.25, "rgba(255,110,20,0.35)"); gr.addColorStop(1, "rgba(255,60,0,0)");
    g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  })();
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: haloTex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0.85 }));
  halo.scale.set(7.5, 7.5, 1);
  halo.position.copy(orb.position);
  world.add(halo);

  /* ---------------- nodes */
  const nodeMeshes = {};
  const ringGeo = new THREE.RingGeometry(0.24, 0.27, 48);
  const nodeGeo = new THREE.SphereGeometry(0.13, 20, 20);
  Object.entries(NODES).forEach(([id, p]) => {
    if (id === "heatwave") return;
    const g = new THREE.Group();
    const core = new THREE.Mesh(nodeGeo, new THREE.MeshBasicMaterial({ color: C("#ffb066"), transparent: true }));
    const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color: C("#ff922b"), transparent: true, opacity: 0.55, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
    g.add(core, ring);
    g.position.copy(V(p));
    world.add(g);
    nodeMeshes[id] = { g, core, ring, base: C("#ffb066") };
  });

  /* ---------------- edges (curves + tubes) */
  const GROUP_COLOR = { main: "#ff7a1a", wheat: "#ffc078", dairy: "#ffa94d", water: "#ff8787", direct: "#ffd43b", shelter: "#51cf66" };
  const edges = EDGES.map(([a, b, group], i) => {
    const pa = V(NODES[a]), pb = V(NODES[b]);
    const mid = pa.clone().lerp(pb, 0.5);
    const bend = group === "direct" ? 3.6 : 0.6;
    mid.y += (i % 2 ? 1 : -1) * 0.35 + (group === "direct" ? bend : 0);
    mid.z += (i % 3 - 1) * 0.5;
    const curve = new THREE.CatmullRomCurve3([pa, mid, pb]);
    const N = 96, samples = new Float32Array((N + 1) * 3);
    for (let k = 0; k <= N; k++) { const q = curve.getPoint(k / N); samples.set([q.x, q.y, q.z], k * 3); }
    const color = C(GROUP_COLOR[group]);
    const core = new THREE.Mesh(new THREE.TubeGeometry(curve, 64, 0.012, 6, false),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false }));
    const glow = new THREE.Mesh(new THREE.TubeGeometry(curve, 64, 0.05, 8, false),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.08, blending: THREE.AdditiveBlending, depthWrite: false }));
    world.add(core, glow);
    return { a, b, group, curve, samples, N, core, glow, color: color.clone(), cur: color.clone(), speed: 1, alpha: 1 };
  });

  /* ---------------- particle streams */
  const PCOUNT = isMobile ? 900 : 3200;
  const weights = edges.map((e) => (e.group === "main" ? 3 : e.group === "direct" ? 0.8 : e.group === "shelter" ? 1.2 : 1.4));
  const wsum = weights.reduce((a, b) => a + b, 0);
  const pEdge = new Uint16Array(PCOUNT), pT = new Float32Array(PCOUNT), pSpd = new Float32Array(PCOUNT), pJit = new Float32Array(PCOUNT * 3);
  for (let i = 0; i < PCOUNT; i++) {
    let r = Math.random() * wsum, k = 0;
    while (r > weights[k]) { r -= weights[k]; k++; }
    pEdge[i] = Math.min(k, edges.length - 1);
    pT[i] = Math.random();
    pSpd[i] = 0.06 + Math.random() * 0.12;
    pJit.set([(Math.random() - 0.5) * 0.12, (Math.random() - 0.5) * 0.12, (Math.random() - 0.5) * 0.12], i * 3);
  }
  const pPos = new Float32Array(PCOUNT * 3), pCol = new Float32Array(PCOUNT * 3), pSize = new Float32Array(PCOUNT);
  for (let i = 0; i < PCOUNT; i++) pSize[i] = 0.5 + Math.random() * 1.2;
  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute("position", new THREE.BufferAttribute(pPos, 3).setUsage(THREE.DynamicDrawUsage));
  pGeo.setAttribute("color", new THREE.BufferAttribute(pCol, 3).setUsage(THREE.DynamicDrawUsage));
  pGeo.setAttribute("size", new THREE.BufferAttribute(pSize, 1));
  const pointMat = (scale) => new THREE.ShaderMaterial({
    uniforms: { uScale: { value: scale * dpr }, uOpacity: { value: 1 } },
    vertexShader: /* glsl */ `attribute float size; attribute vec3 color; varying vec3 vC; uniform float uScale;
      void main(){ vC = color; vec4 mv = modelViewMatrix*vec4(position,1.); gl_PointSize = size*uScale*(10.0/-mv.z); gl_Position = projectionMatrix*mv; }`,
    fragmentShader: /* glsl */ `varying vec3 vC; uniform float uOpacity;
      void main(){ float d = length(gl_PointCoord-.5); float a = smoothstep(.5,.0,d); gl_FragColor = vec4(vC*a*1.6, a*uOpacity); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, vertexColors: false,
  });
  const particles = new THREE.Points(pGeo, pointMat(isMobile ? 2.4 : 2.0));
  particles.frustumCulled = false;
  pGeo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 60);
  world.add(particles);

  /* ---------------- dust (heat shimmer) */
  const DCOUNT = isMobile ? 500 : 1600;
  const dPos = new Float32Array(DCOUNT * 3), dCol = new Float32Array(DCOUNT * 3), dSize = new Float32Array(DCOUNT);
  for (let i = 0; i < DCOUNT; i++) {
    dPos.set([(Math.random() - 0.5) * 50, (Math.random() - 0.5) * 24, (Math.random() - 0.5) * 30 - 4], i * 3);
    const c = C(Math.random() < 0.8 ? "#ff9f5a" : "#8ab4ff").multiplyScalar(0.25 + Math.random() * 0.35);
    dCol.set([c.r, c.g, c.b], i * 3); dSize[i] = 0.3 + Math.random() * 0.8;
  }
  const dGeo = new THREE.BufferGeometry();
  dGeo.setAttribute("position", new THREE.BufferAttribute(dPos, 3));
  dGeo.setAttribute("color", new THREE.BufferAttribute(dCol, 3));
  dGeo.setAttribute("size", new THREE.BufferAttribute(dSize, 1));
  const dust = new THREE.Points(dGeo, pointMat(1.4));
  scene.add(dust);

  /* ---------------- heat terrain (fields below the graph) */
  const terrainU = { uTime: { value: 0 }, uHeat: { value: 0.6 }, uOrb: { value: V(NODES.heatwave) } };
  const terrain = new THREE.Mesh(
    new THREE.PlaneGeometry(80, 60, isMobile ? 90 : 180, isMobile ? 70 : 140),
    new THREE.ShaderMaterial({
      uniforms: terrainU, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: NOISE + /* glsl */ `uniform float uTime; varying vec2 vUv; varying float vH; varying vec3 vW;
        void main(){ vUv = uv; vec3 p = position; float h = snoise(vec3(p.xy*0.08, uTime*0.05))*1.4 + snoise(vec3(p.xy*0.25, uTime*0.1))*0.3;
          p.z += h; vH = h; vec4 w = modelMatrix*vec4(p,1.); vW = w.xyz; gl_Position = projectionMatrix*viewMatrix*w; }`,
      fragmentShader: /* glsl */ `uniform float uHeat; uniform vec3 uOrb; varying vec2 vUv; varying float vH; varying vec3 vW;
        void main(){ vec2 g = abs(fract(vUv*vec2(80.,60.))-.5)/fwidth(vUv*vec2(80.,60.)); float line = 1.-min(min(g.x,g.y),1.);
          float dist = length(vW.xz - uOrb.xz); float heat = exp(-dist*0.09)*uHeat;
          vec3 cold = vec3(0.10,0.16,0.28); vec3 hot = vec3(1.0,0.38,0.06);
          vec3 c = mix(cold, hot, clamp(heat*1.6 + vH*0.12,0.,1.));
          float fade = smoothstep(38.,6.,length(vW.xz));
          gl_FragColor = vec4(c*line*(0.35+heat), line*fade*0.55); }`,
    })
  );
  terrain.rotation.x = -Math.PI / 2;
  terrain.position.y = -5.2;
  scene.add(terrain);

  /* ---------------- hypothesis orbs (chapter 2) */
  const AGENTS = [
    { name: "weather", color: "#4dabf7", edge: 1, fate: "accept" },
    { name: "health", color: "#da77f2", edge: 4, fate: "accept" },
    { name: "agronomy", color: "#69db7c", edge: 7, fate: "defeat" },
  ];
  const hyp = AGENTS.map((a) => {
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.2, 24, 24), new THREE.MeshBasicMaterial({ color: C(a.color).multiplyScalar(2.2), transparent: true, opacity: 0 }));
    const r = new THREE.Mesh(new THREE.RingGeometry(0.34, 0.37, 48), new THREE.MeshBasicMaterial({ color: C(a.color), transparent: true, opacity: 0, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
    m.add(r); world.add(m);
    return { ...a, m, r };
  });
  const SH = isMobile ? 160 : 420;
  const shPos = new Float32Array(SH * 3), shVel = new Float32Array(SH * 3), shCol = new Float32Array(SH * 3), shSize = new Float32Array(SH);
  for (let i = 0; i < SH; i++) {
    const v = new THREE.Vector3().randomDirection().multiplyScalar(0.6 + Math.random() * 2.2);
    shVel.set([v.x, v.y, v.z], i * 3);
    const c = C(Math.random() < 0.5 ? "#69db7c" : "#ff6b6b"); shCol.set([c.r, c.g, c.b], i * 3); shSize[i] = 0.6 + Math.random() * 1.4;
  }
  const shGeo = new THREE.BufferGeometry();
  shGeo.setAttribute("position", new THREE.BufferAttribute(shPos, 3).setUsage(THREE.DynamicDrawUsage));
  shGeo.setAttribute("color", new THREE.BufferAttribute(shCol, 3));
  shGeo.setAttribute("size", new THREE.BufferAttribute(shSize, 1));
  const shards = new THREE.Points(shGeo, pointMat(2.6));
  shards.frustumCulled = false; shards.visible = false;
  shGeo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 60);
  world.add(shards);

  /* ---------------- post-processing */
  const composer = new EffectComposer(renderer);
  composer.setPixelRatio(dpr);
  composer.setSize(innerWidth, innerHeight);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth / (isMobile ? 2 : 1), innerHeight / (isMobile ? 2 : 1)), isMobile ? 0.9 : 1.15, 0.65, 0.12);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  /* ---------------- labels */
  const labelLayer = $("#labels");
  const labels = LABELS.filter((l) => !isMobile || l.mobile).map((l) => {
    const el = document.createElement("div");
    el.className = "nlabel " + (l.cls || ""); el.textContent = l.text; labelLayer.appendChild(el);
    return { ...l, el, v: new THREE.Vector3() };
  });

  /* ---------------- interaction */
  const mouse = { x: 0, y: 0, sx: 0, sy: 0 };
  addEventListener("pointermove", (e) => { mouse.x = e.clientX / innerWidth - 0.5; mouse.y = e.clientY / innerHeight - 0.5; }, { passive: true });
  const onResize = () => {
    camera.aspect = innerWidth / innerHeight;
    camera.fov = innerWidth < innerHeight ? 62 : 45;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight, false);
    composer.setSize(innerWidth, innerHeight);
  };
  addEventListener("resize", onResize);

  /* ---------------- frame loop */
  const camPos = V(KF[0].p), camTgt = V(KF[0].t), tmpP = new THREE.Vector3(), tmpT = new THREE.Vector3();
  const grey = C("#6c757d"), dimRed = C("#7a2a2a"), green = C("#51cf66");
  let sDamped = getStoryIndex(), last = performance.now(), time = 0, frames = 0, fpsT = 0, lowered = false;
  const mobileZ = innerWidth < innerHeight ? 1.45 : 1;

  function keyframe(s, outP, outT) {
    let i = 0; while (i < KF.length - 2 && s > KF[i + 1].s) i++;
    const a = KF[i], b = KF[i + 1];
    const t = smooth(clamp((s - a.s) / (b.s - a.s)));
    outP.set(lerp(a.p[0], b.p[0], t), lerp(a.p[1], b.p[1], t), lerp(a.p[2], b.p[2], t) * mobileZ);
    outT.set(lerp(a.t[0], b.t[0], t), lerp(a.t[1], b.t[1], t), lerp(a.t[2], b.t[2], t));
  }

  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (!reduceMotion) time += dt;
    // adaptive quality: drop DPR once if the first seconds are slow
    frames++; fpsT += dt;
    if (!lowered && fpsT > 2.5) { if (frames / fpsT < 40 && dpr > 1) { dpr = 1; renderer.setPixelRatio(1); composer.setPixelRatio(1); onResize(); } lowered = true; }

    const sTarget = getStoryIndex();
    sDamped += (sTarget - sDamped) * (reduceMotion ? 1 : 1 - Math.pow(0.0015, dt));
    const s = sDamped;

    const focusMain = bell(s, 0.75, 1.0, 1.9, 2.2);
    const hypOn = bell(s, 1.8, 2.05, 3.0, 3.2);
    const shatter = ramp(s, 2.3, 2.75);
    const memory = ramp(s, 2.95, 3.4);
    const greyOut = ramp(s, 3.95, 4.4);
    const outro = ramp(s, 4.75, 5.2);

    // camera
    keyframe(s, tmpP, tmpT);
    mouse.sx += (mouse.x - mouse.sx) * 0.05; mouse.sy += (mouse.y - mouse.sy) * 0.05;
    camPos.lerp(tmpP, reduceMotion ? 1 : 0.12); camTgt.lerp(tmpT, reduceMotion ? 1 : 0.12);
    camera.position.set(camPos.x + mouse.sx * 1.4, camPos.y - mouse.sy * 0.9, camPos.z);
    camera.lookAt(camTgt);
    world.rotation.y = outro * Math.sin(time * 0.15) * 0.25 + (1 - outro) * mouse.sx * 0.05;

    // orb
    orbU.uTime.value = time;
    orbU.uHeat.value = 1 + 0.08 * Math.sin(time * 2.0);
    orb.rotation.y = time * 0.1;
    halo.material.opacity = 0.75 + 0.15 * Math.sin(time * 1.3);
    terrainU.uTime.value = time;
    terrainU.uHeat.value = 0.55 + 0.25 * focusMain + 0.2 * outro;

    // edge state
    edges.forEach((e) => {
      let col = e.color, alpha = 0.55, glow = 0.07, speed = 1;
      if (e.group === "main") { alpha = 0.65 + 0.35 * focusMain; glow = 0.08 + 0.12 * focusMain + 0.18 * memory * (0.6 + 0.4 * Math.sin(time * 3 + e.N)); }
      if (e.group === "wheat") { alpha = 0.45 + 0.4 * hypOn * (1 - shatter); col = e.color.clone().lerp(dimRed, shatter); glow = 0.06 + 0.1 * hypOn * (1 - shatter); speed = 1 - 0.85 * shatter; }
      if (e.group === "dairy") { col = e.color.clone().lerp(grey, greyOut); alpha = 0.5 - 0.15 * greyOut; glow = 0.06 * (1 - greyOut); speed = 1 - greyOut; }
      if (e.group === "direct") { alpha = 0.28 - 0.18 * focusMain; glow = 0.03; }
      if (e.group === "water") { alpha = 0.4; }
      if (e.group === "shelter") { col = green; alpha = memory * 0.95; glow = memory * (0.18 + 0.1 * Math.sin(time * 4)); speed = memory; }
      const dimOthers = e.group !== "main" && e.group !== "shelter" ? 1 - 0.55 * focusMain : 1;
      e.cur.copy(col); e.speed = speed; e.alpha = alpha * dimOthers;
      e.core.material.color.copy(col); e.core.material.opacity = e.alpha;
      e.glow.material.color.copy(col); e.glow.material.opacity = glow * dimOthers;
    });

    // nodes
    Object.entries(nodeMeshes).forEach(([id, n]) => {
      let col = n.base, scale = 1;
      if (id.startsWith("dairy") || id === "milk") { col = n.base.clone().lerp(C("#3d434a"), greyOut); scale = 1 - 0.2 * greyOut; }
      if (id.startsWith("wheat") || id === "mandi_wheat") col = n.base.clone().lerp(dimRed, shatter);
      if (id === "worksite_cool_shelters") { col = green; scale = memory * (1.2 + 0.15 * Math.sin(time * 4)); }
      if (id === "heat_stress_illness") { col = C("#ff6b6b"); scale = 1.35 + 0.1 * Math.sin(time * 2.4); }
      if (id === "farm_laborers") scale = 1.15 + 0.25 * memory;
      n.core.material.color.copy(col).multiplyScalar(1.6);
      n.ring.material.color.copy(col);
      n.g.scale.setScalar(Math.max(scale, 0.0001));
      n.ring.lookAt(camera.position);
      n.ring.rotation.z += dt * 0.5;
    });

    // particles flow along curves
    const pos = pGeo.attributes.position.array, col = pGeo.attributes.color.array;
    for (let i = 0; i < PCOUNT; i++) {
      const e = edges[pEdge[i]];
      pT[i] += dt * pSpd[i] * e.speed * (e.group === "main" ? 1.2 : 1);
      if (pT[i] > 1) pT[i] -= 1;
      const f = Math.min(pT[i], 0.9999) * e.N, k = Math.floor(f), fr = f - k, k3 = k * 3, s3 = e.samples;
      const j = i * 3;
      pos[j] = s3[k3] + (s3[k3 + 3] - s3[k3]) * fr + pJit[j];
      pos[j + 1] = s3[k3 + 1] + (s3[k3 + 4] - s3[k3 + 1]) * fr + pJit[j + 1];
      pos[j + 2] = s3[k3 + 2] + (s3[k3 + 5] - s3[k3 + 2]) * fr + pJit[j + 2];
      // hotter toward the head of each edge, faded by edge alpha
      const heat = (0.55 + 0.6 * Math.sin(pT[i] * Math.PI)) * e.alpha;
      col[j] = e.cur.r * heat; col[j + 1] = e.cur.g * heat; col[j + 2] = e.cur.b * heat;
    }
    pGeo.attributes.position.needsUpdate = true;
    pGeo.attributes.color.needsUpdate = true;

    // dust rises like heat shimmer
    const dp = dGeo.attributes.position.array;
    if (!reduceMotion) {
      for (let i = 0; i < DCOUNT; i++) { dp[i * 3 + 1] += dt * (0.12 + (i % 7) * 0.02); if (dp[i * 3 + 1] > 12) dp[i * 3 + 1] = -12; }
      dGeo.attributes.position.needsUpdate = true;
    }

    // hypothesis orbs + shatter
    hyp.forEach((h, idx) => {
      const e = edges[h.edge];
      const travel = ramp(s, 1.85 + idx * 0.08, 2.3 + idx * 0.05);
      const q = e.curve.getPoint(0.15 + 0.7 * travel);
      const bob = Math.sin(time * 2 + idx) * 0.12;
      h.m.position.set(q.x, q.y + 0.55 + bob, q.z);
      const defeated = h.fate === "defeat" ? shatter : 0;
      h.m.material.opacity = hypOn * (1 - defeated);
      h.r.material.opacity = hypOn * (1 - defeated) * 0.8;
      h.r.lookAt(camera.position);
      h.m.scale.setScalar(1 + (h.fate === "accept" ? 0.3 * shatter : 0));
    });
    const agro = hyp[2];
    shards.visible = shatter > 0.001 && shatter < 0.999 && hypOn > 0.01;
    if (shards.visible) {
      const sp = shGeo.attributes.position.array, o = agro.m.position;
      for (let i = 0; i < SH; i++) { const k = shatter * (1.2 + shatter); sp[i * 3] = o.x + shVel[i * 3] * k; sp[i * 3 + 1] = o.y + shVel[i * 3 + 1] * k - shatter * shatter * 1.2; sp[i * 3 + 2] = o.z + shVel[i * 3 + 2] * k; }
      shGeo.attributes.position.needsUpdate = true;
      shards.material.uniforms.uOpacity.value = (1 - shatter) * hypOn;
    }

    composer.render();

    // labels (project after render so they track the camera)
    labels.forEach((l) => {
      const node = l.id === "heatwave" ? orb : nodeMeshes[l.id].g;
      l.v.setFromMatrixPosition(node.matrixWorld).project(camera);
      const vis = !!l.show(s) && l.v.z < 1;
      const x = (l.v.x * 0.5 + 0.5) * innerWidth, y = (-l.v.y * 0.5 + 0.5) * innerHeight;
      l.el.style.transform = `translate3d(${x + 14}px, ${y - 10}px, 0)`;
      l.el.classList.toggle("show", vis);
      if (l.defeatAt) l.el.classList.toggle("defeated", s > l.defeatAt);
    });

    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  return true;
}

/* ------------------------------------------------------------------ story index from scroll */
function storyIndexFn() {
  const secs = $$(".chapter");
  let tops = [], hs = [];
  const measure = () => { tops = secs.map((s) => s.offsetTop); hs = secs.map((s) => s.offsetHeight); };
  measure();
  addEventListener("resize", measure);
  addEventListener("load", measure);
  return () => {
    const mid = scrollY + innerHeight * 0.5;
    if (mid < tops[1]) return clamp((mid - innerHeight * 0.5) / Math.max(1, tops[1] - innerHeight * 0.5)) * 0.9;
    for (let i = secs.length - 1; i >= 1; i--) {
      if (mid >= tops[i]) return Math.min(secs.length - 1 + 0.35, i - 0.1 + clamp((mid - tops[i]) / hs[i]) * 1.0);
    }
    return 0;
  };
}

/* ------------------------------------------------------------------ boot */
async function boot() {
  splitWords();
  chrome();
  const loader = $("#loader"), pct = $("#loaderPct");
  let p = 0; const tick = setInterval(() => { p = Math.min(96, p + 7 + Math.random() * 9); pct.textContent = Math.round(p); }, 60);
  const finish = () => { clearInterval(tick); pct.textContent = "100"; loader.classList.add("done"); };
  const lenis = motionText();
  let ok = false;
  try {
    const gl = document.createElement("canvas").getContext("webgl2") || document.createElement("canvas").getContext("webgl");
    ok = !!gl && (await scene3d(storyIndexFn()));
  } catch (e) {
    console.warn("3D scene disabled:", e);
    ok = false;
  }
  if (!ok) document.documentElement.classList.add("no-webgl");
  setTimeout(finish, ok ? 350 : 0);
  window.__sentinel = { webgl: ok, lenis: !!lenis, reduceMotion, isMobile };
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
