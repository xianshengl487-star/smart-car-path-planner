# Optimization Roadmap

This note records verified optimization work and candidate next steps for the
16x12 directional smart-car planner.

## Verified In This Iteration

- Python recognition planning now uses integer states:
  `state = recognized_mask * pose_count + pose`.
- Python recognition no longer stores tuple states or per-node path copies.
- Android recognition planning now uses the same parent-pointer integer BFS.
- Python strict push search now updates numbered box tuples by index instead of
  rebuilding `{id: pos}` dictionaries for every candidate push.
- Static and dynamic deadlock checks now accept prebuilt box-position sets and
  reusable goal-position sets, reducing temporary allocation while preserving
  the same pruning rules.
- Bomb successor generation no longer sorts the full wall set. Explosions filter
  the existing sorted wall tuple, and moving a bomb only sorts the small bomb
  tuple.
- Dynamic wall checks now inline the grid bounds check on the hot path instead
  of calling `Board.inside()` for every candidate cell.
- Fixed-wall heuristic lookups now cache the `walls_tuple -> frozenset` adapter
  used after bombs are gone, reducing repeated allocation in level 103.
- Dynamic deadlock checking now computes adjacent wall flags once per candidate
  and reuses them for corner and wall-line deadlock checks.
- Main push loops now read pose-BFS reachability and stance cost directly from
  the stamped arrays instead of calling `can_reach()` and `cost_to()` for every
  candidate stance.
- The strict Python A* heuristic now adds a cheap admissible lower bound for the
  car reaching some next push stance. It uses Manhattan distance to adjacent
  stance cells and returns 0 on goal states. The stronger wall/occupancy-filtered
  version was tested first, but the cheaper unfiltered bound gave the better
  speed/complexity tradeoff.
- Python fixed-wall heuristics now use cached reverse single-box push distances
  instead of plain wall-aware grid distances. This is still admissible because
  it ignores other boxes and player routing, while every real push costs at
  least one action. Live-bomb states still use Manhattan distance because future
  explosions may remove walls.
- Python pose reachability now binds hot `deque.append` / `deque.popleft`
  methods locally inside the pose BFS, reducing CPython method-lookup
  overhead without changing the explored states or shortest-path guarantees.
- Python next-push-stance lower bound no longer allocates `boxes + bombs` or
  iterates through full direction tuples. It computes the four adjacent stance
  distances directly.
- Android native deadlock checking now avoids allocating a per-grid boolean array
  on every candidate by scanning the small box list directly.
- Android native dynamic wall checks now inline the bounds check, and
  reachability target marking uses occupancy indices instead of temporary
  `Cell` objects.
- Android strict A* now uses the same safe next-push-stance lower bound idea as
  the Python solver. It returns 0 for goal box states, so exact mode still
  preserves shortest-path optimality.
- Android fixed-wall heuristic now uses cached reverse single-box push distance
  tables when bombs cannot still remove walls. While a live bomb can change the
  wall set, it falls back to Manhattan distance to avoid overestimating.
- Android pose reachability now reuses stamped arrays and a fixed integer queue
  instead of allocating `seen`, `target`, `prev`, `action`, and `ArrayDeque`
  structures for every A* node. The pose expansion loop also uses integer
  pose/cell indexes instead of short-lived `Cell` objects.
- Android core smoke now guards strict optimal costs and rejects a level-103
  strict-search expansion regression above 10,000 nodes.
- A fixed-array Python queue was tested for pose BFS and rejected because it was
  slower than `collections.deque` on CPython. The embedded C side can still use
  fixed arrays because the runtime model is different.
- A "legal push stance only" early-stop target experiment was tested and
  rejected because it added complexity without stable speedup on the current
  maps.
- Android A* tie-breaking by smaller `g` was tested to match Python's heap order
  and rejected. It increased 103 strict expansions from 26,111 to 30,148 and
  worsened bounded-mode frontier pressure.
- Cached reverse single-box push distances are kept because they are safe and
  useful for harder fixed-wall maps, but the current default maps did not reduce
  expansions beyond the stance lower-bound result.
