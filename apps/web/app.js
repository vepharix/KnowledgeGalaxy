(() => {
  "use strict";

  const POINT_VERTEX = `#version 300 es
    precision highp float;
    layout(location=0) in vec3 aPosition;
    layout(location=1) in vec3 aColor;
    layout(location=2) in float aBrightness;
    layout(location=3) in float aSemantic;
    uniform mat3 uRotation;
    uniform float uAspect;
    uniform float uZoom;
    uniform float uPixelRatio;
    out vec3 vColor;
    out float vBrightness;
    out float vSemantic;
    void main() {
      vec3 point = uRotation * aPosition;
      float perspective = 2.35 / max(1.25, 3.1 - point.z);
      gl_Position = vec4(point.x * uZoom * perspective / uAspect, point.y * uZoom * perspective, point.z * 0.12, 1.0);
      gl_PointSize = clamp((aSemantic > 0.5 ? 5.0 + 15.0 * aBrightness : 1.0 + 1.8 * aBrightness) * perspective * uPixelRatio, 1.0, 52.0);
      vColor = aColor;
      vBrightness = aBrightness;
      vSemantic = aSemantic;
    }`;
  const POINT_FRAGMENT = `#version 300 es
    precision highp float;
    in vec3 vColor;
    in float vBrightness;
    in float vSemantic;
    out vec4 outputColor;
    void main() {
      float distance = length(gl_PointCoord - vec2(0.5)) * 2.0;
      if (distance > 1.0) discard;
      float halo = exp(-distance * distance * (vSemantic > 0.5 ? 4.0 : 7.0));
      float core = smoothstep(0.28, 0.0, distance);
      vec3 color = mix(vColor, vec3(1.0), core * 0.9);
      float alpha = halo * (vSemantic > 0.5 ? 0.36 + 0.62 * vBrightness : 0.28);
      outputColor = vec4(color, alpha);
    }`;
  const LINE_VERTEX = `#version 300 es
    precision highp float;
    layout(location=0) in vec3 aPosition;
    layout(location=1) in vec4 aColor;
    uniform mat3 uRotation;
    uniform float uAspect;
    uniform float uZoom;
    out vec4 vColor;
    void main() {
      vec3 point = uRotation * aPosition;
      float perspective = 2.35 / max(1.25, 3.1 - point.z);
      gl_Position = vec4(point.x * uZoom * perspective / uAspect, point.y * uZoom * perspective, point.z * 0.12, 1.0);
      vColor = aColor;
    }`;
  const LINE_FRAGMENT = `#version 300 es
    precision highp float;
    in vec4 vColor;
    out vec4 outputColor;
    void main() { outputColor = vColor; }`;

  const canvas = document.getElementById("galaxy");
  const selectedPanel = document.getElementById("selected");
  const gl = canvas.getContext("webgl2", { antialias: true, alpha: true, powerPreference: "high-performance" });
  if (!gl) {
    selectedPanel.innerHTML = "<h2>无法启动 WebGL2</h2><div>当前浏览器或显卡没有提供 WebGL2。本页面不会退回逐节点 DOM 绘制，以免在大图上产生错误的性能预期。</div>";
    return;
  }
  const snapshot = window.KNOWLEDGE_GALAXY_SNAPSHOT;
  if (!snapshot) {
    selectedPanel.innerHTML = "<h2>尚未生成星图数据</h2><div>请先运行数学构建，再刷新页面。</div>";
    return;
  }

  const requestedCount = Number(new URLSearchParams(location.search).get("benchmark") || 0);
  const benchmarkCount = Number.isFinite(requestedCount) ? Math.max(0, Math.min(100000, Math.floor(requestedCount))) : 0;
  const synthetic = benchmarkCount >= 1000;
  const sourceNodes = synthetic ? createBenchmarkNodes(benchmarkCount) : snapshot.nodes;
  const policy = window.KnowledgeGalaxyRenderPolicy.chooseRenderPolicy(sourceNodes.length);
  const sourceRelations = synthetic ? [] : window.KnowledgeGalaxyRenderPolicy.selectRelations(snapshot, policy);
  const scene = prepareScene(sourceNodes, sourceRelations, synthetic);
  const background = createBackgroundStars(Math.min(2400, Math.max(1200, Math.floor(sourceNodes.length * 0.16))));
  const camera = { yaw: -0.58, pitch: 0.32, zoom: 1 };
  const pointer = { down: false, x: 0, y: 0, moved: false };
  let lastFrame = performance.now();
  let fpsAverage = 60;

  const pointProgram = createProgram(POINT_VERTEX, POINT_FRAGMENT);
  const lineProgram = createProgram(LINE_VERTEX, LINE_FRAGMENT);
  const pointGeometry = uploadPointGeometry(scene.nodes);
  const backgroundGeometry = uploadPointGeometry(background);
  const lineGeometry = uploadLineGeometry(scene.relations, scene.nodeById);
  const labelLayer = document.getElementById("labels");
  const labelNodes = synthetic ? [] : [...scene.nodes].sort((left, right) => right.connectivity - left.connectivity).slice(0, policy.labelBudget);
  const labelElements = new Map(labelNodes.map((node) => {
    const element = document.createElement("span");
    element.className = "star-label";
    element.textContent = node.name;
    labelLayer.appendChild(element);
    return [node.id, element];
  }));

  document.getElementById("node-count").textContent = sourceNodes.length.toLocaleString();
  document.getElementById("edge-count").textContent = scene.relations.length.toLocaleString();
  document.getElementById("label-count").textContent = labelNodes.length.toLocaleString();
  if (synthetic) {
    const mode = document.getElementById("mode-label");
    mode.textContent = `${sourceNodes.length.toLocaleString()} synthetic points · render benchmark only`;
    mode.classList.add("benchmark");
    selectedPanel.innerHTML = "<h2>合成渲染测试</h2><div>这些点只用于测量 WebGL 绘制能力，不是数学节点，也不进入 H、D、R 或布局计算。</div>";
  }

  function prepareScene(nodes, relations, isSynthetic) {
    const maximumRadius = nodes.reduce(
      (maximum, node) => Math.max(maximum, Math.hypot(node.coordinate.x, node.coordinate.y, node.coordinate.z)),
      1e-6,
    );
    const normalized = nodes.map((node, index) => ({
      id: node.id || `benchmark-${index}`,
      name: node.name || `Benchmark ${index}`,
      x: node.coordinate.x / maximumRadius,
      y: node.coordinate.y / maximumRadius,
      z: node.coordinate.z / maximumRadius,
      depth: Number(node.dependencyDepthNormalized || 0),
      connectivity: Number(node.connectivityNormalized || 0),
      original: node,
      synthetic: isSynthetic,
    }));
    return { nodes: normalized, relations, nodeById: new Map(normalized.map((node) => [node.id, node])) };
  }

  function createBenchmarkNodes(count) {
    let seed = 0x6d2b79f5;
    const random = () => {
      seed = Math.imul(seed ^ (seed >>> 15), seed | 1);
      seed ^= seed + Math.imul(seed ^ (seed >>> 7), seed | 61);
      return ((seed ^ (seed >>> 14)) >>> 0) / 4294967296;
    };
    return Array.from({ length: count }, (_, index) => {
      const radius = Math.sqrt(random());
      const angle = (index % 5) * Math.PI * 0.4 + radius * 8.5 + (random() - 0.5) * 0.42;
      return {
        id: `benchmark-${index}`,
        name: `Benchmark ${index}`,
        description: "Synthetic performance point",
        coordinate: { x: Math.cos(angle) * radius, y: (random() - 0.5) * (0.08 + 0.18 * (1 - radius)), z: Math.sin(angle) * radius },
        dependencyDepthNormalized: radius,
        connectivityNormalized: Math.pow(random(), 5),
      };
    });
  }

  function createBackgroundStars(count) {
    let seed = 0x1234abcd;
    const random = () => ((seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0) / 4294967296);
    return Array.from({ length: count }, (_, index) => ({
      id: `background-${index}`,
      name: "",
      x: (random() - 0.5) * 3.8,
      y: (random() - 0.5) * 2.3,
      z: -0.8 + random() * 1.2,
      depth: random(),
      connectivity: random() * 0.05,
      background: true,
    }));
  }

  function uploadPointGeometry(nodes) {
    const values = new Float32Array(nodes.length * 8);
    nodes.forEach((node, index) => {
      const color = node.background ? [0.32, 0.5, 0.68] : depthColor(node.depth);
      values.set([node.x, node.y, node.z, color[0], color[1], color[2], node.connectivity, node.background ? 0 : 1], index * 8);
    });
    const vao = gl.createVertexArray();
    gl.bindVertexArray(vao);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, values, gl.STATIC_DRAW);
    for (const [location, size, offset] of [[0, 3, 0], [1, 3, 12], [2, 1, 24], [3, 1, 28]]) {
      gl.enableVertexAttribArray(location);
      gl.vertexAttribPointer(location, size, gl.FLOAT, false, 32, offset);
    }
    gl.bindVertexArray(null);
    return { vao, count: nodes.length };
  }

  function uploadLineGeometry(relations, nodeById) {
    const values = [];
    for (const relation of relations) {
      const left = nodeById.get(relation.left), right = nodeById.get(relation.right);
      if (!left || !right) continue;
      const color = relation.type === "D" ? [1, 0.52, 0.2] : [0.24, 0.66, 1];
      const alpha = 0.08 + 0.34 * relation.strength;
      values.push(left.x, left.y, left.z, ...color, alpha, right.x, right.y, right.z, ...color, alpha);
    }
    const vao = gl.createVertexArray();
    gl.bindVertexArray(vao);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(values), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 28, 0);
    gl.enableVertexAttribArray(1);
    gl.vertexAttribPointer(1, 4, gl.FLOAT, false, 28, 12);
    gl.bindVertexArray(null);
    return { vao, count: values.length / 7 };
  }

  function depthColor(depth) {
    const t = Math.max(0, Math.min(1, depth));
    return [1 - 0.58 * t, 0.73 + 0.12 * t, 0.42 + 0.58 * t];
  }

  function createProgram(vertexSource, fragmentSource) {
    const program = gl.createProgram();
    const compile = (type, source) => {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
      return shader;
    };
    gl.attachShader(program, compile(gl.VERTEX_SHADER, vertexSource));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragmentSource));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    return program;
  }

  function rotationMatrix() {
    const cy = Math.cos(camera.yaw), sy = Math.sin(camera.yaw), cp = Math.cos(camera.pitch), sp = Math.sin(camera.pitch);
    return new Float32Array([cy, -sp * sy, cp * sy, 0, cp, sp, -sy, -sp * cy, cp * cy]);
  }

  function setCameraUniforms(program) {
    gl.useProgram(program);
    gl.uniformMatrix3fv(gl.getUniformLocation(program, "uRotation"), false, rotationMatrix());
    gl.uniform1f(gl.getUniformLocation(program, "uAspect"), canvas.width / canvas.height);
    gl.uniform1f(gl.getUniformLocation(program, "uZoom"), camera.zoom);
    const location = gl.getUniformLocation(program, "uPixelRatio");
    if (location !== null) gl.uniform1f(location, Math.min(devicePixelRatio || 1, Math.max(0.55, 1.3 - sourceNodes.length / 50000)));
  }

  function draw() {
    resizeCanvas();
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.disable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    setCameraUniforms(pointProgram);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.bindVertexArray(backgroundGeometry.vao);
    gl.drawArrays(gl.POINTS, 0, backgroundGeometry.count);
    if (document.getElementById("show-edges").checked && lineGeometry.count) {
      setCameraUniforms(lineProgram);
      gl.bindVertexArray(lineGeometry.vao);
      gl.drawArrays(gl.LINES, 0, lineGeometry.count);
    }
    setCameraUniforms(pointProgram);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    gl.bindVertexArray(pointGeometry.vao);
    gl.drawArrays(gl.POINTS, 0, pointGeometry.count);
    gl.bindVertexArray(null);
    updateLabels();
  }

  function resizeCanvas() {
    const ratio = Math.min(devicePixelRatio || 1, 2);
    const width = Math.round(innerWidth * ratio), height = Math.round(innerHeight * ratio);
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
  }

  function rotatePoint(node) {
    const cy = Math.cos(camera.yaw), sy = Math.sin(camera.yaw);
    const x = node.x * cy - node.z * sy, z1 = node.x * sy + node.z * cy;
    const cp = Math.cos(camera.pitch), sp = Math.sin(camera.pitch);
    return { x, y: node.y * cp - z1 * sp, z: node.y * sp + z1 * cp };
  }

  function project(node) {
    const point = rotatePoint(node), perspective = 2.35 / Math.max(1.25, 3.1 - point.z);
    return { x: innerWidth * 0.5 + point.x * camera.zoom * perspective * innerHeight * 0.5, y: innerHeight * 0.5 - point.y * camera.zoom * perspective * innerHeight * 0.5, z: point.z };
  }

  function updateLabels() {
    const visible = document.getElementById("show-labels").checked;
    for (const node of labelNodes) {
      const element = labelElements.get(node.id), screen = project(node);
      const onScreen = visible && screen.x > -80 && screen.x < innerWidth + 40 && screen.y > -30 && screen.y < innerHeight + 30;
      element.style.display = onScreen ? "block" : "none";
      if (onScreen) {
        element.style.left = `${screen.x}px`;
        element.style.top = `${screen.y}px`;
        element.style.opacity = String(Math.max(0.28, Math.min(1, 0.56 + screen.z * 0.32)));
      }
    }
  }

  function pickNode(x, y) {
    if (synthetic && sourceNodes.length > 20000) return null;
    let best = null, distance = 14;
    for (const node of scene.nodes) {
      const screen = project(node), candidate = Math.hypot(x - screen.x, y - screen.y);
      if (candidate < distance) { best = node; distance = candidate; }
    }
    return best;
  }

  function showNode(node) {
    if (!node || node.synthetic) return;
    const original = node.original;
    const number = (value) => Number(value || 0).toFixed(4);
    selectedPanel.innerHTML = `<h2>${escapeHtml(original.nameZh || original.name)}</h2><div>${escapeHtml(original.description)}</div><dl><dt>ID</dt><dd>${escapeHtml(original.id)}</dd><dt>依赖深度</dt><dd>${number(original.dependencyDepthNormalized)}</dd><dt>连接度</dt><dd>${number(original.connectivityNormalized)}</dd><dt>目标 / 实际半径</dt><dd>${number(original.targetRadius)} / ${number(original.actualRadius)}</dd></dl>`;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
  }

  canvas.addEventListener("pointerdown", (event) => {
    pointer.down = true; pointer.moved = false; pointer.x = event.clientX; pointer.y = event.clientY;
    canvas.classList.add("dragging"); canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!pointer.down) return;
    const dx = event.clientX - pointer.x, dy = event.clientY - pointer.y;
    pointer.moved ||= Math.abs(dx) + Math.abs(dy) > 2;
    camera.yaw -= dx * 0.006;
    camera.pitch = Math.max(-1.42, Math.min(1.42, camera.pitch + dy * 0.006));
    pointer.x = event.clientX; pointer.y = event.clientY;
  });
  canvas.addEventListener("pointerup", (event) => {
    if (!pointer.moved) showNode(pickNode(event.clientX, event.clientY));
    pointer.down = false; canvas.classList.remove("dragging");
  });
  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    camera.zoom = Math.max(0.35, Math.min(4.5, camera.zoom * Math.exp(-event.deltaY * 0.001)));
  }, { passive: false });
  document.getElementById("reset-view").addEventListener("click", () => Object.assign(camera, { yaw: -0.58, pitch: 0.32, zoom: 1 }));

  function animate(time) {
    const elapsed = Math.min(50, time - lastFrame);
    lastFrame = time;
    fpsAverage = fpsAverage * 0.94 + (elapsed > 0 ? 1000 / elapsed : 60) * 0.06;
    if (document.getElementById("auto-rotate").checked && !pointer.down) camera.yaw += elapsed * 0.00004;
    draw();
    document.getElementById("fps").textContent = `${Math.round(fpsAverage)} fps`;
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
})();
