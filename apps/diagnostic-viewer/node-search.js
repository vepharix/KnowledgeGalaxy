/* Search affects selection/camera only, never source relations or coordinates. */
window.installNodeSearch = function (nodes, input, select, onSelect) {
  const matches = () => {
    const query = input.value.trim().toLocaleLowerCase();
    return nodes.filter(node => [node.id, node.name, node.nameZh || ""].some(value => value.toLocaleLowerCase().includes(query)));
  };
  function update() {
    const selected = select.value;
    select.replaceChildren();
    for (const node of matches()) {
      const option = document.createElement("option");
      option.value = node.id;
      option.textContent = `${node.nameZh || node.name} · ${node.name}`;
      select.appendChild(option);
    }
    select.value = matches().some(node => node.id === selected) ? selected : "";
  }
  input.addEventListener("input", update);
  input.addEventListener("keydown", event => {
    if (event.key === "Enter") {
      const node = matches()[0];
      if (node) { select.value = node.id; onSelect(node.id); }
    }
  });
  select.addEventListener("change", () => {
    if (nodes.some(node => node.id === select.value)) onSelect(select.value);
  });
  update();
};
