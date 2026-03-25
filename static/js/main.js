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

// ── Generic tag input (trade/stats tabs — no qty) ─────────────
function makeTagInput(wrapperId, inputId, suggestId) {
  const wrapper    = document.getElementById(wrapperId);
  const input      = document.getElementById(inputId);
  const suggestBox = document.getElementById(suggestId);
  const tags       = [];
  let activeIdx    = -1;

  wrapper.addEventListener("click", () => input.focus());

  function renderTags() {
    wrapper.querySelectorAll(".tag").forEach(t => t.remove());
    tags.forEach((name, i) => {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.innerHTML = `${name}<button class="tag-remove" data-i="${i}">×</button>`;
      wrapper.insertBefore(tag, input);
    });
    wrapper.querySelectorAll(".tag-remove").forEach(btn => {
      btn.addEventListener("click", e => {
        e.stopPropagation();
        tags.splice(+btn.dataset.i, 1);
        renderTags();
      });
    });
  }

  function addTag(name) {
    const clean = name.trim().toLowerCase();
    if (clean && !tags.includes(clean)) {
      tags.push(clean);
      renderTags();
    }
    input.value = "";
    hideSuggestions();
  }

  function showSuggestions(query) {
    if (!query) { hideSuggestions(); return; }
    const matches = allItems.filter(i => i.includes(query)).slice(0, 8);
    if (!matches.length) { hideSuggestions(); return; }
    suggestBox.innerHTML = matches.map(m => `<li>${m}</li>`).join("");
    suggestBox.classList.add("open");
    activeIdx = -1;
    suggestBox.querySelectorAll("li").forEach(li => {
      li.addEventListener("mousedown", e => { e.preventDefault(); addTag(li.textContent); });
    });
  }

  function hideSuggestions() { suggestBox.classList.remove("open"); activeIdx = -1; }

  input.addEventListener("input", () => showSuggestions(input.value.trim().toLowerCase()));
  input.addEventListener("blur",  () => setTimeout(hideSuggestions, 150));
  input.addEventListener("keydown", e => {
    const items = suggestBox.querySelectorAll("li");
    if (e.key === "ArrowDown") { e.preventDefault(); activeIdx = Math.min(activeIdx + 1, items.length - 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); activeIdx = Math.max(activeIdx - 1, -1); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0 && items[activeIdx]) addTag(items[activeIdx].textContent);
      else if (input.value.trim()) addTag(input.value.trim());
      return;
    } else if (e.key === "Backspace" && !input.value && tags.length) { tags.pop(); renderTags(); return; }
    items.forEach((li, i) => li.classList.toggle("active", i === activeIdx));
  });

  return { getTags: () => [...tags], clear: () => { tags.length = 0; renderTags(); } };
}

const yoursInput  = makeTagInput("yours-tags",  "yours-input",  "yours-suggestions");
const theirsInput = makeTagInput("theirs-tags", "theirs-input", "theirs-suggestions");

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
  "Underpaid For": "people often trade this below its listed value, so it may be hard to get fair value back out of it",
  "Decreasing":    "this item is actively losing value and may be worth less by the time you try to retrade it",
  "Losing Hype":   "demand is fading on this item, which could make it harder to move later",
  "Fluctuating":   "this item's price is unstable and hard to pin down — trades involving it are riskier",
};

// ── Check trade ───────────────────────────────────────────────
document.getElementById("check-btn").addEventListener("click", async () => {
  const yours  = yoursInput.getTags();
  const theirs = theirsInput.getTags();
  const errEl  = document.getElementById("trade-error");
  const panel  = document.getElementById("result-panel");
  errEl.classList.add("hidden");
  panel.classList.add("hidden");
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
    warns.push(`⚠ You'd receive a <strong>${s}</strong> item — ${STAB_WARN[s] || s}.`);
  });
  if (data.bundle_penalty) warns.push("⚠ Bundle penalty applied — giving multiple items reduces your AI score slightly.");
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
  statsSuggest.classList.add("open");
  statsActiveIdx = -1;
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
// INVENTORY TAB — with quantities
// Saved to localStorage as: [{name: "harvester", qty: 72}, ...]
// ════════════════════════════════════════════════════════════════

