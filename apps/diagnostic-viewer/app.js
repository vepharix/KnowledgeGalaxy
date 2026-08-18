(() => {
  "use strict";

  const snapshot = window.KNOWLEDGE_GALAXY_SNAPSHOT;
  const canvas = document.getElementById("view");
  const context = canvas.getContext("2d");
  const details = document.getElementById("details");
  if (!snapshot) {
    details.innerHTML = "<h2>尚未生成演示数据</h2><div>请先在项目目录运行 <code>python -m knowledge_galaxy build</code>，然后重新打开本页面。</div>";
    return;
  }
  const showR = document.getElementById("show-r");
  const showD = document.getElementById("show-d");
  const showHColor = document.getElementById("show-h-color");
  const rThreshold = document.getElementById("r-threshold");
  const rValue = document.getElementById("r-value");
  const nodeById = new Map(snapshot.nodes.map((node) => [node.id, node]));
  const palette = ["#62b6ff", "#f28e74", "#77d49b", "#c598ff", "#f0ce67", "#66d5d0", "#ed83bd", "#a9be6c"];
  const roots = hierarchyRoots(snapshot.H);
  const familyById = hierarchyFamilies(snapshot.hierarchyMembers, roots);

  const camera = { yaw: -0.65, pitch: 0.38, zoom: 1, panX: 0, panY: 0 };
  const pointer = { down: false, mode: "orbit", x: 0, y: 0, moved: false };
  let projected = [];
  let selectedId = null;
  let hoveredId = null;

  function hierarchyRoots(edges) {
    const broader = new Set(edges.map((edge) => edge.broader));
    const narrower = new Set(edges.map((edge) => edge.narrower));
    return [...broader].filter((id) => !narrower.has(id)).sort();
  }

  function hierarchyFamilies(memberSets, rootIds) {
    const result = new Map();
    for (const node of snapshot.nodes) {
      const memberships = rootIds.filter((root) => root === node.id || (memberSets[root] || []).includes(node.id));
      result.set(node.id, memberships);
    }
    return result;
  }

  function resize() {
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(innerWidth * ratio);
    canvas.height = Math.round(innerHeight * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    render();
  }

  function rotate(point) {
    const cosY = Math.cos(camera.yaw);
    const sinY = Math.sin(camera.yaw);
    const x1 = point.x * cosY - point.z * sinY;
    const z1 = point.x * sinY + point.z * cosY;
    const cosP = Math.cos(camera.pitch);
    const sinP = Math.sin(camera.pitch);
    return { x: x1, y: point.y * cosP - z1 * sinP, z: point.y * sinP + z1 * cosP };
  }

  function project(node) {
    const rotated = rotate(node.coordinate);
    const base = Math.min(innerWidth, innerHeight) * 0.075 * camera.zoom;
    const perspective = 1 / Math.max(0.45, 1 + rotated.z * 0.035);
    return {
      node,
      x: innerWidth / 2 + camera.panX + rotated.x * base * perspective,
      y: innerHeight / 2 + camera.panY - rotated.y * base * perspective,
      z: rotated.z,
      radius: nodeRadius(node) * Math.sqrt(perspective),
    };
  }

  function nodeRadius(node) {
    return 7 + 8 * node.connectivityNormalized;
  }

  function nodeColor(node) {
    if (!showHColor.checked) return "#9dcbea";
    const families = familyById.get(node.id) || [];
    if (!families.length) return "#a7b3ba";
    return palette[roots.indexOf(families[0]) % palette.length];
  }

  function drawLine(left, right, color, alpha, width) {
    context.beginPath();
    context.moveTo(left.x, left.y);
    context.lineTo(right.x, right.y);
    context.strokeStyle = color;
    context.globalAlpha = alpha;
    context.lineWidth = width;
    context.stroke();
    context.globalAlpha = 1;
  }

  function drawArrow(left, right, strength) {
    drawLine(left, right, "#f0a45d", 0.22 + strength * 0.5, 0.7 + strength * 1.8);
    const angle = Math.atan2(right.y - left.y, right.x - left.x);
    const tipDistance = right.radius + 2;
    const tipX = right.x - Math.cos(angle) * tipDistance;
    const tipY = right.y - Math.sin(angle) * tipDistance;
    const size = 4 + strength * 4;
    context.beginPath();
    context.moveTo(tipX, tipY);
    context.lineTo(tipX - Math.cos(angle - 0.55) * size, tipY - Math.sin(angle - 0.55) * size);
    context.lineTo(tipX - Math.cos(angle + 0.55) * size, tipY - Math.sin(angle + 0.55) * size);
    context.closePath();
    context.fillStyle = "#f0a45d";
    context.globalAlpha = 0.45 + strength * 0.45;
    context.fill();
    context.globalAlpha = 1;
  }

  function render() {
    context.clearRect(0, 0, innerWidth, innerHeight);
    const glow = context.createRadialGradient(innerWidth / 2, innerHeight / 2, 0, innerWidth / 2, innerHeight / 2, Math.max(innerWidth, innerHeight) * 0.7);
    glow.addColorStop(0, "#102432");
    glow.addColorStop(1, "#050b10");
    context.fillStyle = glow;
    context.fillRect(0, 0, innerWidth, innerHeight);

    projected = snapshot.nodes.map(project);
    const screenById = new Map(projected.map((item) => [item.node.id, item]));
    if (showR.checked) {
      const threshold = Number(rThreshold.value);
      for (const relation of snapshot.R) {
        if (relation.value < threshold) continue;
        drawLine(screenById.get(relation.left), screenById.get(relation.right), "#80bfff", 0.08 + relation.value * 0.32, 0.5 + relation.value * 1.5);
      }
    }
    if (showD.checked) {
      for (const edge of snapshot.D) drawArrow(screenById.get(edge.foundation), screenById.get(edge.dependent), edge.value);
    }

    for (const item of [...projected].sort((left, right) => left.z - right.z)) {
      const active = item.node.id === hoveredId || item.node.id === selectedId;
      context.beginPath();
      context.arc(item.x, item.y, item.radius + (active ? 3 : 0), 0, Math.PI * 2);
      context.fillStyle = nodeColor(item.node);
      context.globalAlpha = active ? 1 : 0.88;
      context.shadowColor = nodeColor(item.node);
      context.shadowBlur = active ? 18 : 7;
      context.fill();
      context.shadowBlur = 0;
      context.globalAlpha = 1;
      if (active) {
        context.fillStyle = "#eef8fb";
        context.font = "12px system-ui";
        context.fillText(item.node.name, item.x + item.radius + 7, item.y + 4);
      }
    }
  }

  function hitTest(x, y) {
    return [...projected]
      .reverse()
      .find((item) => Math.hypot(x - item.x, y - item.y) <= item.radius + 5)?.node.id || null;
  }

  function showDetails(id) {
    if (!id) return;
    const node = nodeById.get(id);
    const families = familyById.get(id) || [];
    const format = (value) => Number(value).toFixed(4);
    details.innerHTML = `<h2>${escapeHtml(node.name)}</h2><div>${escapeHtml(node.description)}</div><dl>
      <dt>id</dt><dd>${escapeHtml(node.id)}</dd>
      <dt>x / y / z</dt><dd>${format(node.coordinate.x)} / ${format(node.coordinate.y)} / ${format(node.coordinate.z)}</dd>
      <dt>dependency depth</dt><dd>${format(node.dependencyDepthRaw)} (${format(node.dependencyDepthNormalized)})</dd>
      <dt>target / actual radius</dt><dd>${format(node.targetRadius)} / ${format(node.actualRadius)}</dd>
      <dt>connectivity</dt><dd>${format(node.connectivityRaw)} (${format(node.connectivityNormalized)})</dd>
      <dt>H color families</dt><dd>${families.length ? families.map(escapeHtml).join(", ") : "none"}</dd>
    </dl>`;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
  }

  canvas.addEventListener("pointerdown", (event) => {
    pointer.down = true;
    pointer.mode = event.button === 2 || event.shiftKey ? "pan" : "orbit";
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    pointer.moved = false;
    canvas.classList.add("dragging");
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (pointer.down) {
      const dx = event.clientX - pointer.x;
      const dy = event.clientY - pointer.y;
      pointer.moved ||= Math.abs(dx) + Math.abs(dy) > 2;
      if (pointer.mode === "pan") {
        camera.panX += dx;
        camera.panY += dy;
      } else {
        camera.yaw += dx * 0.008;
        camera.pitch = Math.max(-1.45, Math.min(1.45, camera.pitch + dy * 0.008));
      }
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      render();
      return;
    }
    hoveredId = hitTest(event.clientX, event.clientY);
    if (hoveredId) showDetails(hoveredId);
    render();
  });
  canvas.addEventListener("pointerup", (event) => {
    if (!pointer.moved) {
      selectedId = hitTest(event.clientX, event.clientY);
      if (selectedId) showDetails(selectedId);
    }
    pointer.down = false;
    canvas.classList.remove("dragging");
    render();
  });
  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    camera.zoom = Math.max(0.25, Math.min(5, camera.zoom * Math.exp(-event.deltaY * 0.001)));
    render();
  }, { passive: false });
  canvas.addEventListener("contextmenu", (event) => event.preventDefault());
  for (const control of [showR, showD, showHColor]) control.addEventListener("change", render);
  rThreshold.addEventListener("input", () => { rValue.value = Number(rThreshold.value).toFixed(2); render(); });
  window.addEventListener("resize", resize);
  resize();
})();
