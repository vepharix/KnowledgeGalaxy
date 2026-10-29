/* Evidence presentation belongs only to the diagnostic app. No graph calculation. */
window.showFormalEvidence = function (container, node, snapshot) {
  const alignment = snapshot.formalAlignment;
  if (!alignment) return;
  const semanticNode = alignment.nodes.find((item) => item.id === node.id);
  const section = document.createElement("section");
  section.className = "formal-evidence";
  const text = (parent, tag, value) => {
    const element = document.createElement(tag);
    element.textContent = value;
    parent.appendChild(element);
    return element;
  };
  const kinds = { field: "领域", concept: "概念", result: "结果" };
  text(section, "h3", `Lean 形式证据 · ${kinds[node.semanticKind] || node.semanticKind}`);
  if (semanticNode) text(section, "p", semanticNode.scope_note);
  const mappings = alignment.mappings.filter((item) => item.node_id === node.id);
  if (!mappings.length) text(section, "p", "知识范围节点，不强制对应单个 Lean 声明。");
  const roles = {
    defining_expression: "定义性表达", variant: "具体形式", value_operator: "取值算子",
    related_result: "相关结果", application: "应用", context: "上下文条件",
  };
  for (const mapping of mappings) {
    const declaration = alignment.declarations.find((item) => item.id === mapping.declaration_id);
    const entry = document.createElement("details");
    text(entry, "summary", `${mapping.declaration_id} · ${roles[mapping.role] || mapping.role}`);
    text(entry, "code", mapping.expression);
    text(entry, "p", `条件：${mapping.conditions.join("；")}`);
    if (mapping.caveats.length) text(entry, "p", `边界：${mapping.caveats.join("；")}`);
    text(entry, "p", `${mapping.review_status} · ${mapping.review_note}`);
    if (declaration && /^https:\/\/github\.com\/leanprover-community\/mathlib4\/blob\/[0-9a-f]{40}\//.test(declaration.url)) {
      const link = text(entry, "a", "查看固定版本源码");
      link.href = declaration.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
    section.appendChild(entry);
  }
  text(section, "p", "已核对源码与语义条件；本项目尚未运行 Lean 编译验证。");
  container.appendChild(section);
};
