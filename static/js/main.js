// ── Item database (fetched once on load) ─────────────────────
let allItems = [];
fetch("/api/items").then(r => r.json()).then(d => {
  allItems = d;
  loadSavedInventory();
});

// ── Tab switching ─────────────────────────────────────────────
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

// ════════════════════════════════════════════════════════════════
// QTY TAG INPUT FACTORY
// Used for trade (yours/theirs) AND inventory tabs.
// Each tag shows an ×N badge; clicking opens an inline qty popup.
// options.autoPopup — open qty popup immediately when a new tag is added
// ════════════════════════════════════════════════════════════════
function makeQtyTagInput(wrapperId, inputId, suggestId, options = {}) {
  const wrapper    = document.getElementById(wrapperId);
  const textInput  = document.getElementById(inputId);
  const suggestBox = document.getElementById(suggestId);
  // items: [{name, qty}]
  let items = [];
  let activeIdx     = -1;
  let activePopup   = null;

  wrapper.addEventListener("click", e => {
    if (!e.target.closest(".qty-popup") && !e.target.closest(".qty-badge")) {
      textInput.focus();
    }
  });

  // ── Render all tags ──────────────────────────────────────────
  function renderTags() {
    wrapper.querySelectorAll(".tag").forEach(t => t.remove());
    items.forEach((entry, i) => {
      const tag = document.createElement("span");
      tag.className = "tag tag-qty";
      tag.dataset.i = i;

      const label = document.createElement("span");
      label.className = "tag-name";
      label.textContent = entry.name;

      const badge = document.createElement("button");
      badge.className = "qty-badge";
      badge.textContent = "×" + entry.qty;
      badge.title = "click to change quantity";
      badge.addEventListener("click", e => { e.stopPropagation(); openPopup(tag, i); });

      const removeBtn = document.createElement("button");
      removeBtn.className = "tag-remove";
      removeBtn.textContent = "×";
      removeBtn.addEventListener("click", e => {
        e.stopPropagation();
        closePopup();
        items.splice(i, 1);
        renderTags();
      });

      tag.appendChild(label);
      tag.appendChild(badge);
      tag.appendChild(removeBtn);
      wrapper.insertBefore(tag, textInput);
    });
  }

  // ── Qty popup ────────────────────────────────────────────────
  function openPopup(tagEl, idx) {
    closePopup();
    const popup = document.createElement("div");
    popup.className = "qty-popup";

    const minus = document.createElement("button");
    minus.className = "qty-btn"; minus.textContent = "−";

    const numInput = document.createElement("input");
    numInput.type = "number"; numInput.className = "qty-num";
    numInput.min = 1; numInput.max = 9999;
    numInput.value = items[idx].qty;

    const plus = document.createElement("button");
    plus.className = "qty-btn"; plus.textContent = "+";

    const done = document.createElement("button");
    done.className = "qty-done"; done.textContent = "done";

    function updateQty(val) {
      const n = Math.max(1, Math.min(9999, parseInt(val) || 1));
      items[idx].qty = n;
      numInput.value = n;
      tagEl.querySelector(".qty-badge").textContent = "×" + n;
    }

    minus.addEventListener("click", e => { e.stopPropagation(); updateQty(items[idx].qty - 1); });
    plus.addEventListener("click",  e => { e.stopPropagation(); updateQty(items[idx].qty + 1); });
    numInput.addEventListener("input", e => { e.stopPropagation(); updateQty(numInput.value); });
    numInput.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); closePopup(); } });
    done.addEventListener("click", e => { e.stopPropagation(); closePopup(); });

    popup.append(minus, numInput, plus, done);
    tagEl.appendChild(popup);
    activePopup = popup;
    numInput.focus(); numInput.select();
  }

  function closePopup() {
    if (activePopup) { activePopup.remove(); activePopup = null; }
  }

  document.addEventListener("click", e => {
    if (activePopup && !e.target.closest(".tag-qty")) closePopup();
  });

  // ── Add item ─────────────────────────────────────────────────
  function addItem(name) {
    const clean = name.trim().toLowerCase();
    if (!clean) return;
    const existing = items.find(e => e.name === clean);
    if (existing) {
      // Already exists — open popup to bump qty
      renderTags();
      const idx = items.indexOf(existing);
      const tags = wrapper.querySelectorAll(".tag-qty");
      if (tags[idx]) openPopup(tags[idx], idx);
    } else {
      items.push({ name: clean, qty: 1 });
      renderTags();
      if (options.autoPopup !== false) {
        const tags = wrapper.querySelectorAll(".tag-qty");
        const newIdx = items.length - 1;
        if (tags[newIdx]) openPopup(tags[newIdx], newIdx);
      }
    }
    textInput.value = "";
    hideSuggest();
  }

  // ── Suggestions ──────────────────────────────────────────────
  function showSuggest(query) {
    if (!query) { hideSuggest(); return; }
    const matches = allItems.filter(i => i.includes(query)).slice(0, 8);
    if (!matches.length) { hideSuggest(); return; }
    suggestBox.innerHTML = matches.map(m => `<li>${m}</li>`).join("");
    suggestBox.classList.add("open");
    activeIdx = -1;
    suggestBox.querySelectorAll("li").forEach(li => {
      li.addEventListener("mousedown", e => { e.preventDefault(); addItem(li.textContent); });
    });
  }
  function hideSuggest() { suggestBox.classList.remove("open"); activeIdx = -1; }

  textInput.addEventListener("input", () => showSuggest(textInput.value.trim().toLowerCase()));
  textInput.addEventListener("blur",  () => setTimeout(hideSuggest, 150));
  textInput.addEventListener("keydown", e => {
    const lis = suggestBox.querySelectorAll("li");
    if (e.key === "ArrowDown") { e.preventDefault(); activeIdx = Math.min(activeIdx+1, lis.length-1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); activeIdx = Math.max(activeIdx-1, -1); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0 && lis[activeIdx]) addItem(lis[activeIdx].textContent);
      else if (textInput.value.trim()) addItem(textInput.value.trim());
      return;
    } else if (e.key === "Backspace" && !textInput.value && items.length) {
      closePopup(); items.pop(); renderTags(); return;
    }
    lis.forEach((li, i) => li.classList.toggle("active", i === activeIdx));
  });

  // ── Public API ───────────────────────────────────────────────
  return {
    // Returns flat expanded array (e.g. harvester ×3 → ["harvester","harvester","harvester"])
    getTags: () => {
      const out = [];
      items.forEach(e => { for (let i = 0; i < e.qty; i++) out.push(e.name); });
      return out;
    },
    // Returns [{name, qty}] for storage
    getItems: () => items.map(e => ({ ...e })),
    // Load from [{name, qty}] array
    setItems: (arr) => {
      items = arr.map(e => typeof e === "string" ? { name: e, qty: 1 } : { name: e.name, qty: e.qty || 1 });
      renderTags();
    },
    clear: () => { closePopup(); items = []; renderTags(); },
    closePopup,
  };
}

