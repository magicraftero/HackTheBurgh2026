(function () {
  "use strict";

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var CONDITIONS = [
    { id: "lice", label: "Lice", high: "Lice outbreak", low: "Few lice" },
    { id: "mortality", label: "Deaths", high: "More deaths than usual", low: "Fewer deaths than usual" },
    { id: "temp", label: "Sea temperature", high: "Warmer sea than normal", low: "Colder sea than normal" }
  ];
  var PRESETS = [
    { label: "Calm month", set: { lice: 50, mortality: 50, temp: 50 } },
    { label: "Lice outbreak", set: { lice: 97, mortality: 60, temp: 60 } },
    { label: "Mass deaths", set: { lice: 60, mortality: 98, temp: 50 } },
    { label: "Cold snap", set: { lice: 30, mortality: 45, temp: 3 } },
    { label: "Heatwave", set: { lice: 85, mortality: 70, temp: 97 } },
    { label: "Perfect year", set: { lice: 5, mortality: 5, temp: 75 } }
  ];

  var data, state = { area: 6, fish: 600000, weight: 2.4, month: 10, lice: 50, mortality: 50, temp: 50 };
  var $ = function (id) { return document.getElementById(id); };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function fmtTonnes(kg) {
    var t = kg / 1000;
    return t >= 100 ? Math.round(t).toLocaleString("en-GB") + " t" : t.toFixed(t >= 10 ? 1 : 2) + " t";
  }
  function fmtFish(n) {
    return n >= 1e6 ? (n / 1e6).toFixed(2) + " M" : Math.round(n / 1000).toLocaleString("en-GB") + "k";
  }
  function fmtPct(x) {
    var p = 100 * x;
    return (p >= 0 ? "+" : "") + p.toFixed(Math.abs(p) < 10 ? 1 : 0) + "%";
  }
  function levelWords(p) {
    if (p >= 80) return "very high";
    if (p >= 60) return "high";
    if (p > 40) return "normal";
    if (p > 20) return "low";
    return "very low";
  }
  function area() {
    return data.areas.find(function (a) { return a.area === state.area; });
  }

  // Effect of a condition at percentile p: the measured top or bottom third (against the middle)
  // reached at the third's centre, scaled linearly in between, never beyond what was measured.
  function conditionEffect(id, p) {
    var e = data.effects[id];
    if (!e) return { count: 0, weight: 0 };
    var side = p >= 50 ? e.high : e.low;
    var share = Math.min(Math.abs(p - 50) / (100 / 3), 1);
    return { count: side.count * share, weight: side.weight * share };
  }

  function heavyShare(a) {
    var sw = a.stock_weight;
    if (state.weight <= sw.p50) return 0;
    return Math.min((state.weight - sw.p50) / Math.max(sw.p80 - sw.p50, 0.01), 1);
  }

  function simulate() {
    var a = area(), m = state.month - 1;
    var rate = a.rate[m] || 0, hw = a.harvest_weight[m] || state.weight;
    var biomass = state.fish * state.weight;
    var typicalKg = biomass * rate;
    var typicalCount = typicalKg / hw;

    var steps = [];
    var logCount = Math.log(Math.max(typicalCount, 1)), logWeight = Math.log(hw);
    var kgBefore = typicalKg;
    function step(label, dc, dw, info) {
      logCount += dc; logWeight += dw;
      var kgNow = Math.exp(logCount + logWeight);
      steps.push({ label: label, delta: kgNow - kgBefore, after: kgNow, dc: dc, dw: dw, info: info });
      kgBefore = kgNow;
    }
    var heavy = heavyShare(a) * data.heavy_stock;
    step("Heavy stock", heavy, 0, { share: heavyShare(a) });
    CONDITIONS.forEach(function (c) {
      var e = conditionEffect(c.id, state[c.id]);
      step(c.label, e.count, e.weight, { p: state[c.id] });
    });

    var count = Math.min(Math.exp(logCount), state.fish);
    var weight = Math.exp(logWeight);
    return {
      typical: { kg: typicalKg, count: typicalCount, weight: hw },
      kg: count * weight, count: count, weight: weight, steps: steps, rate: rate
    };
  }

  // ---------- Controls ----------

  function setupControls() {
    var select = $("area");
    data.areas.forEach(function (a) {
      var opt = el("option", null, "Area " + a.area + ": " + a.name);
      opt.value = a.area;
      select.appendChild(opt);
    });
    select.value = state.area;
    select.addEventListener("change", function () { state.area = +select.value; update(); });

    var months = $("months");
    MONTHS.forEach(function (name, i) {
      var chip = el("button", "chip", name);
      chip.type = "button";
      chip.addEventListener("click", function () { state.month = i + 1; update(); });
      months.appendChild(chip);
    });

    ["fish", "weight", "lice", "mortality", "temp"].forEach(function (id) {
      $(id).addEventListener("input", function () { state[id] = +$(id).value; update(); });
    });

    var presets = $("presets");
    PRESETS.forEach(function (p) {
      var b = el("button", "btn btn-soft btn-sm", p.label);
      b.type = "button";
      b.addEventListener("click", function () { animateTo(p.set); });
      presets.appendChild(b);
    });

    $("load-real").addEventListener("click", loadReal);
  }

  function animateTo(target) {
    var start = {}, t0 = performance.now(), duration = 600;
    Object.keys(target).forEach(function (k) { start[k] = state[k]; });
    function frame(now) {
      var t = Math.min((now - t0) / duration, 1), ease = 1 - Math.pow(1 - t, 3);
      Object.keys(target).forEach(function (k) { state[k] = start[k] + (target[k] - start[k]) * ease; });
      update();
      if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function loadReal() {
    var a = area(), target = {};
    CONDITIONS.forEach(function (c) { if (a.now[c.id] !== null && a.now[c.id] !== undefined) target[c.id] = a.now[c.id]; });
    if (a.fish_weight_in_water) target.weight = a.fish_weight_in_water.kg;
    state.month = +data.target_month.slice(5, 7);
    animateTo(target);
  }

  function syncControls() {
    ["fish", "weight", "lice", "mortality", "temp"].forEach(function (id) {
      if (document.activeElement !== $(id)) $(id).value = state[id];
    });
    $("fish-out").textContent = Math.round(state.fish).toLocaleString("en-GB");
    $("weight-out").textContent = state.weight.toFixed(2) + " kg";
    CONDITIONS.forEach(function (c) {
      $(c.id + "-out").textContent = levelWords(state[c.id]) + " (" + Math.round(state[c.id]) + "th pct)";
    });
    var sw = area().stock_weight;
    $("weight-hint").textContent = "Typical for this area: " + sw.p20 + "-" + sw.p80 + " kg (young fish included). Heavier than " + sw.p80 + " kg counts as heavy stock.";
    document.querySelectorAll("#months .chip").forEach(function (chip, i) {
      chip.setAttribute("aria-pressed", String(i + 1 === state.month));
    });
  }

  // ---------- Results ----------

  function delta(node, now, typical) {
    var change = now / typical - 1;
    node.replaceChildren();
    if (!isFinite(change)) return;
    var span = el("span", Math.abs(change) < 0.0005 ? "" : change > 0 ? "up" : "down", fmtPct(change));
    node.appendChild(span);
    node.appendChild(document.createTextNode(" vs a typical " + MONTHS[state.month - 1]));
  }

  function renderResults(r) {
    $("r-kg").textContent = fmtTonnes(r.kg);
    delta($("r-kg-d"), r.kg, r.typical.kg);
    $("r-count").textContent = fmtFish(r.count);
    delta($("r-count-d"), r.count, r.typical.count);
    $("r-weight").textContent = r.weight.toFixed(2) + " kg";
    delta($("r-weight-d"), r.weight, r.typical.weight);
    if (data.price) {
      var nok = r.kg * data.price.price_nok_kg;
      $("r-value").textContent = "NOK " + (nok >= 1e6 ? (nok / 1e6).toFixed(1) + " M" : Math.round(nok / 1000) + "k");
      $("r-value-d").textContent = "at " + data.price.price_nok_kg.toFixed(2) + " NOK/kg (" + data.price.week + ")";
    }
  }

  function renderWaterfall(r) {
    var rows = [{ label: "Typical " + MONTHS[state.month - 1], from: 0, to: r.typical.kg, kind: "wf-total" }];
    var level = r.typical.kg;
    r.steps.forEach(function (s) {
      rows.push({ label: s.label, from: level, to: s.after, kind: Math.abs(s.delta) < 1 ? "wf-zero" : s.delta > 0 ? "wf-pos" : "wf-neg", delta: s.delta });
      level = s.after;
    });
    rows.push({ label: "Your month", from: 0, to: r.kg, kind: "wf-total" });
    var max = Math.max.apply(null, rows.map(function (x) { return Math.max(x.from, x.to); })) * 1.05 || 1;

    var wf = $("waterfall");
    if (wf.children.length !== rows.length) {
      wf.replaceChildren();
      rows.forEach(function () {
        var row = el("div", "wf-row");
        row.appendChild(el("span"));
        var track = el("div", "wf-track");
        track.appendChild(el("div", "wf-bar"));
        row.appendChild(track);
        row.appendChild(el("b"));
        wf.appendChild(row);
      });
    }
    rows.forEach(function (x, i) {
      var row = wf.children[i], lo = Math.min(x.from, x.to), hi = Math.max(x.from, x.to);
      row.children[0].textContent = x.label;
      var bar = row.children[1].firstChild;
      bar.className = "wf-bar " + x.kind;
      bar.style.left = (100 * lo / max) + "%";
      bar.style.width = Math.max(100 * (hi - lo) / max, 0.6) + "%";
      row.children[2].textContent = x.delta === undefined ? fmtTonnes(x.to)
        : Math.abs(x.delta) < 10 ? "no change"
        : (x.delta >= 0 ? "+" : "-") + fmtTonnes(Math.abs(x.delta));
    });
  }

  function renderWhy(r) {
    var box = $("why");
    box.replaceChildren(el("h2", "panel-title", "Why"));
    var list = el("div", "why-list");
    var any = false;
    CONDITIONS.forEach(function (c) {
      var p = state[c.id], e = data.effects[c.id];
      if (!e || (p > 40 && p < 60)) return;
      any = true;
      var high = p >= 50, measured = high ? e.high : e.low;
      var card = el("div", "why " + (high && c.id !== "temp" ? "warn" : "info"));
      card.appendChild(el("h3", null, high ? c.high : c.low));
      card.appendChild(el("p", null, "Across Norway, months like this were followed by " + fmtPct(Math.exp(measured.count) - 1) +
        " fish harvested at " + fmtPct(Math.exp(measured.weight) - 1) + " weight per fish over the next " + e.window + " months."));
      card.appendChild(el("p", null, whatItMeans(c.id, high)));
      list.appendChild(card);
    });
    var hs = heavyShare(area());
    if (hs > 0) {
      any = true;
      var card = el("div", "why info");
      card.appendChild(el("h3", null, "Heavy stock: a harvest wave is coming"));
      card.appendChild(el("p", null, "When fish in the water are in the heaviest fifth for their area, the next month's harvest takes about " +
        (100 * (Math.exp(data.heavy_stock) - 1)).toFixed(0) + "% more of the stock than in a middling month."));
      card.appendChild(el("p", null, "Book well boats and processing slots early."));
      list.appendChild(card);
    }
    if (!any) {
      var ok = el("div", "why");
      ok.appendChild(el("h3", null, "Nothing unusual"));
      ok.appendChild(el("p", null, "Every condition is in the normal range for the time of year. Move a slider or try a scenario."));
      list.appendChild(ok);
    }
    box.appendChild(list);
  }

  function whatItMeans(id, high) {
    if (id === "lice") return high ? "Forced early harvests of smaller fish. The smaller-fish effect passed our pre-registered test (M1). Consider treating early or harvesting before lice cut size."
      : "Fish stay in longer and grow bigger.";
    if (id === "mortality") return high ? "Emergency harvests: farmers pull fish out before more die. Consider a health check and keeping processing capacity free."
      : "Fewer forced harvests, so fish reach full size.";
    return high ? "Faster growth: the harvest window can open early. Watch for stress above 14 °C."
      : "Slower growth: fish reach harvest size later. Plan sales and feed for a slower month.";
  }

  function renderLive() {
    var a = area(), box = $("live");
    box.replaceChildren();
    var grid = el("div", "live-grid");
    function cell(value, label) {
      var c = el("div", "live-cell");
      c.appendChild(el("b", null, value));
      c.appendChild(el("span", null, label));
      grid.appendChild(c);
    }
    var month = MONTHS[+data.target_month.slice(5, 7) - 1] + " " + data.target_month.slice(0, 4);
    if (a.forecast) {
      cell(fmtTonnes(a.forecast.kg), "whole area, " + month + " forecast");
      cell(fmtTonnes(a.forecast.kg_range[0]) + " - " + fmtTonnes(a.forecast.kg_range[1]), "likely range");
    } else {
      cell("No forecast", "harvest too irregular in this area");
    }
    CONDITIONS.forEach(function (c) {
      var p = a.now[c.id];
      if (p !== null && p !== undefined) cell(levelWords(p), c.label.toLowerCase() + " now (" + Math.round(p) + "th pct)");
    });
    box.appendChild(el("h2", "panel-title", "Area " + a.area + ": " + a.name));
    box.appendChild(grid);
  }

  // ---------- Pen animation ----------

  var canvas, ctx, fishes = [], bubbles = [], last = 0, sim = null;

  function seedFish() {
    fishes = [];
    for (var i = 0; i < 70; i++) {
      fishes.push({ x: Math.random(), y: 0.15 + Math.random() * 0.65, v: 0.02 + Math.random() * 0.03,
                    dir: Math.random() < 0.5 ? -1 : 1, phase: Math.random() * 6.28, seed: Math.random() });
    }
    for (var j = 0; j < 25; j++) bubbles.push({ x: Math.random(), y: Math.random(), v: 0.03 + Math.random() * 0.05 });
  }

  function waterColour(p) {
    var cold = [18, 52, 92], warm = [22, 96, 104], t = p / 100;
    return "rgb(" + cold.map(function (c, i) { return Math.round(c + (warm[i] - c) * t); }).join(",") + ")";
  }

  function drawFish(f, w, h, scale, harvested, dead, lice, time) {
    var x = f.x * w, y = f.y * h + Math.sin(time * 2 + f.phase) * 4;
    var len = 26 * scale, ht = 9 * scale;
    ctx.save();
    ctx.translate(x, y);
    if (dead) { ctx.rotate(Math.PI); ctx.globalAlpha = 0.7; }
    ctx.scale(f.dir, 1);
    ctx.fillStyle = dead ? "#8a96a3" : harvested ? "#e0825f" : "#c7d0d9";
    ctx.beginPath();
    ctx.ellipse(0, 0, len / 2, ht / 2, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    var wag = Math.sin(time * 8 + f.phase) * ht * 0.25;
    ctx.moveTo(-len / 2 + 2, 0);
    ctx.lineTo(-len / 2 - len * 0.32, -ht / 2 + wag);
    ctx.lineTo(-len / 2 - len * 0.32, ht / 2 + wag);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#142130";
    ctx.beginPath();
    ctx.arc(len * 0.3, -ht * 0.12, Math.max(1.2, 1.6 * scale), 0, Math.PI * 2);
    ctx.fill();
    if (!dead && lice > 0) {
      ctx.fillStyle = "#ff5a4f";
      for (var k = 0; k < lice; k++) {
        var lx = (((f.seed * 97 + k * 0.618) % 1) - 0.5) * len * 0.7;
        var ly = (((f.seed * 53 + k * 0.382) % 1) - 0.5) * ht * 0.6;
        ctx.beginPath();
        ctx.arc(lx, ly, Math.max(1.3, 1.8 * scale), 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.restore();
  }

  function drawPen(now) {
    var dt = Math.min((now - last) / 1000, 0.05); last = now;
    var rect = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(rect.width * dpr) || canvas.height !== Math.round(rect.height * dpr)) {
      canvas.width = Math.round(rect.width * dpr); canvas.height = Math.round(rect.height * dpr);
    }
    var w = rect.width, h = rect.height, time = now / 1000;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    var grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, waterColour(state.temp));
    grad.addColorStop(1, "#0d1824");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = "rgba(199,208,217,0.18)";
    ctx.lineWidth = 1;
    for (var gx = 0; gx < w; gx += 22) { ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, h); ctx.stroke(); }
    for (var gy = 0; gy < h; gy += 22) { ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(w, gy); ctx.stroke(); }

    ctx.fillStyle = "rgba(255,255,255,0.25)";
    bubbles.forEach(function (b) {
      b.y -= b.v * dt * (0.6 + state.temp / 80);
      if (b.y < 0) { b.y = 1; b.x = Math.random(); }
      ctx.beginPath(); ctx.arc(b.x * w, b.y * h, 2, 0, Math.PI * 2); ctx.fill();
    });

    if (!sim) return requestAnimationFrame(drawPen);
    var shown = Math.max(6, Math.min(70, Math.round(state.fish / 28000)));
    var harvestShare = Math.min(sim.count / state.fish, 1);
    var harvestedN = Math.round(shown * harvestShare);
    var deadN = Math.round(shown * Math.max(state.mortality - 55, 0) / 300);
    var lice = Math.round(Math.max(state.lice - 35, 0) / 16);
    var scale = Math.max(0.45, Math.min(1.9, Math.sqrt(state.weight / 2.4)));
    var speed = 0.5 + state.temp / 100;

    for (var i = 0; i < shown; i++) {
      var f = fishes[i], dead = i >= shown - deadN;
      if (dead) {
        f.y = Math.max(f.y - 0.04 * dt, 0.06);
      } else {
        f.x += f.dir * f.v * dt * speed;
        if (f.x > 1.05) f.dir = -1;
        if (f.x < -0.05) f.dir = 1;
        if (f.y < 0.12) f.y = 0.15 + f.seed * 0.6;
      }
      drawFish(f, w, h, scale, i < harvestedN, dead, lice, time);
    }

    ctx.fillStyle = "rgba(255,255,255,0.9)";
    ctx.font = "600 13px " + getComputedStyle(document.documentElement).getPropertyValue("--font");
    ctx.fillText(Math.round(state.fish).toLocaleString("en-GB") + " fish, " + state.weight.toFixed(1) + " kg each  |  " +
      Math.round(harvestShare * 1000) / 10 + "% harvested next month", 14, h - 14);
    requestAnimationFrame(drawPen);
  }

  // ---------- Main ----------

  function update() {
    syncControls();
    sim = simulate();
    renderResults(sim);
    renderWaterfall(sim);
    renderWhy(sim);
    renderLive();
  }

  // Resolved from this script, so /cockpit and /cockpit/ both find the file.
  var dataUrl = new URL("data/cockpit.json", document.currentScript.src).href;
  fetch(dataUrl)
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (json) {
      data = json;
      $("made-on").textContent = "Data as of " + data.made_on;
      $("disclaimer").textContent = data.disclaimer;
      state.weight = area().stock_weight.p50;
      canvas = $("pen"); ctx = canvas.getContext("2d");
      seedFish();
      setupControls();
      update();
      requestAnimationFrame(drawPen);
    })
    .catch(function () {
      $("why").textContent = "Couldn't load data/cockpit.json. Run python -m analysis.cockpit from the repo root, then serve the repo folder.";
    });
})();
