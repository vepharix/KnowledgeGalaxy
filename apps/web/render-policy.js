(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.KnowledgeGalaxyRenderPolicy = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  function chooseRenderPolicy(nodeCount) {
    if (!Number.isInteger(nodeCount) || nodeCount < 0) throw new Error("nodeCount must be a nonnegative integer");
    if (nodeCount <= 2000) return { maxEdges: 20000, minimumRelatedness: 0.35, labelBudget: 48, picking: "cpu-on-demand" };
    if (nodeCount <= 20000) return { maxEdges: 4000, minimumRelatedness: 0.72, labelBudget: 16, picking: "cpu-on-click" };
    return { maxEdges: 1500, minimumRelatedness: 0.88, labelBudget: 6, picking: "gpu-id-buffer-required" };
  }

  function selectRelations(snapshot, policy) {
    const relations = [];
    for (const relation of snapshot.R || []) {
      if (relation.value >= policy.minimumRelatedness) relations.push({ type: "R", left: relation.left, right: relation.right, strength: relation.value });
    }
    for (const relation of snapshot.D || []) relations.push({ type: "D", left: relation.foundation, right: relation.dependent, strength: relation.value * 0.82 });
    return relations.sort((left, right) => right.strength - left.strength).slice(0, policy.maxEdges);
  }

  return { chooseRenderPolicy, selectRelations };
});