// ── Trade tab inputs ──────────────────────────────────────────
const yoursInput  = makeQtyTagInput("yours-tags",  "yours-input",  "yours-suggestions",  { autoPopup: false });
const theirsInput = makeQtyTagInput("theirs-tags", "theirs-input", "theirs-suggestions", { autoPopup: false });

document.getElementById("clear-btn").addEventListener("click", () => {
  yoursInput.clear();
  theirsInput.clear();
  document.getElementById("result-panel").classList.add("hidden");
  document.getElementById("trade-error").classList.add("hidden");
});

// ── Stability helpers ─────────────────────────────────────────
const STAB_GOOD = new Set(["Rising","Hyped","Doing Well","Overpaid For","Recovering","Stabilizing"]);
const STAB_BAD  = new Set(["Decreasing","Losing Hype","Underpaid For"]);
const STAB_MID  = new Set(["Fluctuating"]);
function stabClass(s) {
  if (STAB_GOOD.has(s)) return "stab-good";
  if (STAB_BAD.has(s))  return "stab-bad";
  if (STAB_MID.has(s))  return "stab-mid";
  return "stab-neutral";
}
function renderStabTags(containerId, stabs) {
  document.getElementById(containerId).innerHTML = stabs.map(s =>
    `<span class="stab-tag ${stabClass(s)}">${s}</span>`).join("");
}
function setDiff(elId, val) {
  const el = document.getElementById(elId);
  el.textContent = (val > 0 ? "+" : "") + val;
  el.className = "value " + (val > 0 ? "diff-pos" : val < 0 ? "diff-neg" : "");
}
const STAB_WARN = {
  "Underpaid For": "people often trade this below its listed value, so it may be very hard to get fair value back out of it",
  "Decreasing":    "this item is actively losing value and may be worth much less by the time you try to retrade it",
  "Losing Hype":   "demand is fading on this item, which could make it harder to trade off later",
  "Fluctuating":   "this item's price is unstable; a lot of new items are given this role which makes the price likely to fall",
};

