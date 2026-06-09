const ROWS = 16;
const COLS = 24;
const START = [1, 5];
const TOKENS = [".", "#", "P", "B1", "T1", "B2", "T2", "B3", "T3", "X"];
const DIRS = [
  [0, -1, "L"],
  [-1, 0, "U"],
  [1, 0, "D"],
  [0, 1, "R"],
];

const templates = {
  101: {
    scan: false,
    bombsInScan: false,
    rows: makeTemplate(false, false),
  },
  102: {
    scan: true,
    bombsInScan: false,
    rows: makeTemplate(false, false),
  },
  103: {
    scan: true,
    bombsInScan: false,
    rows: makeTemplate(true, true),
  },
};

let currentLevel = "101";
let grid = loadLevel(currentLevel);
let brush = "#";
let lastResult = null;
let playTimer = null;
let playIndex = 0;

const hasDOM = typeof document !== "undefined";
const boardEl = hasDOM ? document.querySelector("#board") : null;
const levelSelect = hasDOM ? document.querySelector("#levelSelect") : null;
const brushSelect = hasDOM ? document.querySelector("#brushSelect") : null;
const statusText = hasDOM ? document.querySelector("#statusText") : null;
const costText = hasDOM ? document.querySelector("#costText") : null;
const scanText = hasDOM ? document.querySelector("#scanText") : null;
const expandedText = hasDOM ? document.querySelector("#expandedText") : null;
const actionsText = hasDOM ? document.querySelector("#actionsText") : null;

if (hasDOM) {
  for (const token of TOKENS) {
    const option = document.createElement("option");
    option.value = token;
    option.textContent = token;
    brushSelect.appendChild(option);
  }
  brushSelect.value = brush;

  levelSelect.addEventListener("change", () => {
    currentLevel = levelSelect.value;
    grid = loadLevel(currentLevel);
    lastResult = null;
    render();
  });
  brushSelect.addEventListener("change", () => {
    brush = brushSelect.value;
  });
  document.querySelector("#solveBtn").addEventListener("click", solveCurrent);
  document.querySelector("#playBtn").addEventListener("click", playResult);
  document.querySelector("#resetBtn").addEventListener("click", () => {
    grid = cloneRows(templates[currentLevel].rows);
    saveLevel(currentLevel, grid);
    lastResult = null;
    render();
  });
  document.querySelector("#saveBtn").addEventListener("click", () => {
    saveLevel(currentLevel, grid);
    statusText.textContent = "已保存到手机本地";
  });
}

if (typeof document !== "undefined") {
  render();
}

function makeTemplate(withThirdBox, withBomb) {
  const rows = Array.from({ length: ROWS }, () => Array(COLS).fill("."));
  for (let r = 0; r < ROWS; r++) {
    rows[r][0] = "#";
    rows[r][COLS - 1] = "#";
  }
  for (let c = 0; c < COLS; c++) {
    rows[0][c] = "#";
    rows[ROWS - 1][c] = "#";
  }
  const wallRanges = [
    [2, 1, 4], [2, 8, 11], [2, 17, 22],
    [4, 2, 6], [4, 11, 14], [4, 20, 22],
    [6, 1, 5], [6, 10, 12], [6, 18, 22],
    [8, 1, 5], [8, 10, 12], [8, 18, 22],
    [10, 2, 6], [10, 11, 14], [10, 20, 22],
    [12, 1, 3], [12, 8, 11], [12, 17, 22],
  ];
  for (const [r, a, b] of wallRanges) {
    for (let c = a; c <= b; c++) rows[r][c] = "#";
  }
  rows[START[0]][START[1]] = "P";
  rows[3][6] = "B1";
  rows[3][16] = "T1";
  rows[7][16] = "B2";
  rows[7][7] = "T2";
  if (withThirdBox) {
    rows[11][6] = "B3";
    rows[11][17] = "T3";
  }
  if (withBomb) rows[2][7] = "X";
  return rows;
}

function render(highlight = null) {
  boardEl.innerHTML = "";
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const cell = document.createElement("div");
      const token = grid[r][c];
      cell.className = `cell ${classFor(token)}`;
      if (highlight?.path?.has(key(r, c))) cell.classList.add("path");
      if (highlight?.scan?.has(key(r, c))) cell.classList.add("scan");
      cell.textContent = token === "." ? "" : token;
      cell.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        paint(r, c);
      });
      cell.addEventListener("pointerenter", (event) => {
        if (event.buttons) paint(r, c);
      });
      boardEl.appendChild(cell);
    }
  }
}

function paint(r, c) {
  if (r === 0 || c === 0 || r === ROWS - 1 || c === COLS - 1) return;
  if (brush === "P") clearToken("P");
  grid[r][c] = brush;
  saveLevel(currentLevel, grid);
  render();
}