- Python cached reverse single-box push distances showed the same pattern on
  the default maps: no extra node reduction yet, but a stronger safe heuristic
  for future harder fixed-wall layouts.
- Reachability-result caching was measured on the previous larger level 103 and
  rejected: repeated keys were too rare for cache lookup and memory pressure to
  pay back.
- The Python strict solver returns the new 16x12 optimal costs:
  101 = 29, 102 = 65, 103 = 106. Level 103 expands 4,407 nodes on the default
  complex benchmark.
- The Android strict solver returns the new 16x12 optimal costs:
  101 = 29, 102 = 65, 103 = 106. Level 103 strict expansion is 3,860 nodes on
  the default native map.
- The map was migrated to 16x12 with the car at `(row=5, col=1)`, matching the
  first-column/fifth-row coordinate convention.
- Delivered numbered boxes now vanish on their matching target, so later routes
  can reuse that cell instead of treating it as a permanent obstacle.
- STM32 export remains fixed-memory friendly:
  max exported actions = 106, estimated runtime RAM = 968 bytes.
- Contest screenshot solving now uses a fixed 16x12 wall-grid detector and a
  two-stage exact A* matching probe. The local `比赛关卡/` batch remains 7/7
  solved and dropped from roughly 75 seconds to roughly 22 seconds.
- Python deadlock checks now inline the hot wall/bounds tests instead of calling
  `Board.is_wall()` for every neighbor, reducing the slowest contest direct
  solve by about 13 percent without changing pruning semantics.
- The directional car reachability BFS now skips parent/action recording during
  A* expansion and only records paths during final reconstruction. This keeps
  the exact same movement costs while reducing per-state BFS write traffic.
- Fixed-wall category-2 maps now bake static walls into the reachability
  workspace's forward-transition table. Per-state BFS only stamps dynamic
  blockers, while bomb maps keep the dynamic-wall path.

## Strict-Optimal Candidates

- Instance-dependent pattern databases:
  use small exact lower-bound tables for selected box subsets after fixed walls
  are known. This targets the outer A* heuristic without changing action costs.
  References:
  https://ojs.aaai.org/index.php/SOCS/article/view/18290
  https://www.ijcai.org/Abstract/16/100

- Deadlock pattern learning:
  promote recurring local deadlock shapes into cached pattern rules. A learned
  deadlock is equivalent to setting the heuristic lower bound to infinity, so it
  is safe when the pattern is proven.
  References:
  https://m.aaai.org/Library/AAAI/1998/aaai98-059.php
  https://cdn.aaai.org/AAAI/1998/AAAI98-059.pdf

- Relevance cuts for macro pushes:
  prune pushes that are unrelated to recent progress only when the relevance
  condition is proven safe for the current macro state.
  Reference:
  https://webdocs.cs.ualberta.ca/~games/Sokoban/program.html

- Bidirectional macro search:
  explore reverse/pull macro states from the numbered goal configuration and
  meet the forward search. This needs careful state connection logic to preserve
  optimality with directional car costs.
  Reference:
  https://www.ijcai.org/proceedings/2023/625

## Embedded-Bounded Candidates

- Weighted A* with explicit mode labels:
  keep the current strict mode for proofs, and expose weighted/beam modes as
  bounded engineering approximations on Android.

- Fixed-beam macro search:
  keep only the top N candidate pushes by `(g + w*h, tie_breaks)` for STM32
  simulation. This is not strict-optimal, but gives predictable RAM.

- Hierarchical push-order planning:
  first find a small candidate push or bomb sequence on an abstract board, then
  route the car between stances with fixed-array BFS.

## Grok Review Notes

Grok suggested the same broad directions: pattern databases, bidirectional macro
search, phase-aware bomb handling, memory-bounded optimal search variants, and
bounded weighted/beam modes for embedded targets. It also emitted environment
warnings because this folder is not a git repository and the local Claude
settings file failed to parse, so those suggestions were treated as advisory.