// ── Check trade ───────────────────────────────────────────────
document.getElementById("check-btn").addEventListener("click", async () => {
  const yours  = yoursInput.getTags();
  const theirs = theirsInput.getTags();
  const errEl  = document.getElementById("trade-error");
  const panel  = document.getElementById("result-panel");
  errEl.classList.add("hidden"); panel.classList.add("hidden");
  if (!yours.length || !theirs.length) {
    errEl.textContent = "Please add at least one item on each side.";
    errEl.classList.remove("hidden"); return;
  }
  const res  = await fetch("/api/trade", { method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ yours: yours.join(", "), theirs: theirs.join(", ") }) });
  const data = await res.json();
  if (!res.ok) { errEl.textContent = data.error || "Something went wrong."; errEl.classList.remove("hidden"); return; }

  const verdict = document.getElementById("result-verdict");
  verdict.textContent = { win:"WIN", lose:"LOSE", fair:"FAIR" }[data.result] || data.result.toUpperCase();
  verdict.className = "result-verdict verdict-" + data.result;
  document.getElementById("r-your-raw").textContent   = data.your_raw;
  document.getElementById("r-their-raw").textContent  = data.their_raw;
  setDiff("r-raw-diff", data.raw_diff);
  document.getElementById("r-your-ai").textContent    = data.your_ai;
  document.getElementById("r-their-ai").textContent   = data.their_ai;
  setDiff("r-ai-diff", data.ai_diff);
  document.getElementById("r-your-demand").textContent  = data.your_demand;
  document.getElementById("r-their-demand").textContent = data.their_demand;
  setDiff("r-demand-diff", data.demand_diff);
  document.getElementById("r-your-rarity").textContent  = data.your_rarity;
  document.getElementById("r-their-rarity").textContent = data.their_rarity;
  setDiff("r-rarity-diff", data.rarity_diff);
  renderStabTags("r-your-stab",  data.your_stability);
  renderStabTags("r-their-stab", data.their_stability);
  const warns = [];
  const danger = new Set(["Fluctuating","Losing Hype","Underpaid For","Decreasing"]);
  data.their_stability.filter(s => danger.has(s)).forEach(s => {
    warns.push(`⚠ You'd receive a <strong>${s}</strong> item: ${STAB_WARN[s] || s}.`);
  });
  if (data.bundle_penalty) warns.push("⚠ Bundle penalty applied: giving multiple items reduces your AI score slightly.");
  document.getElementById("r-warnings").innerHTML = warns.map(w => `<div class="warn-item">${w}</div>`).join("");
  panel.classList.remove("hidden");
});