// inv_items: array of {name: string, qty: number}
let inv_items = [];
let activeQtyPopup = null;  // tracks open qty popup so we can close it

const invWrapper  = document.getElementById("inv-tags");
const invTextInput = document.getElementById("inv-input");
const invSuggest  = document.getElementById("inv-suggestions");
let invActiveIdx  = -1;

invWrapper.addEventListener("click", e => {
  // Don't re-focus if a qty popup button was clicked
  if (!e.target.closest(".qty-popup") && !e.target.closest(".qty-badge")) {
    invTextInput.focus();
  }
});

// ── Render inventory tags with qty badges ─────────────────────
function renderInvTags() {
  invWrapper.querySelectorAll(".tag").forEach(t => t.remove());
  inv_items.forEach((entry, i) => {
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
    badge.addEventListener("click", e => {
      e.stopPropagation();
      openQtyPopup(tag, i);
    });

    const removeBtn = document.createElement("button");
    removeBtn.className = "tag-remove";
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", e => {
      e.stopPropagation();
      closeQtyPopup();
      inv_items.splice(i, 1);
      renderInvTags();
    });

    tag.appendChild(label);
    tag.appendChild(badge);
    tag.appendChild(removeBtn);
    invWrapper.insertBefore(tag, invTextInput);
  });
}

// ── Qty popup (appears anchored below the badge) ──────────────
function openQtyPopup(tagEl, idx) {
  closeQtyPopup();

  const popup = document.createElement("div");
  popup.className = "qty-popup";

  const minus = document.createElement("button");
  minus.className = "qty-btn";
  minus.textContent = "−";

  const numInput = document.createElement("input");
  numInput.type = "number";
  numInput.className = "qty-num";
  numInput.min = 1;
  numInput.max = 9999;
  numInput.value = inv_items[idx].qty;

  const plus = document.createElement("button");
  plus.className = "qty-btn";
  plus.textContent = "+";

  const done = document.createElement("button");
  done.className = "qty-done";
  done.textContent = "done";

  function updateQty(val) {
    const n = Math.max(1, Math.min(9999, parseInt(val) || 1));
    inv_items[idx].qty = n;
    numInput.value = n;
    // update badge text live
    tagEl.querySelector(".qty-badge").textContent = "×" + n;
  }

  minus.addEventListener("click", e => { e.stopPropagation(); updateQty(inv_items[idx].qty - 1); });
  plus.addEventListener("click",  e => { e.stopPropagation(); updateQty(inv_items[idx].qty + 1); });
  numInput.addEventListener("input", e => { e.stopPropagation(); updateQty(numInput.value); });
  numInput.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); closeQtyPopup(); } });
  done.addEventListener("click", e => { e.stopPropagation(); closeQtyPopup(); });

  popup.appendChild(minus);
  popup.appendChild(numInput);
  popup.appendChild(plus);
  popup.appendChild(done);

  tagEl.appendChild(popup);
  activeQtyPopup = popup;
  numInput.focus();
  numInput.select();
}

function closeQtyPopup() {
  if (activeQtyPopup) {
    activeQtyPopup.remove();
    activeQtyPopup = null;
  }
}

// Close popup when clicking outside
document.addEventListener("click", e => {
  if (activeQtyPopup && !e.target.closest(".tag-qty")) {
    closeQtyPopup();
  }
});

// ── Add item to inventory ─────────────────────────────────────
function invAddItem(name) {
  const clean = name.trim().toLowerCase();
  if (!clean) return;
  const existing = inv_items.find(e => e.name === clean);
  if (existing) {
    // If already in inventory, just open qty popup to let them bump the count
    const tags = invWrapper.querySelectorAll(".tag-qty");
    const idx  = inv_items.indexOf(existing);
    if (tags[idx]) openQtyPopup(tags[idx], idx);
  } else {
    inv_items.push({ name: clean, qty: 1 });
    renderInvTags();
    // Auto-open qty popup for the new item so they can immediately set qty
    const tags = invWrapper.querySelectorAll(".tag-qty");
    const newIdx = inv_items.length - 1;
    if (tags[newIdx]) openQtyPopup(tags[newIdx], newIdx);
  }
  invTextInput.value = "";
  hideInvSuggestions();
}

