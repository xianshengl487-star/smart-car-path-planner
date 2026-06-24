# STM32F304 Integration Notes

The STM32F304 target should not run the full Python A* solver. The MCU path is:

1. Run `python export_stm32.py` on the PC.
2. Copy these files into the STM32CubeIDE project:
   - `embedded/stm32f304/planner_core.h`
   - `embedded/stm32f304/planner_core.c`
   - `embedded/generated/stm32_plans.h`
3. Include `stm32_plans.h` in the firmware task that controls the car.
4. Use `pp_runner_next()` to get the next fixed-size command.
5. Use `pp_bfs_path()` only for small local correction/re-route tasks.

## Runtime Model

- Full Sokoban A* stays on PC.
- The MCU executes compact 1-byte commands.
- `command.turn_left` / `command.turn_right` means rotate in place before any forward motion. When either flag is true, use `command.dir` as the resulting heading.
- `PP_KIND_MOVE` means a normal forward move after any requested turn.
- `PP_KIND_SCAN_MOVE` means drive one cell and run the vision recognition step.
- `PP_KIND_PUSH_BOX` means drive one cell while pushing the box.
- `PP_KIND_PUSH_BOMB` means drive one cell while pushing the bomb.
- `command.explode == true` means the bomb should be treated as a wall impact.

## Memory

- Max actions per plan: 106
- Static flash for plan data: about 272 bytes
- Runtime RAM for runner + BFS workspace: about 968 bytes
- No `malloc`, `free`, recursion, OpenCV, Tkinter, Python dict, or heap is used on MCU.

## Region-Guided IDA* Variant

The project also includes a lightweight experimental solver path for future
on-board replanning:

- `region_ida.h` / `region_ida.c`
- `export_region_ida.py`
- `embedded/generated/region_ida_example.h`

This variant follows the STM32-first design:

- Pack player + 3 boxes into one `uint32_t`.
- Use a 16-region 4x3 block graph for 16x12 maps.
- Store `region_id[192]`, `adj[20][4]`, `deadlock[192]`, and
  `region_dist[20][20]`.
- Use region distance as the IDA* heuristic.
- Keep only the current DFS path stack, not a large visited table.
- Leave exact macro generation as a small hook: generate a push across a local
  region boundary, reject deadlocks, verify player reachability, then recurse.

Export the demo region data:

```powershell
python export_region_ida.py --map examples\16x12_hard\stm32_16x12_3box_region_demo.txt
```

The generated header is:

```text
embedded/generated/region_ida_example.h
```

Compile-side entry points:

```c
pp_state_t state = region_ida_example_start;
uint16_t h = pp_region_heuristic(
    state,
    &region_ida_example_graph,
    region_ida_example_goals
);
```

This is not a replacement for the PC exact solver yet. It is the embedded
planning skeleton for region-guided macro-action IDA*.

## Minimal Use

```c
#include "planner_core.h"
#include "stm32_plans.h"

static pp_runner_t runner;

void mission_start(void) {
    pp_runner_init(&runner, &stm32_plans[2]); /* 103 */
}

void mission_tick(void) {
    pp_command_t command;
    if (!pp_runner_next(&runner, &command)) {
        /* mission done */
        return;
    }

    /* Map command.dir to motor motion.
       Map command.kind to scan/push behavior.
       Use command.explode for bomb impact handling. */
}
```