// ── Stats lookup ──────────────────────────────────────────────
const statsInput   = document.getElementById("stats-input");
const statsSuggest = document.getElementById("stats-suggestions");
let statsActiveIdx = -1;
statsInput.addEventListener("input", () => {
  const q = statsInput.value.trim().toLowerCase();
  if (!q) { statsSuggest.classList.remove("open"); return; }
  const matches = allItems.filter(i => i.includes(q)).slice(0, 8);
  if (!matches.length) { statsSuggest.classList.remove("open"); return; }
  statsSuggest.innerHTML = matches.map(m => `<li>${m}</li>`).join("");
  statsSuggest.classList.add("open"); statsActiveIdx = -1;
  statsSuggest.querySelectorAll("li").forEach(li => {
    li.addEventListener("mousedown", e => { e.preventDefault(); statsInput.value = li.textContent; statsSuggest.classList.remove("open"); });
  });
});
statsInput.addEventListener("blur", () => setTimeout(() => statsSuggest.classList.remove("open"), 150));
statsInput.addEventListener("keydown", e => {
  const items = statsSuggest.querySelectorAll("li");
  if (e.key === "ArrowDown") { e.preventDefault(); statsActiveIdx = Math.min(statsActiveIdx+1, items.length-1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); statsActiveIdx = Math.max(statsActiveIdx-1, -1); }
  else if (e.key === "Enter") { e.preventDefault(); lookupStats(); return; }
  items.forEach((li, i) => li.classList.toggle("active", i === statsActiveIdx));
});
async function lookupStats() {
  const name = statsInput.value.trim().toLowerCase();
  const errEl = document.getElementById("stats-error");
  const panel = document.getElementById("stats-panel");
  errEl.classList.add("hidden"); panel.classList.add("hidden");
  if (!name) { errEl.textContent = "Please enter an item name."; errEl.classList.remove("hidden"); return; }
  const res = await fetch("/api/stats?item=" + encodeURIComponent(name));
  const data = await res.json();
  if (!res.ok) { errEl.textContent = data.error || "Item not found."; errEl.classList.remove("hidden"); return; }
  document.getElementById("s-name").textContent      = data.name;
  document.getElementById("s-value").textContent     = data.value;
  document.getElementById("s-range").textContent     = data.range;
  document.getElementById("s-demand").textContent    = data.demand;
  document.getElementById("s-rarity").textContent    = data.rarity;
  document.getElementById("s-stability").textContent = data.stability;
  document.getElementById("s-ai").textContent        = data.ai_score;
  panel.classList.remove("hidden");
}
document.getElementById("stats-btn").addEventListener("click", lookupStats);


// ════════════════════════════════════════════════════════════════
// INVENTORY TAB
// ════════════════════════════════════════════════════════════════
const invInput = makeQtyTagInput("inv-tags", "inv-input", "inv-suggestions", { autoPopup: true });

const LS_KEY = "mm2_inventory_v2";

// ── Import/export string format: "item1:qty1,item2:qty2,..."
// e.g. "harvester:72,darkbringer:1,eternal iv:3"
function inventoryToString(itemsArr) {
  return itemsArr.map(e => e.qty > 1 ? `${e.name}:${e.qty}` : e.name).join(",");
}

function stringToInventory(str) {
  if (!str || !str.trim()) return [];
  return str.split(",").map(s => s.trim()).filter(Boolean).map(part => {
    const colonIdx = part.lastIndexOf(":");
    if (colonIdx !== -1) {
      const name = part.slice(0, colonIdx).trim().toLowerCase();
      const qty  = Math.max(1, parseInt(part.slice(colonIdx + 1)) || 1);
      return { name, qty };
    }
    return { name: part.toLowerCase(), qty: 1 };
  });
}

function loadSavedInventory() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (Array.isArray(data)) {
      invInput.setItems(data);
      updateExportBox();
    }
  } catch (e) { /* ignore */ }
}

function saveToLocalStorage() {
  localStorage.setItem(LS_KEY, JSON.stringify(invInput.getItems()));
  updateExportBox();
}

function updateExportBox() {
  const box = document.getElementById("inv-export-box");
  if (box) box.value = inventoryToString(invInput.getItems());
}

