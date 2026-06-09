#ifndef SMART_CAR_PLANNER_CORE_H
#define SMART_CAR_PLANNER_CORE_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PP_ROWS 12u
#define PP_COLS 16u
#define PP_CELL_COUNT (PP_ROWS * PP_COLS)
#define PP_WALL_WORDS ((PP_CELL_COUNT + 31u) / 32u)
#define PP_MAX_ACTIONS 128u
#define PP_MAX_BFS_PATH PP_CELL_COUNT

typedef enum {
    PP_DIR_LEFT = 0,
    PP_DIR_UP = 1,
    PP_DIR_DOWN = 2,
    PP_DIR_RIGHT = 3,
} pp_dir_t;

typedef enum {
    PP_KIND_MOVE = 0u,
    PP_KIND_PUSH_BOX = 1u,
    PP_KIND_SCAN_MOVE = 2u,
    PP_KIND_PUSH_BOMB = 3u,
} pp_kind_t;

#define PP_ACTION(dir, kind) ((uint8_t)(((uint8_t)(dir) & 0x03u) | (((uint8_t)(kind) & 0x03u) << 2)))
#define PP_ACTION_EXPLODE 0x10u
#define PP_ACTION_TURN_LEFT 0x20u
#define PP_ACTION_TURN_RIGHT 0x40u

typedef struct {
    uint8_t level_id;
    uint8_t rows;
    uint8_t cols;
    uint16_t action_count;
    uint16_t recognition_cost;
    uint16_t total_cost;
    uint16_t pushes;
    uint32_t wall_bits[PP_WALL_WORDS];
    const uint8_t *actions;
} pp_plan_t;

typedef struct {
    uint8_t dir;
    uint8_t kind;
    bool explode;
    bool turn_left;
    bool turn_right;
} pp_command_t;

typedef struct {
    const pp_plan_t *plan;
    uint16_t action_index;
} pp_runner_t;

typedef struct {
    uint16_t queue[PP_CELL_COUNT];
    int16_t parent[PP_CELL_COUNT];
    uint8_t parent_dir[PP_CELL_COUNT];
} pp_bfs_workspace_t;

void pp_runner_init(pp_runner_t *runner, const pp_plan_t *plan);
bool pp_runner_next(pp_runner_t *runner, pp_command_t *out_command);
uint16_t pp_cell_index(uint8_t row, uint8_t col);
bool pp_wall_get(const uint32_t wall_bits[PP_WALL_WORDS], uint8_t row, uint8_t col);
void pp_wall_set(uint32_t wall_bits[PP_WALL_WORDS], uint8_t row, uint8_t col, bool value);
bool pp_bfs_path(
    const uint32_t wall_bits[PP_WALL_WORDS],
    uint8_t start_row,
    uint8_t start_col,
    uint8_t goal_row,
    uint8_t goal_col,
    pp_bfs_workspace_t *workspace,
    uint8_t out_dirs[PP_MAX_BFS_PATH],
    uint16_t *out_len
);
uint16_t pp_estimated_ram_bytes(void);

#ifdef __cplusplus
}
#endif

#endif
