"use strict";

// Console web do APEX NEXUS: desenha o tabuleiro em canvas e conversa com a API.

const SYMBOLS = {
  "#": { color: "#2b3552", label: "parede", shape: "block" },
  "O": { color: "#5dff8f", label: "você", shape: "circle" },
  "$": { color: "#ffd84d", label: "moeda", shape: "dot" },
  "Q": { color: "#ff5252", label: "mina", shape: "diamond" },
  "*": { color: "#ff8a3d", label: "fogo", shape: "block" },
  "E": { color: "#4de3ff", label: "saída aberta", shape: "block" },
  "e": { color: "#2a6f80", label: "saída trancada", shape: "block" },
  "X": { color: "#ff5ad1", label: "perseguidor", shape: "circle" },
  "Y": { color: "#c77dff", label: "interceptador", shape: "circle" },
  "W": { color: "#b06a9e", label: "vagante", shape: "circle" },
  "A": { color: "#ff3d7f", label: "emboscador", shape: "circle" },
  "z": { color: "#6b4a66", label: "emboscador dormindo", shape: "circle" },
  "B": { color: "#ff1744", label: "chefe", shape: "block" },
  "+": { color: "#7fb3ff", label: "vida", shape: "diamond" },
  "S": { color: "#7fb3ff", label: "escudo", shape: "diamond" },
  "F": { color: "#7fb3ff", label: "gelo", shape: "diamond" },
  "M": { color: "#7fb3ff", label: "ímã", shape: "diamond" },
  "!": { color: "#7fb3ff", label: "fúria", shape: "diamond" },
  "~": { color: "#141a29", label: "névoa", shape: "block" },
};
const LETTERED = new Set(["X", "Y", "W", "A", "z", "B", "+", "S", "F", "M", "!", "E", "e", "Q"]);
const KEYS = {
  w: "w", arrowup: "w", a: "a", arrowleft: "a", s: "s", arrowdown: "s",
  d: "d", arrowright: "d", " ": ".", ".": ".", e: "e", f: "f", b: "b", h: "h",
};
const SHOP = { 1: "heart", 2: "shield", 3: "boots", 4: "potion", 5: "bomb" };
const ITEM_NAMES = { potion: "Poção", bomb: "Bomba" };
const BOSS_NAMES = { guardian: "Guardião", sentinel: "Sentinela", colossus: "Colosso" };
const STATUS_TEXT = {
  won: "Vitória! Você concluiu todas as fases.",
  lost: "Fim de jogo.",
  level_complete: "Fase concluída! Loja: 1 Coração (12), 2 Escudo (8), 3 Botas (15), "
    + "4 Poção (6), 5 Bomba (10). Enter continua.",
};

const $ = (id) => document.getElementById(id);
const canvas = $("board");
const context = canvas.getContext("2d");
let sessionId = null;
let snapshot = null;
let busy = false;

async function api(path, method = "GET", body = null) {
  const options = { method, headers: {} };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Requisição inválida.";
    throw new Error(detail);
  }
  return data;
}

function setMessage(text) {
  $("message").textContent = text;
}

function fillSelect(select, entries, chosen) {
  select.replaceChildren();
  for (const [value, text] of entries) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    option.selected = value === chosen;
    select.append(option);
  }
}

function drawCell(char, x, y, size) {
  const symbol = SYMBOLS[char];
  if (!symbol) return;
  const left = x * size;
  const top = y * size;
  context.fillStyle = symbol.color;
  if (symbol.shape === "block") {
    context.fillRect(left, top, size, size);
  } else if (symbol.shape === "diamond") {
    context.beginPath();
    context.moveTo(left + size / 2, top + 1);
    context.lineTo(left + size - 1, top + size / 2);
    context.lineTo(left + size / 2, top + size - 1);
    context.lineTo(left + 1, top + size / 2);
    context.fill();
  } else {
    const radius = symbol.shape === "dot" ? size * 0.28 : size * 0.45;
    context.beginPath();
    context.arc(left + size / 2, top + size / 2, radius, 0, Math.PI * 2);
    context.fill();
  }
  if (LETTERED.has(char)) {
    context.fillStyle = "#05070c";
    context.fillText(char, left + size / 2, top + size / 2 + 1);
  }
}

function draw() {
  if (!snapshot) return;
  const { width, height } = snapshot.size;
  const ratio = window.devicePixelRatio || 1;
  const size = Math.max(4, Math.floor(canvas.clientWidth / width));
  canvas.width = width * size * ratio;
  canvas.height = height * size * ratio;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.fillStyle = "#05070c";
  context.fillRect(0, 0, width * size, height * size);
  context.font = `bold ${Math.floor(size * 0.7)}px monospace`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  snapshot.rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x += 1) {
      if (row[x] !== " ") drawCell(row[x], x, y, size);
    }
  });
}

function hudRow(list, term, value) {
  const dt = document.createElement("dt");
  dt.textContent = term;
  const dd = document.createElement("dd");
  dd.textContent = value;
  list.append(dt, dd);
}

