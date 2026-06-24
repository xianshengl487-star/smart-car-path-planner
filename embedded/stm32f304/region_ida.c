#include "region_ida.h"

pp_state_t pp_pack_state(uint8_t player, uint8_t box1, uint8_t box2, uint8_t box3) {
    return ((pp_state_t)player << 24)
        | ((pp_state_t)box1 << 16)
        | ((pp_state_t)box2 << 8)
        | (pp_state_t)box3;
}

uint8_t pp_state_player(pp_state_t state) {
    return (uint8_t)(state >> 24);
}

uint8_t pp_state_box(pp_state_t state, uint8_t box_index) {
    uint8_t shift = (uint8_t)(16u - (box_index * 8u));
    return (uint8_t)((state >> shift) & 0xFFu);
}

pp_state_t pp_state_set_box(pp_state_t state, uint8_t box_index, uint8_t cell) {
    uint8_t shift = (uint8_t)(16u - (box_index * 8u));
    pp_state_t mask = ((pp_state_t)0xFFu) << shift;
    return (state & ~mask) | (((pp_state_t)cell) << shift);
}

bool pp_region_is_goal(pp_state_t state, const uint8_t goal_cells[PP_MAX_BOXES]) {
    if (goal_cells == 0) {
        return false;
    }
    for (uint8_t i = 0u; i < PP_MAX_BOXES; ++i) {
        if (pp_state_box(state, i) != goal_cells[i]) {
            return false;
        }
    }
    return true;
}

uint16_t pp_region_heuristic(
    pp_state_t state,
    const pp_region_graph_t *graph,
    const uint8_t goal_cells[PP_MAX_BOXES]
) {
    if (graph == 0 || goal_cells == 0) {
        return PP_IDA_INF;
    }
    uint16_t h = 0u;
    for (uint8_t i = 0u; i < PP_MAX_BOXES; ++i) {
        uint8_t box_cell = pp_state_box(state, i);
        uint8_t goal_cell = goal_cells[i];
        uint8_t box_region = graph->region_id[box_cell];
        uint8_t goal_region = graph->region_id[goal_cell];
        if (box_region == PP_REGION_INVALID || goal_region == PP_REGION_INVALID) {
            return PP_IDA_INF;
        }
        h += graph->region_dist[box_region][goal_region];
    }
    return h;
}

bool pp_region_path_contains(const pp_region_ida_workspace_t *workspace, pp_state_t state) {
    if (workspace == 0) {
        return false;
    }
    for (uint8_t i = 0u; i < workspace->depth; ++i) {
        if (workspace->stack[i] == state) {
            return true;
        }
    }
    return false;
}

int16_t pp_region_ida_search(
    pp_state_t state,
    const pp_region_graph_t *graph,
    const uint8_t goal_cells[PP_MAX_BOXES],
    uint16_t g_cost,
    uint16_t threshold,
    pp_region_ida_workspace_t *workspace
) {
    if (graph == 0 || goal_cells == 0 || workspace == 0) {
        return PP_IDA_INF;
    }

    uint16_t h = pp_region_heuristic(state, graph, goal_cells);
    uint16_t f = (uint16_t)(g_cost + h);
    if (f > threshold) {
        return (int16_t)f;
    }
    if (pp_region_is_goal(state, goal_cells)) {
        return 0;
    }
    if (workspace->depth >= (uint8_t)(sizeof(workspace->stack) / sizeof(workspace->stack[0]))) {
        return PP_IDA_INF;
    }

    workspace->expanded++;
    workspace->stack[workspace->depth++] = state;

    /*
     * Macro generation hook:
     * 1. Pick each box.
     * 2. Try pushing it toward neighboring regions from graph->adj.
     * 3. Reject graph->deadlock[to_cell].
     * 4. Verify player can reach push stance with pp_bfs_path or a pose BFS.
     * 5. Recurse with the packed new state.
     *
     * The hook is intentionally left data-driven so generated level headers can
     * choose between tiny static macro tables or runtime local BFS.
     */

    workspace->depth--;
    return PP_IDA_INF;
}