// ── Save button ───────────────────────────────────────────────
document.getElementById("inv-save-btn").addEventListener("click", () => {
  invInput.closePopup();
  const status = document.getElementById("inv-status");
  const items  = invInput.getItems();
  status.className = "inv-status";

  if (items.length === 0) {
    status.classList.remove("hidden");
    status.classList.add("status-err");
    status.textContent = "Add some items first.";
    return;
  }

  saveToLocalStorage();

  // Sync to server too (best-effort)
  const flat = invInput.getTags();
  fetch("/api/inventory", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items: flat }),
  }).catch(() => {});

  const total = items.reduce((s, e) => s + e.qty, 0);
  status.classList.remove("hidden");
  status.classList.add("status-ok");
  status.textContent = `Saved: ${items.length} item type${items.length !== 1 ? "s" : ""}, ${total} total.`;
  setTimeout(() => status.classList.add("hidden"), 3500);
});

// ── Clear button ──────────────────────────────────────────────
document.getElementById("inv-clear-btn").addEventListener("click", () => {
  invInput.clear();
  localStorage.removeItem(LS_KEY);
  document.getElementById("inv-status").classList.add("hidden");
  updateExportBox();
});

// ── Import string ─────────────────────────────────────────────
document.getElementById("inv-import-btn").addEventListener("click", () => {
  const box    = document.getElementById("inv-export-box");
  const status = document.getElementById("inv-status");
  const str    = box.value.trim();
  if (!str) return;

  const parsed = stringToInventory(str);
  if (!parsed.length) {
    status.classList.remove("hidden");
    status.classList.add("status-err");
    status.textContent = "Couldn't parse that string. Format: itemname:qty,itemname,...";
    return;
  }

  invInput.setItems(parsed);
  saveToLocalStorage();

  const total = parsed.reduce((s, e) => s + e.qty, 0);
  status.classList.remove("hidden");
  status.classList.add("status-ok");
  status.textContent = `Imported ${parsed.length} item type${parsed.length !== 1 ? "s" : ""}, ${total} total.`;
  setTimeout(() => status.classList.add("hidden"), 3500);
});

// Copy export string
document.getElementById("inv-copy-btn").addEventListener("click", () => {
  const box = document.getElementById("inv-export-box");
  box.select();
  navigator.clipboard.writeText(box.value).catch(() => document.execCommand("copy"));
  const btn = document.getElementById("inv-copy-btn");
  btn.textContent = "copied!";
  setTimeout(() => btn.textContent = "copy", 1800);
});

// ── Offer generator (multi-item tag input) ────────────────────
const offerTargetInput = makeQtyTagInput("offer-tags", "offer-input", "offer-suggestions", { autoPopup: false });
const offerInput   = document.getElementById("offer-input");
const offerSuggest = document.getElementById("offer-suggestions");
let offerActiveIdx = -1;

function addOfferTag() {
  const val = offerInput.value.trim().toLowerCase();
  if (!val) return;
  const match = allItems.find(i => i === val) || allItems.find(i => i.includes(val));
  if (match) {
    offerTargetInput.setItems([...offerTargetInput.getItems(), { name: match, qty: 1 }]);
    offerInput.value = "";
    offerSuggest.classList.remove("open");
  }
}

