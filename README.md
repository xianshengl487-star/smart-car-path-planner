# Numbered Smart-Car Path Planner

This project is a 16 x 12 smart-car vision contest style path-planning demo.
It supports OpenCV grid recognition, numbered multi-box planning, pushable
bombs, Tkinter animation, a map editor, and a local MCP server.

## Rules

- `.` means empty cell.
- `#` means wall. Boundary walls are protected. Interior walls can be removed by bomb explosions.
- `P` means the car start. Built-in maps start at `(row=5, col=1)`, which is the first interior column and fifth interior row when read left-to-right/top-to-bottom.
- `E` means the endpoint for category 1.
- `B1`, `B2`, `B3`, `B4` mean numbered boxes.
- `T1`, `T2`, `T3`, `T4` mean matching numbered targets.
- `X` means a pushable bomb.
- `D` and `*` are deprecated and intentionally rejected by the parser.

Number matching is fixed: `B1 -> T1`, `B2 -> T2`, and so on.

Boxes vanish on delivery: once a numbered box `Bi` is pushed onto its matching target `Ti`, the box is removed from the board and the cell no longer blocks the car or other boxes. This applies to category 2/3 planning (controlled by `Level.boxes_vanish_on_goal`).

Bomb rule: when the car pushes `X` into an empty cell, the bomb moves one cell.
When the car pushes `X` into a wall, the bomb explodes at the impacted wall
cell and removes non-boundary wall cells in the surrounding 3 x 3 area. The
outer boundary remains closed.

HP is display metadata only. The current competition rule does not deduct HP
for walking, standing on cells, or explosions.

## Built-In Levels

- Level 1: direct numbered multi-box planning. The map is read from code, and no vision step is used.
- Level 2: OpenCV recognition plus difficult numbered multi-box planning.
- Level 3: OpenCV recognition for boxes/targets plus pushable `X` bombs that break wall openings. Bombs are not required recognition objects.

The editor still supports a simple category-1 `P -> E` navigation mode for quick experiments, but the required built-in Level 1 is a multi-box puzzle.

## Run

```powershell
cd G:\路径规划
python main.py --level 1 --no-gui
python main.py --level 2 --no-gui
python main.py --level 3 --no-gui
python main.py --all --no-gui
```

Remove `--no-gui` to see the Tkinter animation.

## Map Editor

```powershell
cd G:\路径规划
python map_editor.py
```

The editor only exposes official tokens: empty cells, walls, car, endpoint,
numbered boxes, numbered targets, and `X` bombs.

## MCP

The local stdio MCP server is started by:

```powershell
G:\路径规划\run_mcp_server.bat
```

It is registered as `smart-car-planner` for Claude Code and Grok Build. The
server exposes:

- `list_levels`
- `solve_level`
- `render_level`
- `solve_contest_folder`

Health checks:

```powershell
claude mcp get smart-car-planner
grok mcp doctor smart-car-planner
```

## Verification

```powershell
cd G:\路径规划
python -m compileall -q .
python -m unittest discover -s tests -v
python main.py --all --no-gui
python main.py --contest --no-gui --max-expanded 250000
python optimization_loop.py --iterations 50
python export_stm32.py
```

## STM32F304 Export

The full Python A* solver is used on the PC. For STM32F304 firmware, run:

```powershell
python export_stm32.py
```

This generates:

- `embedded/generated/stm32_plans.h`
- `embedded/generated/stm32_memory_report.json`

Copy `embedded/stm32f304/planner_core.c`, `planner_core.h`, and the generated
header into STM32CubeIDE. The embedded runner uses fixed arrays, 1-byte actions,
and a 16x12 fixed-queue BFS workspace. It avoids dynamic allocation and is
designed for small SRAM MCUs.

## Native Android App

`android_native/` contains a real Android app project, separate from the PWA.
It lets a phone edit custom 16x12 maps for 101/102/103, run the planner on the
phone, and choose STM32-style performance limits. The debug APK can be built
with the bundled Android Gradle setup, and the shared Java planning core is
verified with:

```powershell
android_native\run_core_smoke.ps1
```

## Complex Maps

`planner/complex_maps.py` defines three benchmark maps:

| Level ID | Category | Purpose |
| --- | --- | --- |
| 101 | Cat 2 | Push boxes only: two numbered boxes, no recognition pre-scan, no bombs |
| 102 | Cat 2 | Same map complexity as 101, but the car first approaches boxes and targets for recognition |
| 103 | Cat 3 | Builds on 102 with three boxes and an `X` bomb used during planning, but not required during recognition |

For all 101/102/103 benchmark maps, a numbered box disappears when it reaches
its matching target, leaving that cell free for later movement.

Benchmark JSON files are saved under `.orchestration/optimization_runs/`.

## Contest Folder

`比赛关卡/` PNG screenshots are recognized with a contest-specific 16x12 grid
detector. The detector ignores the row/column labels around the screenshot,
classifies yellow cells as boxes and blue cells as targets, and forces the car
start to `(row=5, col=1)`.

When a screenshot does not expose reliable object numbers, the batch solver
keeps direct reading-order numbering first, then uses a small exact A* probe on
cyclic target remaps before falling back to full-budget strict A*. On the local
7-image folder this keeps all maps solvable while reducing batch time from
about 75 seconds to about 22 seconds.