function render(data) {
  snapshot = data.snapshot;
  sessionId = data.session_id;
  const state = snapshot;
  const count = state.level.count === null ? "?" : state.level.count;
  $("level").textContent = `Fase ${state.level.index + 1}/${count}: ${state.level.title}`;
  $("objective").textContent = state.level.objective;
  const hud = $("hud");
  hud.replaceChildren();
  const player = state.player;
  const coins = state.level.target
    ? `${state.coins_collected}/${state.level.target}` : `${state.coins_collected}`;
  hudRow(hud, "Pontos", state.score);
  hudRow(hud, "Ouro", player.gold);
  hudRow(hud, "Moedas", coins);
  hudRow(hud, "Vida", `${player.hp}/${player.max_hp}`);
  hudRow(hud, "Escudo", player.shield);
  hudRow(hud, "Combo", `x${player.combo}`);
  if (state.time_left !== null) hudRow(hud, "Tempo", state.time_left);
  if (state.boss) {
    const name = BOSS_NAMES[state.level.boss] || "Chefe";
    hudRow(hud, name, `${state.boss.hp}/${state.boss.max_hp}`);
  }
  hudRow(hud, "Dash", player.dash_cooldown ? `em ${player.dash_cooldown}` : "pronto");
  hudRow(hud, "Pulso", player.pulse_cooldown ? `em ${player.pulse_cooldown}` : "pronto");
  const effects = [["Fúria", player.fury], ["Ímã", player.magnet], ["Gelo", state.freeze]]
    .filter(([, turns]) => turns > 0)
    .map(([label, turns]) => `${label} ${turns}`);
  hudRow(hud, "Efeitos", effects.length ? effects.join(", ") : "nenhum");
  const items = Object.entries(player.items)
    .map(([item, count]) => `${ITEM_NAMES[item] || item} x${count}`);
  hudRow(hud, "Itens", items.length ? items.join(", ") : "nenhum");
  hudRow(hud, "Seed", state.seed);

  let text = STATUS_TEXT[state.status] || state.message;
  if (state.status === "level_complete") text = `${state.message} ${text}`;
  if (data.result) {
    const names = data.result.new_achievements.map((item) => item.title);
    text += ` Ranking: ${data.result.position}º.`;
    if (names.length) text += ` Novas conquistas: ${names.join(", ")}.`;
    loadRanking();
  }
  setMessage(text);
  $("next").hidden = state.status !== "level_complete";
  $("shop").hidden = state.status !== "level_complete";
  draw();
}

async function run(task) {
  if (busy) return;
  busy = true;
  try {
    await task();
  } catch (error) {
    setMessage(error.message);
  } finally {
    busy = false;
  }
}

function act(action) {
  if (!sessionId || !snapshot || snapshot.status !== "running") return;
  run(async () => render(await api(`/v1/games/${sessionId}/actions`, "POST", { action })));
}

function nextLevel() {
  if (!sessionId || !snapshot || snapshot.status !== "level_complete") return;
  run(async () => render(await api(`/v1/games/${sessionId}/next-level`, "POST")));
}

function buy(item) {
  if (!sessionId || !snapshot || snapshot.status !== "level_complete") return;
  run(async () => render(await api(`/v1/games/${sessionId}/shop/${item}`, "POST")));
}

function newGame() {
  run(async () => {
    const body = { mode: $("mode").value, difficulty: $("difficulty").value };
    const name = $("name").value.trim();
    const seed = $("seed").value.trim();
    if (name) body.name = name;
    if (seed) body.seed = Number(seed);
    render(await api("/v1/games", "POST", body));
    canvas.focus();
    loadRanking();
  });
}

function saveGame() {
  if (!sessionId) return;
  run(async () => {
    await api(`/v1/games/${sessionId}/save`, "POST");
    setMessage("Partida salva.");
  });
}

function loadGame() {
  const name = $("name").value.trim();
  if (!name) {
    setMessage("Informe o nome do jogador para carregar.");
    return;
  }
  run(async () => {
    render(await api("/v1/games/load", "POST", { name }));
    canvas.focus();
  });
}

async function loadRanking() {
  try {
    const data = await api(`/v1/leaderboard?mode=${encodeURIComponent($("mode").value)}&limit=5`);
    const list = $("ranking");
    list.replaceChildren();
    for (const entry of data.entries) {
      const item = document.createElement("li");
      item.textContent = `${entry.profile}: ${entry.score} (${entry.difficulty})`;
      list.append(item);
    }
    if (!data.entries.length) {
      const item = document.createElement("li");
      item.textContent = "Ainda sem partidas neste modo.";
      list.append(item);
    }
  } catch (error) {
    setMessage(error.message);
  }
}

function buildLegend() {
  const list = $("legend");
  for (const [char, symbol] of Object.entries(SYMBOLS)) {
    const item = document.createElement("li");
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.background = symbol.color;
    item.append(swatch, document.createTextNode(`${char === "#" ? "#" : char}  ${symbol.label}`));
    list.append(item);
  }
}

function onKey(event) {
  const tag = event.target.tagName;
  if (tag === "INPUT" || tag === "SELECT" || event.ctrlKey || event.metaKey || event.altKey) return;
  const key = event.key.toLowerCase();
  if (key === "enter" && snapshot && snapshot.status === "level_complete") {
    event.preventDefault();
    nextLevel();
  } else if (key in SHOP && snapshot && snapshot.status === "level_complete") {
    event.preventDefault();
    buy(SHOP[key]);
  } else if (key in KEYS && tag !== "BUTTON") {
    event.preventDefault();
    act(KEYS[key]);
  }
}

async function start() {
  buildLegend();
  const data = await api("/v1/catalog");
  fillSelect($("mode"), Object.entries(data.modes).map(([id, mode]) => [id, mode.title]), "campaign");
  fillSelect($("difficulty"), data.difficulties.map((id) => [id, id]), "normal");
  $("setup").addEventListener("submit", (event) => {
    event.preventDefault();
    newGame();
  });
  $("save").addEventListener("click", saveGame);
  $("load").addEventListener("click", loadGame);
  $("next").addEventListener("click", nextLevel);
  $("mode").addEventListener("change", loadRanking);
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => act(button.dataset.action));
  });
  document.querySelectorAll("[data-buy]").forEach((button) => {
    button.addEventListener("click", () => buy(button.dataset.buy));
  });
  document.addEventListener("keydown", onKey);
  window.addEventListener("resize", draw);
  newGame();
}

start().catch((error) => setMessage(error.message));

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