function solveCurrent() {
  try {
    const board = parseGrid(grid);
    const cfg = templates[currentLevel];
    const scan = cfg.scan ? planRecognition(board, cfg.bombsInScan) : { path: [[board.player[0], board.player[1]]], actions: [], order: [] };
    const solveBoard = { ...board, player: scan.path[scan.path.length - 1] };
    const solved = solveSokoban(solveBoard, currentLevel === "103");
    const actions = [...scan.actions, ...solved.actions];
    const scanCells = new Set(scan.path.map(([r, c]) => key(r, c)));
    const pathCells = new Set(solved.playerPath.map(([r, c]) => key(r, c)));
    lastResult = { actions, scan, solved, scanCells, pathCells };
    statusText.textContent = "已求解";
    costText.textContent = actions.length;
    scanText.textContent = scan.actions.length;
    expandedText.textContent = solved.expanded;
    actionsText.textContent = actions.join(" ");
    render({ scan: scanCells, path: pathCells });
  } catch (error) {
    statusText.textContent = "无解 / 地图错误";
    actionsText.textContent = String(error.message || error);
  }
}

function playResult() {
  if (!lastResult) solveCurrent();
  if (!lastResult) return;
  clearInterval(playTimer);
  playIndex = 0;
  const trace = [...lastResult.scan.path, ...lastResult.solved.playerPath];
  playTimer = setInterval(() => {
    const path = new Set(trace.slice(0, playIndex + 1).map(([r, c]) => key(r, c)));
    render({ scan: lastResult.scanCells, path });
    playIndex++;
    if (playIndex >= trace.length) clearInterval(playTimer);
  }, 120);
}

function solveSokoban(board, allowBombs) {
  const ids = [...board.boxes.keys()].sort((a, b) => a - b);
  const startBoxes = ids.map((id) => board.boxes.get(id));
  const start = stateKey(board.player, startBoxes, board.bombs);
  const heap = [{ f: heuristic(board, startBoxes, ids), g: 0, player: board.player, boxes: startBoxes, bombs: [...board.bombs], actions: [], path: [board.player] }];
  const best = new Map([[start, 0]]);
  let expanded = 0;
  while (heap.length && expanded < 90000) {
    heap.sort((a, b) => a.f - b.f || a.g - b.g);
    const node = heap.shift();
    expanded++;
    if (isGoal(board, node.boxes, ids)) return { actions: node.actions, playerPath: node.path, expanded };
    const boxByPos = new Map(node.boxes.map((p, i) => [key(p[0], p[1]), i]));
    const bombSet = new Set(node.bombs.map(([r, c]) => key(r, c)));
    for (const [dr, dc, dir] of DIRS) {
      const nextPlayer = [node.player[0] + dr, node.player[1] + dc];
      if (isWall(board, nextPlayer)) continue;
      let nextBoxes = node.boxes.map((p) => [...p]);
      let nextBombs = node.bombs.map((p) => [...p]);
      let action = dir.toLowerCase();
      const posKey = key(nextPlayer[0], nextPlayer[1]);
      if (boxByPos.has(posKey)) {
        const index = boxByPos.get(posKey);
        const pushed = [nextPlayer[0] + dr, nextPlayer[1] + dc];
        if (isWall(board, pushed) || boxByPos.has(key(pushed[0], pushed[1])) || bombSet.has(key(pushed[0], pushed[1]))) continue;
        nextBoxes[index] = pushed;
        if (isSimpleDeadlock(board, pushed, ids[index])) continue;
        action = dir;
      } else if (bombSet.has(posKey)) {
        if (!allowBombs) continue;
        const target = [nextPlayer[0] + dr, nextPlayer[1] + dc];
        if (isWall(board, target) || boxByPos.has(key(target[0], target[1])) || bombSet.has(key(target[0], target[1]))) continue;
        nextBombs = nextBombs.filter((p) => key(p[0], p[1]) !== posKey);
        nextBombs.push(target);
        action = `x${dir}`;
      }
      const sk = stateKey(nextPlayer, nextBoxes, nextBombs);
      const ng = node.g + 1;
      if (ng >= (best.get(sk) ?? Infinity)) continue;
      best.set(sk, ng);
      heap.push({ f: ng + heuristic(board, nextBoxes, ids), g: ng, player: nextPlayer, boxes: nextBoxes, bombs: nextBombs, actions: [...node.actions, action], path: [...node.path, nextPlayer] });
    }
  }
  throw new Error("搜索超限，建议减少箱子或放宽通道");
}

