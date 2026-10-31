const assert = require("node:assert/strict");
const test = require("node:test");
const { chooseRenderPolicy, selectRelations } = require("../apps/web/render-policy.js");

test("render policy reduces edges and labels as node count grows", () => {
  const small = chooseRenderPolicy(30);
  const medium = chooseRenderPolicy(20000);
  const large = chooseRenderPolicy(50000);
  assert.ok(small.maxEdges > medium.maxEdges);
  assert.ok(medium.maxEdges > large.maxEdges);
  assert.ok(small.labelBudget > medium.labelBudget);
  assert.ok(medium.labelBudget > large.labelBudget);
  assert.equal(large.picking, "gpu-id-buffer-required");
});

test("relationship selection is strength ordered and capped", () => {
  const snapshot = { R: [{ left: "a", right: "b", value: 0.9 }, { left: "a", right: "c", value: 0.4 }], D: [{ foundation: "b", dependent: "c", value: 1 }] };
  const selected = selectRelations(snapshot, { maxEdges: 1, minimumRelatedness: 0.5 });
  assert.equal(selected.length, 1);
  assert.deepEqual(selected[0], { type: "R", left: "a", right: "b", strength: 0.9 });
});
