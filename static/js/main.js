// ── Item database (fetched once on load) ─────────────────────
// /api/items already filters out untradeable gold/silver/bronze/red/blue/purple items
let allItems = [];
fetch("/api/items").then(r => r.json()).then(d => {
  allItems = d;
  loadSavedInventory();  // pre-populate inventory tab after items load
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

// ── Tag input factory ─────────────────────────────────────────
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
      li.addEventListener("mousedown", e => {
        e.preventDefault();
        addTag(li.textContent);
      });
    });
  }

  function hideSuggestions() {
    suggestBox.classList.remove("open");
    activeIdx = -1;
  }

  input.addEventListener("input", () => showSuggestions(input.value.trim().toLowerCase()));
  input.addEventListener("blur",  () => setTimeout(hideSuggestions, 150));

  input.addEventListener("keydown", e => {
    const items = suggestBox.querySelectorAll("li");
    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIdx = Math.min(activeIdx + 1, items.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIdx = Math.max(activeIdx - 1, -1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0 && items[activeIdx]) {
        addTag(items[activeIdx].textContent);
      } else if (input.value.trim()) {
        addTag(input.value.trim());
      }
      return;
    } else if (e.key === "Backspace" && !input.value && tags.length) {
      tags.pop(); renderTags(); return;
    }
    items.forEach((li, i) => li.classList.toggle("active", i === activeIdx));
  });

  return {
    getTags:  () => [...tags],
    setTags:  (newTags) => { tags.length = 0; newTags.forEach(t => tags.push(t)); renderTags(); },
    clear:    () => { tags.length = 0; renderTags(); },
  };
}

const yoursInput  = makeTagInput("yours-tags",  "yours-input",  "yours-suggestions");
const theirsInput = makeTagInput("theirs-tags", "theirs-input", "theirs-suggestions");

// ── Clear button ──────────────────────────────────────────────
document.getElementById("clear-btn").addEventListener("click", () => {
  yoursInput.clear();
  theirsInput.clear();
  document.getElementById("result-panel").classList.add("hidden");
  document.getElementById("trade-error").classList.add("hidden");
});

// ── Stability tag styling ─────────────────────────────────────
const STAB_GOOD = new Set(["Rising", "Hyped", "Doing Well", "Overpaid For", "Recovering", "Stabilizing"]);
const STAB_BAD  = new Set(["Decreasing", "Losing Hype", "Underpaid For"]);
const STAB_MID  = new Set(["Fluctuating"]);

function stabClass(s) {
  if (STAB_GOOD.has(s)) return "stab-good";
  if (STAB_BAD.has(s))  return "stab-bad";
  if (STAB_MID.has(s))  return "stab-mid";
  return "stab-neutral";
}

function renderStabTags(containerId, stabs) {
  const el = document.getElementById(containerId);
  el.innerHTML = stabs.map(s =>
    `<span class="stab-tag ${stabClass(s)}">${s}</span>`
  ).join("");
}

// ── Diff colouring ────────────────────────────────────────────
function setDiff(elId, val) {
  const el = document.getElementById(elId);
  const sign = val > 0 ? "+" : "";
  el.textContent = sign + val;
  el.className = "value " + (val > 0 ? "diff-pos" : val < 0 ? "diff-neg" : "");
}

// ── Warning descriptions ──────────────────────────────────────
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
    errEl.classList.remove("hidden");
    return;
  }

  const res = await fetch("/api/trade", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ yours: yours.join(", "), theirs: theirs.join(", ") })
  });
  const data = await res.json();

  if (!res.ok) {
    errEl.textContent = data.error || "Something went wrong.";
    errEl.classList.remove("hidden");
    return;
  }

  const labels = { win: "WIN", lose: "LOSE", fair: "FAIR" };
  const verdict = document.getElementById("result-verdict");
  verdict.textContent = labels[data.result] || data.result.toUpperCase();
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

  const warnEl = document.getElementById("r-warnings");
  const warns  = [];
  const danger = new Set(["Fluctuating", "Losing Hype", "Underpaid For", "Decreasing"]);
  const theirDanger = data.their_stability.filter(s => danger.has(s));

  theirDanger.forEach(s => {
    const desc = STAB_WARN[s] || s;
    warns.push(`⚠ You'd receive a <strong>${s}</strong> item — ${desc}.`);
  });
  if (data.bundle_penalty) {
    warns.push("⚠ Bundle penalty applied — giving multiple items reduces your AI score slightly, since single items are easier to retrade.");
  }

  warnEl.innerHTML = warns.map(w => `<div class="warn-item">${w}</div>`).join("");
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
    li.addEventListener("mousedown", e => {
      e.preventDefault();
      statsInput.value = li.textContent;
      statsSuggest.classList.remove("open");
    });
  });
});
statsInput.addEventListener("blur",  () => setTimeout(() => statsSuggest.classList.remove("open"), 150));
statsInput.addEventListener("keydown", e => {
  const items = statsSuggest.querySelectorAll("li");
  if (e.key === "ArrowDown") { e.preventDefault(); statsActiveIdx = Math.min(statsActiveIdx + 1, items.length - 1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); statsActiveIdx = Math.max(statsActiveIdx - 1, -1); }
  else if (e.key === "Enter") { e.preventDefault(); lookupStats(); return; }
  items.forEach((li, i) => li.classList.toggle("active", i === statsActiveIdx));
});

