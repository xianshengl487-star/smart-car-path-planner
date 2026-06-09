#include "planner_core.h"

static int8_t pp_dir_dr(uint8_t dir) {
    static const int8_t table[4] = {0, -1, 1, 0};
    return table[dir & 0x03u];
}

static int8_t pp_dir_dc(uint8_t dir) {
    static const int8_t table[4] = {-1, 0, 0, 1};
    return table[dir & 0x03u];
}

void pp_runner_init(pp_runner_t *runner, const pp_plan_t *plan) {
    if (runner == 0) {
        return;
    }
    runner->plan = plan;
    runner->action_index = 0u;
}

bool pp_runner_next(pp_runner_t *runner, pp_command_t *out_command) {
    if (runner == 0 || runner->plan == 0 || out_command == 0) {
        return false;
    }
    if (runner->action_index >= runner->plan->action_count) {
        return false;
    }

    uint8_t encoded = runner->plan->actions[runner->action_index++];
    out_command->dir = encoded & 0x03u;
    out_command->kind = (encoded >> 2) & 0x03u;
    out_command->explode = (encoded & PP_ACTION_EXPLODE) != 0u;
    out_command->turn_left = (encoded & PP_ACTION_TURN_LEFT) != 0u;
    out_command->turn_right = (encoded & PP_ACTION_TURN_RIGHT) != 0u;
    return true;
}

uint16_t pp_cell_index(uint8_t row, uint8_t col) {
    return (uint16_t)row * (uint16_t)PP_COLS + (uint16_t)col;
}

bool pp_wall_get(const uint32_t wall_bits[PP_WALL_WORDS], uint8_t row, uint8_t col) {
    if (wall_bits == 0 || row >= PP_ROWS || col >= PP_COLS) {
        return true;
    }
    uint16_t index = pp_cell_index(row, col);
    return (wall_bits[index >> 5] & (1u << (index & 31u))) != 0u;
}

void pp_wall_set(uint32_t wall_bits[PP_WALL_WORDS], uint8_t row, uint8_t col, bool value) {
    if (wall_bits == 0 || row >= PP_ROWS || col >= PP_COLS) {
        return;
    }
    uint16_t index = pp_cell_index(row, col);
    uint32_t mask = 1u << (index & 31u);
    if (value) {
        wall_bits[index >> 5] |= mask;
    } else {
        wall_bits[index >> 5] &= ~mask;
    }
}

bool pp_bfs_path(
    const uint32_t wall_bits[PP_WALL_WORDS],
    uint8_t start_row,
    uint8_t start_col,
    uint8_t goal_row,
    uint8_t goal_col,
    pp_bfs_workspace_t *workspace,
    uint8_t out_dirs[PP_MAX_BFS_PATH],
    uint16_t *out_len
) {
    if (wall_bits == 0 || workspace == 0 || out_dirs == 0 || out_len == 0) {
        return false;
    }
    *out_len = 0u;
    if (start_row >= PP_ROWS || start_col >= PP_COLS || goal_row >= PP_ROWS || goal_col >= PP_COLS) {
        return false;
    }
    if (pp_wall_get(wall_bits, start_row, start_col) || pp_wall_get(wall_bits, goal_row, goal_col)) {
        return false;
    }

    for (uint16_t i = 0u; i < PP_CELL_COUNT; ++i) {
        workspace->parent[i] = -1;
        workspace->parent_dir[i] = 0u;
    }

    uint16_t start = pp_cell_index(start_row, start_col);
    uint16_t goal = pp_cell_index(goal_row, goal_col);
    uint16_t head = 0u;
    uint16_t tail = 0u;
    workspace->queue[tail++] = start;
    workspace->parent[start] = (int16_t)start;

    while (head != tail) {
        uint16_t current = workspace->queue[head++];
        if (current == goal) {
            break;
        }
        uint8_t row = (uint8_t)(current / PP_COLS);
        uint8_t col = (uint8_t)(current % PP_COLS);
        for (uint8_t dir = 0u; dir < 4u; ++dir) {
            int16_t nr = (int16_t)row + (int16_t)pp_dir_dr(dir);
            int16_t nc = (int16_t)col + (int16_t)pp_dir_dc(dir);
            if (nr < 0 || nc < 0 || nr >= (int16_t)PP_ROWS || nc >= (int16_t)PP_COLS) {
                continue;
            }
            if (pp_wall_get(wall_bits, (uint8_t)nr, (uint8_t)nc)) {
                continue;
            }
            uint16_t next = pp_cell_index((uint8_t)nr, (uint8_t)nc);
            if (workspace->parent[next] >= 0) {
                continue;
            }
            workspace->parent[next] = (int16_t)current;
            workspace->parent_dir[next] = dir;
            workspace->queue[tail++] = next;
        }
    }

    if (workspace->parent[goal] < 0) {
        return false;
    }

    uint8_t reversed[PP_MAX_BFS_PATH];
    uint16_t length = 0u;
    uint16_t current = goal;
    while (current != start && length < PP_MAX_BFS_PATH) {
        reversed[length++] = workspace->parent_dir[current];
        current = (uint16_t)workspace->parent[current];
    }
    for (uint16_t i = 0u; i < length; ++i) {
        out_dirs[i] = reversed[length - 1u - i];
    }
    *out_len = length;
    return true;
}

uint16_t pp_estimated_ram_bytes(void) {
    return (uint16_t)(sizeof(pp_runner_t) + sizeof(pp_bfs_workspace_t) + PP_MAX_BFS_PATH);
}
