#ifndef SMART_CAR_REGION_IDA_H
#define SMART_CAR_REGION_IDA_H

#include "planner_core.h"

#ifdef __cplusplus
extern "C" {
#endif

#define PP_MAX_BOXES 3u
#define PP_MAX_REGIONS 20u
#define PP_MAX_REGION_ADJ 4u
#define PP_REGION_INVALID 0xFFu
#define PP_IDA_INF 0x7FFFu

typedef uint32_t pp_state_t;

typedef struct {
    uint8_t region_id[PP_CELL_COUNT];
    uint8_t adj[PP_MAX_REGIONS][PP_MAX_REGION_ADJ];
    uint8_t region_count;
    uint8_t box_target_region[PP_MAX_BOXES];
    uint8_t deadlock[PP_CELL_COUNT];
    uint8_t region_dist[PP_MAX_REGIONS][PP_MAX_REGIONS];
} pp_region_graph_t;

typedef struct {
    pp_state_t stack[32];
    uint8_t depth;
    uint16_t expanded;
    uint16_t generated;
    uint16_t pruned_deadlock;
    uint16_t pruned_cycle;
} pp_region_ida_workspace_t;

typedef struct {
    uint8_t box_id;
    uint8_t from_cell;
    uint8_t to_cell;
    uint8_t dir;
    uint8_t cost;
} pp_macro_move_t;

pp_state_t pp_pack_state(uint8_t player, uint8_t box1, uint8_t box2, uint8_t box3);
uint8_t pp_state_player(pp_state_t state);
uint8_t pp_state_box(pp_state_t state, uint8_t box_index);
pp_state_t pp_state_set_box(pp_state_t state, uint8_t box_index, uint8_t cell);
bool pp_region_is_goal(pp_state_t state, const uint8_t goal_cells[PP_MAX_BOXES]);
uint16_t pp_region_heuristic(
    pp_state_t state,
    const pp_region_graph_t *graph,
    const uint8_t goal_cells[PP_MAX_BOXES]
);
bool pp_region_path_contains(const pp_region_ida_workspace_t *workspace, pp_state_t state);
int16_t pp_region_ida_search(
    pp_state_t state,
    const pp_region_graph_t *graph,
    const uint8_t goal_cells[PP_MAX_BOXES],
    uint16_t g_cost,
    uint16_t threshold,
    pp_region_ida_workspace_t *workspace
);

#ifdef __cplusplus
}
#endif

#endif