async function lookupStats() {
  const name   = statsInput.value.trim().toLowerCase();
  const errEl  = document.getElementById("stats-error");
  const panel  = document.getElementById("stats-panel");
  errEl.classList.add("hidden");
  panel.classList.add("hidden");

  if (!name) {
    errEl.textContent = "Please enter an item name.";
    errEl.classList.remove("hidden");
    return;
  }

  const res  = await fetch("/api/stats?item=" + encodeURIComponent(name));
  const data = await res.json();

  if (!res.ok) {
    errEl.textContent = data.error || "Item not found.";
    errEl.classList.remove("hidden");
    return;
  }

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

const invInput = makeTagInput("inv-tags", "inv-input", "inv-suggestions");

// Load saved inventory from server and pre-populate the tag input
async function loadSavedInventory() {
  try {
    const res  = await fetch("/api/inventory");
    const data = await res.json();
    if (Array.isArray(data) && data.length > 0) {
      invInput.setTags(data);
    }
  } catch (e) {
    // silently ignore on load
  }
}

// Save inventory button
document.getElementById("inv-save-btn").addEventListener("click", async () => {
  const tags   = invInput.getTags();
  const status = document.getElementById("inv-status");
  status.className = "inv-status";
  status.textContent = "";
  status.classList.remove("hidden");

  const res  = await fetch("/api/inventory", {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ items: tags }),
  });
  const data = await res.json();

  if (!res.ok) {
    status.classList.add("status-err");
    status.textContent = data.error || "Failed to save.";
  } else {
    status.classList.add("status-ok");
    status.textContent = `Saved ${data.saved.length} item${data.saved.length !== 1 ? "s" : ""}.`;
    setTimeout(() => status.classList.add("hidden"), 3000);
  }
});

// Clear inventory button
document.getElementById("inv-clear-btn").addEventListener("click", () => {
  invInput.clear();
  const status = document.getElementById("inv-status");
  status.classList.add("hidden");
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
    li.addEventListener("mousedown", e => {
      e.preventDefault();
      offerInput.value = li.textContent;
      offerSuggest.classList.remove("open");
    });
  });
});
offerInput.addEventListener("blur",  () => setTimeout(() => offerSuggest.classList.remove("open"), 150));
offerInput.addEventListener("keydown", e => {
  const items = offerSuggest.querySelectorAll("li");
  if (e.key === "ArrowDown") { e.preventDefault(); offerActiveIdx = Math.min(offerActiveIdx + 1, items.length - 1); }
  else if (e.key === "ArrowUp") { e.preventDefault(); offerActiveIdx = Math.max(offerActiveIdx - 1, -1); }
  else if (e.key === "Enter") { e.preventDefault(); generateOffer(); return; }
  items.forEach((li, i) => li.classList.toggle("active", i === offerActiveIdx));
});

document.getElementById("offer-btn").addEventListener("click", generateOffer);

async function generateOffer() {
  const target  = offerInput.value.trim().toLowerCase();
  const errEl   = document.getElementById("offer-error");
  const panel   = document.getElementById("offer-panel");

  errEl.classList.add("hidden");
  panel.classList.add("hidden");

  if (!target) {
    errEl.textContent = "Please enter the item you want to get.";
    errEl.classList.remove("hidden");
    return;
  }

  const res  = await fetch("/api/suggest-offer", {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ target }),
  });
  const data = await res.json();

  if (!res.ok) {
    errEl.textContent = data.error || "Something went wrong.";
    errEl.classList.remove("hidden");
    return;
  }

  // Populate target name in header
  document.getElementById("op-target-name").textContent = data.target_name;

  // You give — offer items as pills
  const offerList = document.getElementById("op-offer-items");
  offerList.innerHTML = data.offer_items
    .map(name => `<span class="offer-item-pill">${name}</span>`)
    .join("");

  document.getElementById("op-offer-ai").textContent  = data.offer_ai;
  document.getElementById("op-offer-raw").textContent = data.offer_raw;

  // You get — target item
  document.getElementById("op-target-pill").textContent = data.target_name;
  document.getElementById("op-target-ai").textContent   = data.target_ai;
  document.getElementById("op-target-raw").textContent  = data.target_raw;

  // Verdict badge
  const verdictEl = document.getElementById("op-verdict");
  const labels = { win: "WIN ✓", lose: "LOSE", fair: "FAIR" };
  verdictEl.textContent = labels[data.verdict] || data.verdict.toUpperCase();
  verdictEl.className = "offer-verdict-badge verdict-" + data.verdict;

  // Gain note
  const gainEl = document.getElementById("op-gain");
  if (data.your_gain > 0) {
    gainEl.textContent = `(+${data.your_gain} AI in your favor)`;
  } else if (data.your_gain < 0) {
    gainEl.textContent = `(${data.your_gain} AI — closest possible from your inventory)`;
  } else {
    gainEl.textContent = "";
  }

  panel.classList.remove("hidden");
}