function planRecognition(board, includeBombs) {
  const objects = [];
  for (const id of [...board.boxes.keys()].sort((a, b) => a - b)) objects.push([`B${id}`, board.boxes.get(id)]);
  for (const id of [...board.goals.keys()].sort((a, b) => a - b)) objects.push([`T${id}`, board.goals.get(id)]);
  if (includeBombs) board.bombs.forEach((p, i) => objects.push([`X${i + 1}`, p]));
  const approaches = new Map(objects.map(([label, pos]) => [label, approachCells(board, pos)]));
  const full = (1 << objects.length) - 1;
  const startMask = maskFor(board.player, objects, approaches);
  const queue = [{ pos: board.player, mask: startMask, path: [board.player], actions: [] }];
  const seen = new Set([`${key(...board.player)}:${startMask}`]);
  while (queue.length) {
    const node = queue.shift();
    if (node.mask === full) return { path: node.path, actions: node.actions.map((a) => `scan_${a}`), order: recognitionOrder(node.path, objects, approaches) };
    for (const [dr, dc, dir] of DIRS) {
      const nxt = [node.pos[0] + dr, node.pos[1] + dc];
      if (isWall(board, nxt) || objectOccupied(board, nxt)) continue;
      const mask = node.mask | maskFor(nxt, objects, approaches);
      const sk = `${key(...nxt)}:${mask}`;
      if (seen.has(sk)) continue;
      seen.add(sk);
      queue.push({ pos: nxt, mask, path: [...node.path, nxt], actions: [...node.actions, dir.toLowerCase()] });
    }
  }
  throw new Error("无法靠近所有识别对象");
}

function parseGrid(rows) {
  const walls = new Set();
  const boxes = new Map();
  const goals = new Map();
  const bombs = [];
  let player = null;
  rows.forEach((row, r) => row.forEach((token, c) => {
    if (token === "#") walls.add(key(r, c));
    else if (token === "P") player = [r, c];
    else if (token === "X") bombs.push([r, c]);
    else if (token.startsWith("B")) boxes.set(Number(token.slice(1)), [r, c]);
    else if (token.startsWith("T")) goals.set(Number(token.slice(1)), [r, c]);
  }));
  if (!player) throw new Error("地图必须有 P");
  if (!boxes.size) throw new Error("地图必须有箱子");
  for (const id of boxes.keys()) if (!goals.has(id)) throw new Error(`缺少 T${id}`);
  return { walls, boxes, goals, bombs, player };
}

function heuristic(board, boxes, ids) {
  return boxes.reduce((sum, p, i) => {
    const g = board.goals.get(ids[i]);
    return sum + Math.abs(p[0] - g[0]) + Math.abs(p[1] - g[1]);
  }, 0);
}

function isGoal(board, boxes, ids) {
  return boxes.every((p, i) => key(...p) === key(...board.goals.get(ids[i])));
}

function isSimpleDeadlock(board, pos, id) {
  if (key(...pos) === key(...board.goals.get(id))) return false;
  const up = isWall(board, [pos[0] - 1, pos[1]]);
  const down = isWall(board, [pos[0] + 1, pos[1]]);
  const left = isWall(board, [pos[0], pos[1] - 1]);
  const right = isWall(board, [pos[0], pos[1] + 1]);
  return (up || down) && (left || right);
}

function isWall(board, pos) {
  const [r, c] = pos;
  return r < 0 || c < 0 || r >= ROWS || c >= COLS || board.walls.has(key(r, c));
}

function objectOccupied(board, pos) {
  const k = key(...pos);
  for (const p of board.boxes.values()) if (key(...p) === k) return true;
  return board.bombs.some((p) => key(...p) === k);
}

function approachCells(board, pos) {
  return new Set(DIRS.map(([dr, dc]) => [pos[0] + dr, pos[1] + dc]).filter((p) => !isWall(board, p) && !objectOccupied(board, p)).map((p) => key(...p)));
}

function maskFor(pos, objects, approaches) {
  let mask = 0;
  objects.forEach(([label], i) => { if (approaches.get(label).has(key(...pos))) mask |= 1 << i; });
  return mask;
}

function recognitionOrder(path, objects, approaches) {
  const seen = new Set();
  const order = [];
  for (const pos of path) {
    for (const [label] of objects) {
      if (!seen.has(label) && approaches.get(label).has(key(...pos))) {
        seen.add(label);
        order.push(label);
      }
    }
  }
  return order;
}

function stateKey(player, boxes, bombs) {
  return `${key(...player)}|${boxes.map((p) => key(...p)).join(";")}|${bombs.map((p) => key(...p)).sort().join(";")}`;
}

function clearToken(token) {
  grid = grid.map((row) => row.map((cell) => cell === token ? "." : cell));
}

function classFor(token) {
  if (token === "#") return "wall";
  if (token === "P") return "player";
  if (token === "X") return "bomb";
  if (token.startsWith("B")) return "box";
  if (token.startsWith("T")) return "target";
  return "empty";
}

function loadLevel(level) {
  const raw = typeof localStorage === "undefined" ? null : localStorage.getItem(`planner-level-${level}`);
  return raw ? JSON.parse(raw) : cloneRows(templates[level].rows);
}

function saveLevel(level, rows) {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(`planner-level-${level}`, JSON.stringify(rows));
}

function cloneRows(rows) {
  return rows.map((row) => [...row]);
}

function key(r, c) {
  return `${r},${c}`;
}

if (typeof module !== "undefined") {
  module.exports = {
    ROWS,
    COLS,
    templates,
    cloneRows,
    parseGrid,
    planRecognition,
    solveSokoban,
  };
}
