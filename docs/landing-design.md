# Landing page design notes

## Concept: "Heat cascade observatory"

A single fixed WebGL stage sits behind a scroll story. The hero is a living heat orb (noise-displaced shader sphere plus additive halo) sitting over a contour "field" terrain. Particle streams flow out of the orb along a 3D copy of the real FalkorDB corridor. The node ids match the seed graph: `heatwave → fodder_jowar_vegetative → fodder → mandi_fodder → farm_laborers → heat_stress_illness`, plus the wheat, dairy and waterborne branches and the direct-exposure arc. Scrolling flies the camera between keyframes, and each chapter changes graph state rather than just showing text:

| Chapter | Scene change |
|---|---|
| 0 Hero | Whole graph, orb pulsing, mouse parallax |
| 1 The chain nobody sees | Camera rides the 5-hop corridor; the other branches dim; node labels are projected from 3D |
| 2 Agents propose, the graph disposes | Weather, health and agronomy hypothesis orbs travel onto paths; agronomy's wheat orb shatters into shards and the wheat branch cools to dim red (defeated) |
| 3 Memory that rewires | The `worksite_cool_shelters` node appears and its green edge pulses in; corridor glow thickens; counters tween 0.27 → 0.50 and 0.50 → 0.40 |
| 4 Refusal as a feature | The dairy branch desaturates to grey, its particles stop, and an `UNPRECEDENTED → escalate` stamp appears |
| 5 Built on FalkorDB | Camera pulls back, the graph slowly orbits, track cards and the CTA show |

Every number is taken from the project's own synthetic backtest output (`make backtest`, `bench/concurrency.py`, `pytest`).

**Stack.** Three.js r180 (vendored ES modules plus an import map, no build step), UnrealBloom and OutputPass post-processing, GSAP 3.13 with ScrollTrigger for text reveals and counters, and Lenis for smooth scroll. Scene state is driven by a damped "story index" computed from scroll position, so the 3D stays in sync without GSAP.

**Performance and access.**
- Particles are cut on mobile (3,200 → 900 flow particles, 1,600 → 500 dust), and DPR is capped at 1.5 on mobile and 2 on desktop.
- If the first 2.5 s average under 40 fps, DPR drops to 1 automatically. Bloom runs at half resolution on mobile.
- With `prefers-reduced-motion`, there's no Lenis, autonomous motion stops, and the counters show their final values.
- If WebGL is unavailable or three.js fails to load, a static gradient plus an SVG corridor is shown instead.
- All paths are relative, so the same file works at `/` (FastAPI) and under `/cascade-sentinel/` (GitHub Pages).

## References studied (fetched while designing)

1. **The Blue Desert** (Adoratorio, Awwwards case study), Three.js + GSAP climate data scrollytelling. Takeaways: one continuous scene with meticulous camera moves, InstancedMesh and shader work, and a double optimisation pass for desktop and mobile. https://www.awwwards.com/the-blue-desert.html
2. **Building Cerebrium: Making Serverless Infrastructure Tangible** (Codrops, 2026). It makes an abstract system tangible with animated network paths, particles and EffectComposer bloom. It also explains why they shipped WebGL over WebGPU for predictable start-up, which is the same choice made here. https://tympanus.net/codrops/2026/07/23/building-cerebrium-making-serverless-infrastructure-tangible/
3. **Codrops: Three.js and particles articles** (Trionn's GSAP + Three.js + Lenis architecture; Unseen Studio's particle experiment). The pattern copied here is one render loop that owns scroll, smoothing and WebGL. https://tympanus.net/codrops/?s=particles+three.js
4. **three.js `webgl_postprocessing_unreal_bloom` example**, the bloom pipeline (RenderPass → UnrealBloomPass → OutputPass). https://threejs.org/examples/webgl_postprocessing_unreal_bloom.html
5. **3d-force-graph "emit particles" example** (vasturiano), particles travelling along graph links as the visual metaphor for propagation. https://github.com/vasturiano/3d-force-graph/blob/master/example/emit-particles/index.html

Also checked: **Tide** (https://www.tide.co/), which contributed clean CTA hierarchy and calm product copy. Dribbble search pages block non-browser fetches, so nothing there was used as a reference.

## Screenshots

`docs/screenshots/landing-1440-*.png` (desktop chapters 0–6) and `landing-390-*.png` (mobile). They were rendered with headless Chrome on SwiftShader, so expect much higher fps on a real GPU.