// ── Suggestion box ────────────────────────────────────────────
function showInvSuggestions(query) {
  if (!query) { hideInvSuggestions(); return; }
  const matches = allItems.filter(i => i.includes(query)).slice(0, 8);
  if (!matches.length) { hideInvSuggestions(); return; }
  invSuggest.innerHTML = matches.map(m => `<li>${m}</li>`).join("");
  invSuggest.classList.add("open");
  invActiveIdx = -1;
  invSuggest.querySelectorAll("li").forEach(li => {
    li.addEventListener("mousedown", e => { e.preventDefault(); invAddItem(li.textContent); });
  });
}
function hideInvSuggestions() { invSuggest.classList.remove("open"); invActiveIdx = -1; }

invTextInput.addEventListener("input", () => showInvSuggestions(invTextInput.value.trim().toLowerCase()));
invTextInput.addEventListener("blur",  () => setTimeout(hideInvSuggestions, 150));
invTextInput.addEventListener("keydown", e => {
  const items = invSuggest.querySelectorAll("li");
  if (e.key === "ArrowDown") { e.preventDefault(); invActiveIdx = Math.min(invActiveIdx+1, items.length-1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); invActiveIdx = Math.max(invActiveIdx-1, -1); }
  else if (e.key === "Enter") {
    e.preventDefault();
    if (invActiveIdx >= 0 && items[invActiveIdx]) invAddItem(items[invActiveIdx].textContent);
    else if (invTextInput.value.trim()) invAddItem(invTextInput.value.trim());
    return;
  } else if (e.key === "Backspace" && !invTextInput.value && inv_items.length) {
    inv_items.pop(); closeQtyPopup(); renderInvTags(); return;
  }
  items.forEach((li, i) => li.classList.toggle("active", i === invActiveIdx));
});

// ── localStorage persistence ──────────────────────────────────
const LS_KEY = "mm2_inventory_v2";

function loadSavedInventory() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (Array.isArray(data)) {
      // Support old format (flat string array) and new format (objects)
      inv_items = data.map(entry => {
        if (typeof entry === "string") return { name: entry, qty: 1 };
        return { name: entry.name, qty: entry.qty || 1 };
      });
      renderInvTags();
    }
  } catch (e) { /* ignore corrupt data */ }
}

function saveInventoryToStorage() {
  localStorage.setItem(LS_KEY, JSON.stringify(inv_items));
}

// ── Save button ───────────────────────────────────────────────
document.getElementById("inv-save-btn").addEventListener("click", () => {
  closeQtyPopup();
  const status = document.getElementById("inv-status");
  status.className = "inv-status";

  if (inv_items.length === 0) {
    status.classList.remove("hidden");
    status.classList.add("status-err");
    status.textContent = "Add some items first.";
    return;
  }

  saveInventoryToStorage();

  // Also sync to server (best-effort, not required for persistence)
  const flat = [];
  inv_items.forEach(e => { for (let i = 0; i < e.qty; i++) flat.push(e.name); });
  fetch("/api/inventory", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items: flat }),
  }).catch(() => {});  // silent — localStorage is the real save

  const total = inv_items.reduce((s, e) => s + e.qty, 0);
  status.classList.remove("hidden");
  status.classList.add("status-ok");
  status.textContent = `Saved — ${inv_items.length} item type${inv_items.length !== 1 ? "s" : ""}, ${total} total.`;
  setTimeout(() => status.classList.add("hidden"), 3500);
});

// ── Clear button ──────────────────────────────────────────────
document.getElementById("inv-clear-btn").addEventListener("click", () => {
  closeQtyPopup();
  inv_items = [];
  renderInvTags();
  localStorage.removeItem(LS_KEY);
  document.getElementById("inv-status").classList.add("hidden");
});

