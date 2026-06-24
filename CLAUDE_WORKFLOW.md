# CLAUDE_WORKFLOW.md -- Smart Car Planner

Claude is the coding body. Codex is the planner, reviewer, and final acceptance gate.

## Roles

| Role | Agent | Responsibilities |
|------|-------|-----------------|
| Brain | Codex | Plan tasks, review diffs, rerun checks, accept/reject, publish |
| Body | Claude | Implement code changes, run focused validation, report results |

## Mandatory Preflight

Before every task, verify current state -- do not trust stale summaries:

```powershell
git rev-parse --short HEAD
git status --short
```

If uncommitted changes exist from a prior incomplete turn, report them before proceeding.

## Project Invariants

1. **16x12 maps only** -- Grid is always `GridMap.ROWS=12`, `GridMap.COLS=16`. Never change dimensions.
2. **Numbered box semantics: B1->T1** -- Under `boxes_vanish_on_goal=True`, a box vanishes only when pushed onto its matching numbered target (see `solve_board` in `planner/solver.py`, the `is_delivery` check). Labels are not interchangeable.
3. **Three STM32 modes preserved** -- `strictShortest()`, `stm32Strict()`, `stm32Relaxed()` must not change. `androidNative()` is a fourth, independent mode.
4. **No GitHub publishing by Claude** -- Do not push, create PRs, or package APKs. Codex handles this.
5. **No long solver tests in CI** -- `test_hard_maps.py` solve test uses `max_expanded=120_000`. Do not increase without Codex approval.

## Task Lifecycle

1. **Read** -- `request.md`, `summary.md`, `CLAUDE_WORKFLOW.md`
2. **Verify** -- `git rev-parse`, `git status`, inspect relevant files
3. **Implement** -- Make minimal, focused changes
4. **Validate** -- Run focused tests (see below)
5. **Report** -- Changed files, command outputs, blockers

## Validation Commands

| Scope | Command |
|-------|---------|
| Hard maps | `python -m pytest tests/test_hard_maps.py -v` |
| Complex maps | `python -m pytest tests/test_complex_maps.py -v` |
| Watch script | `python -m pytest tests/test_watch_optimization.py -v` |
| All quick tests | `python -m pytest tests/test_hard_maps.py tests/test_complex_maps.py tests/test_watch_optimization.py -v` |

Do NOT run full solver benchmarks (e.g., `--max-expanded 1000000`) without explicit Codex approval.

## Delegation Prompt Template (Codex -> Claude)

```
Goal: [one-sentence goal]
Scope: [files to touch, files NOT to touch]
Constraints: [invariants to preserve]
Checks: [specific validation to run after implementation]
Deliverables: [what to report back]
```

## Correction Prompt Template (Codex -> Claude)

```
Fix: [exact issue from prior output]
File: [path and line range]
Expected: [what the code should do]
Do NOT: [things to avoid]
```

## Known Failure Modes

Observed issues in claude-body-control sessions and how to prevent them.

| Issue | What goes wrong | Mitigation |
|-------|-----------------|------------|
| Stale summary / current-state drift | Claude trusts summary.md counts or file contents that changed since last run. Reports wrong map counts, test results, or file states. | ALWAYS run `git status`, `wc -l`, or read the file before making current-state claims. Never say "12 maps" without counting. |
| Wrong semantic assumptions | Claude treats B1/B2 as interchangeable, ignores numbered target pairing, or assumes vanish semantics without checking solver code. | Before claiming box/goal semantics, read the `is_delivery` check in `solve_board`. B1 must reach T1; labels are not fungible. |
| Token / context growth | Long sessions accumulate context. Claude re-reads unchanged files, repeats exploration, wastes turns on already-answered questions. | Minimize reads by checking `git status`/`git diff` first and reading only relevant changed files. Never use cached/summary facts as current evidence -- always verify. |
| Stdout not primary evidence | Claude prints output and claims success without verifying the actual file or test result. Prints pass but file was not actually modified. | After every edit, run a verification command (git diff, pytest, wc -l) and report the output. Print statements are not proof. |
| Missing Codex verification | Claude commits or publishes without Codex review. Makes unilateral design decisions in ambiguous cases. | Claude never commits, pushes, or publishes. For ambiguous design choices, report the options with evidence and wait for Codex direction. |
| Retry loops | Claude retries a failing command multiple times without diagnosing root cause. Burns turns on the same error. | One retry max. If the retry fails, stop and report the exact error to Codex with the command that failed. |

## Failure Handoff Rules

- If a test fails: report the full output, do not retry more than once. If retry fails, hand back to Codex.
- If a file conflict occurs: report both versions, do not guess which is correct.
- If uncertain about a design decision: report the uncertainty with evidence, do not proceed blindly.
- If blocked by missing files or permissions: report the exact error and stop.

## File Map

| File | Purpose |
|------|---------|
| `planner/grid.py` | `Level` dataclass, `parse_level()`, `load_text_map()` |
| `planner/solver.py` | A* solver, `solve()`, vanish logic |
| `planner/complex_maps.py` | Built-in levels 101--106 |
| `planner/vision.py` | PNG recognition, contest batch solver |
| `android_native/.../PerformanceLimits.java` | Solve mode parameters |
| `android_native/.../MainActivity.java` | Android UI, spinner dispatch |
| `android_native/SmokeCore.java` | Java smoke tests |
| `scripts/import_boxoban_hard_maps.py` | Boxoban import pipeline |
| `scripts/watch_optimization.py` | Recurring 30-min solver checks + manifest |
| `tests/test_hard_maps.py` | Hard map discovery + validation tests |
| `tests/test_complex_maps.py` | Built-in complex map tests |
| `hard_maps/*.txt` | External hard map files |
| `hard_maps/README.md` | Map format documentation |
