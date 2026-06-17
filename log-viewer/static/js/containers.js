import { fetchContainers } from "./api.js";
import { colorFor, escapeHTML } from "./utils.js";

export class ContainerList {
  constructor(rootEl, selectAllEl, onChange) {
    this.root = rootEl;
    this.selectAll = selectAllEl;
    this.onChange = onChange;
    this.items = [];
    this.selected = new Set();

    this.selectAll.addEventListener("change", () => {
      const checked = this.selectAll.checked;
      this.selected = checked
        ? new Set(this.items.map((i) => i.name))
        : new Set();
      this.render();
      this.onChange(this.selected);
    });
  }

  async load() {
    try {
      this.items = await fetchContainers();
      this.render();
    } catch (e) {
      this.root.innerHTML = `<li class="sidebar__placeholder">Ошибка: ${escapeHTML(e.message)}</li>`;
    }
  }

  toggle(name) {
    if (this.selected.has(name)) this.selected.delete(name);
    else this.selected.add(name);
    this.selectAll.checked = this.selected.size === this.items.length && this.items.length > 0;
    this.onChange(this.selected);
  }

  render() {
    if (!this.items.length) {
      this.root.innerHTML = `<li class="sidebar__placeholder">Контейнеры не найдены</li>`;
      return;
    }
    const frag = document.createDocumentFragment();
    for (const item of this.items) {
      const li = document.createElement("li");
      li.className = "container-item";
      const checked = this.selected.has(item.name) ? "checked" : "";
      const statusClass = `container-item__status--${item.status}`;
      li.innerHTML = `
        <input type="checkbox" data-name="${escapeHTML(item.name)}" ${checked} />
        <span class="container-item__swatch" style="background:${colorFor(item.name)}"></span>
        <span class="container-item__name" title="${escapeHTML(item.image)}">${escapeHTML(item.name)}</span>
        <span class="container-item__status ${statusClass}">${escapeHTML(item.status)}</span>
      `;
      const checkbox = li.querySelector("input");
      checkbox.addEventListener("change", () => this.toggle(item.name));
      frag.appendChild(li);
    }
    this.root.innerHTML = "";
    this.root.appendChild(frag);
  }
}