offerInput.addEventListener("input", () => {
  const q = offerInput.value.trim().toLowerCase();
  if (!q) { offerSuggest.classList.remove("open"); return; }
  const matches = allItems.filter(i => i.includes(q)).slice(0, 8);
  if (!matches.length) { offerSuggest.classList.remove("open"); return; }
  offerSuggest.innerHTML = matches.map(m => `<li>${m}</li>`).join("");
  offerSuggest.classList.add("open"); offerActiveIdx = -1;
  offerSuggest.querySelectorAll("li").forEach(li => {
    li.addEventListener("mousedown", e => {
      e.preventDefault();
      offerTargetInput.setItems([...offerTargetInput.getItems(), { name: li.textContent, qty: 1 }]);
      offerInput.value = "";
      offerSuggest.classList.remove("open");
    });
  });
});
offerInput.addEventListener("blur", () => setTimeout(() => offerSuggest.classList.remove("open"), 150));
offerInput.addEventListener("keydown", e => {
  const items = offerSuggest.querySelectorAll("li");
  if (e.key === "ArrowDown") { e.preventDefault(); offerActiveIdx = Math.min(offerActiveIdx+1, items.length-1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); offerActiveIdx = Math.max(offerActiveIdx-1, -1); }
  else if (e.key === "Enter") {
    e.preventDefault();
    if (offerActiveIdx >= 0 && items[offerActiveIdx]) {
      offerTargetInput.setItems([...offerTargetInput.getItems(), { name: items[offerActiveIdx].textContent, qty: 1 }]);
      offerInput.value = "";
      offerSuggest.classList.remove("open");
    } else if (offerInput.value.trim()) {
      addOfferTag();
    } else {
      generateOffer();
    }
    return;
  }
  items.forEach((li, i) => li.classList.toggle("active", i === offerActiveIdx));
});
document.getElementById("offer-btn").addEventListener("click", generateOffer);

async function generateOffer() {
  const targets = offerTargetInput.getTags();
  const errEl     = document.getElementById("offer-error");
  const panel     = document.getElementById("offer-panel");
  const loadingEl = document.getElementById("offer-loading");
  const btn       = document.getElementById("offer-btn");
  errEl.classList.add("hidden"); panel.classList.add("hidden"); loadingEl.classList.add("hidden");
  if (!targets.length) {
    errEl.textContent = "Please add at least one item you want to get.";
    errEl.classList.remove("hidden"); return;
  }
  const flat = invInput.getTags();
  if (!flat.length) {
    errEl.textContent = "Your inventory is empty. Add items above first.";
    errEl.classList.remove("hidden"); return;
  }

  loadingEl.classList.remove("hidden");
  btn.disabled = true;

  let res, data;
  try {
    res = await fetch("/api/suggest-offer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target: targets[0], targets, inventory: flat }),
    });
    data = await res.json();
  } finally {
    loadingEl.classList.add("hidden");
    btn.disabled = false;
  }

  if (!res.ok) { errEl.textContent = data.error || "Something went wrong."; errEl.classList.remove("hidden"); return; }

  const targetNames = data.target_names || [data.target_name];
  document.getElementById("op-target-name").textContent = targetNames.join(", ");
  const offerCounts = {};
  data.offer_items.forEach(n => { offerCounts[n] = (offerCounts[n] || 0) + 1; });
  document.getElementById("op-offer-items").innerHTML = Object.entries(offerCounts)
    .map(([name, cnt]) => `<span class="offer-item-pill">${name}${cnt > 1 ? " x"+cnt : ""}</span>`).join("");
  document.getElementById("op-offer-ai").textContent  = data.offer_ai;
  document.getElementById("op-offer-raw").textContent = data.offer_raw;

  const targetItemsEl = document.getElementById("op-target-items");
  targetItemsEl.innerHTML = targetNames.map(n => `<span class="offer-item-pill">${n}</span>`).join("");
  const singlePill = document.getElementById("op-target-pill");
  if (singlePill) singlePill.textContent = "";

  document.getElementById("op-target-ai").textContent   = data.target_ai;
  document.getElementById("op-target-raw").textContent  = data.target_raw;

  const verdictEl = document.getElementById("op-verdict");
  verdictEl.textContent = { win:"WIN", lose:"LOSE", fair:"FAIR" }[data.verdict] || data.verdict.toUpperCase();
  verdictEl.className = "offer-verdict-badge verdict-" + data.verdict;
  const gainEl = document.getElementById("op-gain");
  gainEl.textContent = data.your_gain > 0 ? `(+${data.your_gain} AI in your favor)`
    : data.your_gain < 0 ? `(${data.your_gain} AI, closest possible from your inventory)` : "";
  panel.classList.remove("hidden");
}
