const assert = require("assert");
const app = require("../mobile_app/app.js");

for (const levelId of ["101", "102", "103"]) {
  const template = app.templates[levelId];
  const board = app.parseGrid(app.cloneRows(template.rows));
  const scan = template.scan
    ? app.planRecognition(board, template.bombsInScan)
    : { path: [board.player], actions: [] };
  const solveBoard = { ...board, player: scan.path[scan.path.length - 1] };
  const result = app.solveSokoban(solveBoard, levelId === "103");
  assert(result.actions.length > 0, `${levelId} should have actions`);
  if (levelId === "101") assert.strictEqual(scan.actions.length, 0);
  if (levelId === "102") assert(scan.actions.length > 0);
  if (levelId === "103") assert(scan.actions.length > 0);
  console.log(levelId, {
    scan: scan.actions.length,
    actions: result.actions.length,
    expanded: result.expanded,
  });
}