// ── Offer generator ───────────────────────────────────────────
const offerInput   = document.getElementById("offer-input");
const offerSuggest = document.getElementById("offer-suggestions");
let offerActiveIdx = -1;

offerInput.addEventListener("input", () => {
  const q = offerInput.value.trim().toLowerCase();
  if (!q) { offerSuggest.classList.remove("open"); return; }
  const matches = allItems.filter(i => i.includes(q)).slice(0, 8);
  if (!matches.length) { offerSuggest.classList.remove("open"); return; }
  offerSuggest.innerHTML = matches.map(m => `<li>${m}</li>`).join("");
  offerSuggest.classList.add("open");
  offerActiveIdx = -1;
  offerSuggest.querySelectorAll("li").forEach(li => {
    li.addEventListener("mousedown", e => { e.preventDefault(); offerInput.value = li.textContent; offerSuggest.classList.remove("open"); });
  });
});
offerInput.addEventListener("blur", () => setTimeout(() => offerSuggest.classList.remove("open"), 150));
offerInput.addEventListener("keydown", e => {
  const items = offerSuggest.querySelectorAll("li");
  if (e.key === "ArrowDown") { e.preventDefault(); offerActiveIdx = Math.min(offerActiveIdx+1, items.length-1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); offerActiveIdx = Math.max(offerActiveIdx-1, -1); }
  else if (e.key === "Enter") { e.preventDefault(); generateOffer(); return; }
  items.forEach((li, i) => li.classList.toggle("active", i === offerActiveIdx));
});
document.getElementById("offer-btn").addEventListener("click", generateOffer);

async function generateOffer() {
  const target = offerInput.value.trim().toLowerCase();
  const errEl  = document.getElementById("offer-error");
  const panel  = document.getElementById("offer-panel");
  errEl.classList.add("hidden");
  panel.classList.add("hidden");

  if (!target) {
    errEl.textContent = "Please enter the item you want to get.";
    errEl.classList.remove("hidden"); return;
  }
  if (inv_items.length === 0) {
    errEl.textContent = "Your inventory is empty. Add items above first.";
    errEl.classList.remove("hidden"); return;
  }

  // Expand inventory with quantities for the server
  const flat = [];
  inv_items.forEach(e => { for (let i = 0; i < e.qty; i++) flat.push(e.name); });

  const res = await fetch("/api/suggest-offer", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target, inventory: flat }),
  });
  const data = await res.json();

  if (!res.ok) { errEl.textContent = data.error || "Something went wrong."; errEl.classList.remove("hidden"); return; }

  document.getElementById("op-target-name").textContent = data.target_name;

  // Count duplicates in offer for display e.g. "harvester ×3"
  const offerCounts = {};
  data.offer_items.forEach(n => { offerCounts[n] = (offerCounts[n] || 0) + 1; });
  document.getElementById("op-offer-items").innerHTML = Object.entries(offerCounts)
    .map(([name, cnt]) => `<span class="offer-item-pill">${name}${cnt > 1 ? " ×" + cnt : ""}</span>`)
    .join("");

  document.getElementById("op-offer-ai").textContent  = data.offer_ai;
  document.getElementById("op-offer-raw").textContent = data.offer_raw;
  document.getElementById("op-target-pill").textContent = data.target_name;
  document.getElementById("op-target-ai").textContent   = data.target_ai;
  document.getElementById("op-target-raw").textContent  = data.target_raw;

  const verdictEl = document.getElementById("op-verdict");
  verdictEl.textContent = { win:"WIN ✓", lose:"LOSE", fair:"FAIR" }[data.verdict] || data.verdict.toUpperCase();
  verdictEl.className = "offer-verdict-badge verdict-" + data.verdict;

  const gainEl = document.getElementById("op-gain");
  gainEl.textContent = data.your_gain > 0 ? `(+${data.your_gain} AI in your favor)`
    : data.your_gain < 0 ? `(${data.your_gain} AI — closest possible from your inventory)` : "";

  panel.classList.remove("hidden");
}
