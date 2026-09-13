(() => {
  "use strict";

  const schema = JSON.parse(document.getElementById("cms-editor-schema").textContent);
  const initial = JSON.parse(document.getElementById("cms-editor-document").textContent);
  const endpoints = JSON.parse(document.getElementById("cms-editor-endpoints").textContent);
  const blockTypes = new Map(schema.blocks.map((item) => [item.key, item]));
  const state = structuredClone(initial);

  const fieldsRoot = document.getElementById("cms-editor-fields");
  const errorsRoot = document.getElementById("cms-editor-errors");
  const statusRoot = document.getElementById("cms-editor-status");
  const revisionRoot = document.getElementById("cms-editor-revision");
  const saveButton = document.getElementById("cms-editor-save");
  const publishButton = document.getElementById("cms-editor-publish");

  function getPath(target, path) {
    return path.reduce((value, segment) => value == null ? undefined : value[segment], target);
  }

  function setPath(target, path, value) {
    let current = target;
    path.slice(0, -1).forEach((segment) => {
      if (!current[segment] || typeof current[segment] !== "object") current[segment] = {};
      current = current[segment];
    });
    current[path[path.length - 1]] = value;
  }

  function element(tag, attrs = {}, text = "") {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([key, value]) => {
      if (key === "class") node.className = value;
      else if (key === "disabled") node.disabled = Boolean(value);
      else node.setAttribute(key, String(value));
    });
    if (text) node.textContent = text;
    return node;
  }

  function renderScalar(field, target, parent, className = "cms-editor-field") {
    const wrapper = element("div", {class: className});
    const label = element("label", {}, field.label);
    wrapper.appendChild(label);
    const current = getPath(target, field.path);
    let input;

    if (field.input_kind === "textarea") {
      input = element("textarea", {rows: 6});
      input.value = current ?? "";
    } else if (field.input_kind === "boolean") {
      input = element("input", {type: "checkbox"});
      input.checked = Boolean(current);
    } else if (field.input_kind === "choice" || field.input_kind === "multi_choice") {
      input = element("select", field.input_kind === "multi_choice" ? {multiple: true} : {});
      field.choices.forEach((choice) => {
        const option = element("option", {value: choice.value}, choice.label);
        if (field.input_kind === "multi_choice") {
          option.selected = Array.isArray(current) && current.includes(choice.value);
        } else {
          option.selected = current === choice.value;
        }
        input.appendChild(option);
      });
    } else {
      const type = {
        integer: "number",
        decimal: "number",
        date: "date",
        datetime: "datetime-local",
        email: "email",
        url: "url",
      }[field.input_kind] || "text";
      input = element("input", {type});
      input.value = current ?? "";
      if (field.placeholder) input.placeholder = field.placeholder;
      if (field.input_kind === "decimal") input.step = "any";
    }

    input.disabled = Boolean(field.read_only);
    if (field.required) input.required = true;
    input.addEventListener("change", () => {
      let value;
      if (field.input_kind === "boolean") value = input.checked;
      else if (field.input_kind === "integer") value = input.value === "" ? null : Number.parseInt(input.value, 10);
      else if (field.input_kind === "decimal") value = input.value === "" ? null : Number.parseFloat(input.value);
      else if (field.input_kind === "multi_choice") value = [...input.selectedOptions].map((option) => option.value);
      else value = input.value;
      setPath(target, field.path, value);
    });
    wrapper.appendChild(input);
    if (field.help_text) wrapper.appendChild(element("small", {class: "cms-help"}, field.help_text));
    parent.appendChild(wrapper);
  }

  function allowedBlockTypes(constraint) {
    if (constraint.allowed_types === null) return schema.blocks;
    return constraint.allowed_types.map((key) => blockTypes.get(key)).filter(Boolean);
  }

  function newBlock(type) {
    const definition = blockTypes.get(type);
    if (!definition) throw new Error(`Unknown block type ${type}`);
    const slots = Object.fromEntries(definition.slots.map((slot) => [slot.name, []]));
    return {
      id: crypto.randomUUID(),
      type,
      version: definition.schema_version,
      data: structuredClone(definition.initial_data),
      slots,
    };
  }

  function renderCollection(collection, constraint, parent, title) {
    const wrapper = element("div", {class: "cms-editor-field"});
    wrapper.appendChild(element("label", {}, title));
    const list = element("div", {class: "cms-block-collection"});

    collection.forEach((block, index) => {
      const definition = blockTypes.get(block.type);
      const blockNode = element("div", {class: "cms-block"});
      const header = element("div", {class: "cms-block-header"});
      header.appendChild(element("strong", {}, definition?.label || block.type));
      const actions = element("div", {class: "cms-block-actions"});
      const up = element("button", {type: "button", class: "button", disabled: index === 0}, "↑");
      const down = element("button", {type: "button", class: "button", disabled: index === collection.length - 1}, "↓");
      const remove = element("button", {
        type: "button",
        class: "button",
        disabled: collection.length <= constraint.min_items,
      }, "Remove");
      up.addEventListener("click", () => {
        [collection[index - 1], collection[index]] = [collection[index], collection[index - 1]];
        render();
      });
      down.addEventListener("click", () => {
        [collection[index + 1], collection[index]] = [collection[index], collection[index + 1]];
        render();
      });
      remove.addEventListener("click", () => {
        collection.splice(index, 1);
        render();
      });
      actions.append(up, down, remove);
      header.appendChild(actions);
      blockNode.appendChild(header);

      if (definition) {
        const blockFields = element("div", {class: "cms-block-fields"});
        definition.fields.forEach((field) => renderScalar(field, block.data, blockFields, "cms-block-field"));
        blockNode.appendChild(blockFields);
        definition.slots.forEach((slot) => {
          if (!block.slots[slot.name]) block.slots[slot.name] = [];
          const slotNode = element("div", {class: "cms-block-slot"});
          renderCollection(block.slots[slot.name], slot.constraint, slotNode, slot.label);
          blockNode.appendChild(slotNode);
        });
      }
      list.appendChild(blockNode);
    });

    wrapper.appendChild(list);
    const options = allowedBlockTypes(constraint).filter((item) => item.editable);
    const canAdd = options.length > 0 && (constraint.max_items === null || collection.length < constraint.max_items);
    if (canAdd) {
      const add = element("div", {class: "cms-collection-add"});
      const select = element("select");
      options.forEach((item) => select.appendChild(element("option", {value: item.key}, item.label)));
      const button = element("button", {type: "button", class: "button"}, "Add block");
      button.addEventListener("click", () => {
        collection.push(newBlock(select.value));
        render();
      });
      add.append(select, button);
      wrapper.appendChild(add);
    }
    parent.appendChild(wrapper);
  }

  function render() {
    fieldsRoot.replaceChildren();
    schema.fields.forEach((field) => {
      if (field.constraint) {
        let collection = getPath(state.data, field.path);
        if (!Array.isArray(collection)) {
          collection = [];
          setPath(state.data, field.path, collection);
        }
        renderCollection(collection, field.constraint, fieldsRoot, field.label);
      } else {
        renderScalar(field, state.data, fieldsRoot);
      }
    });
    revisionRoot.textContent = state.is_new
      ? "New content"
      : `Revision ${state.revision_number} · content version ${state.content_version}`;
    publishButton.disabled = state.is_new || !state.revision_id;
  }

  function csrfToken() {
    const field = document.querySelector(
      "#cms-editor-csrf input[name=csrfmiddlewaretoken]",
    );
    if (field) return field.value;
    const row = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith("csrftoken="));
    return row ? decodeURIComponent(row.split("=")[1]) : "";
  }

  async function send(url, body) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) throw payload;
    return payload;
  }

  function showError(error) {
    errorsRoot.hidden = false;
    errorsRoot.replaceChildren();
    errorsRoot.appendChild(element("strong", {}, error.detail || "Request failed."));
    (error.problems || []).forEach((problem) => {
      errorsRoot.appendChild(element("div", {}, `${problem.path}: ${problem.message}`));
    });
  }

  function clearError() {
    errorsRoot.hidden = true;
    errorsRoot.replaceChildren();
  }

  saveButton.addEventListener("click", async () => {
    clearError();
    saveButton.disabled = true;
    statusRoot.textContent = "Saving…";
    try {
      if (state.is_new) {
        const result = await send(endpoints.create, {
          type: state.type,
          schema_version: schema.schema_version,
          data: state.data,
        });
        window.location.href = `${endpoints.changelist}${result.content_id}/editor/`;
        return;
      }
      const result = await send(endpoints.revision, {
        expected_version: state.content_version,
        schema_version: schema.schema_version,
        data: state.data,
      });
      state.content_version = result.content_version;
      state.revision_id = result.revision_id;
      state.revision_number = result.revision_number;
      statusRoot.textContent = "Saved.";
      render();
    } catch (error) {
      statusRoot.textContent = "Save failed.";
      showError(error);
    } finally {
      saveButton.disabled = false;
    }
  });

  publishButton.addEventListener("click", async () => {
    clearError();
    publishButton.disabled = true;
    statusRoot.textContent = "Publishing…";
    try {
      const result = await send(endpoints.publish, {
        expected_version: state.content_version,
        revision_id: state.revision_id,
      });
      state.content_version = result.content_version;
      state.published_revision_id = result.revision_id;
      statusRoot.textContent = "Published.";
      render();
    } catch (error) {
      statusRoot.textContent = "Publish failed.";
      showError(error);
    } finally {
      publishButton.disabled = false;
    }
  });

  render();
})();
