# Hard Maps

Drop `.txt` map files here. Tests automatically discover, parse, and solve them
with a generous budget.

The current sample set is converted from
[DeepMind Boxoban hard levels](https://github.com/google-deepmind/boxoban-levels)
(`hard/000.txt`). Classic Sokoban maps allow any box to reach any target, while
this project requires fixed numbering (`B1 -> T1`, etc.), so imported maps are
screened by the project solver before being committed.

## Format

Each file is a 16×12 grid in MapTextCodec text format:

```text
// Optional comment lines
// SmartCarPlannerMap v1
rows=12 cols=16 level=201 heading=R recognition=false scanBombs=false allowBombPush=false
. . # # # . . . . # # # # . . .
. P . . . . . . . . . . . . . .
...
```

### Header Fields
| Field | Values | Default | Notes |
|-------|--------|---------|-------|
| `level` | int ≥ 101 | 201 | Used for levelId in decode |
| `heading` | U/D/L/R | R | Start heading |
| `recognition` | true/false | false | Requires approach recognition |
| `scanBombs` | true/false | false | Must scan for bombs |
| `allowBombPush` | true/false | false | Bombs can be pushed |

### Tokens
| Token | Meaning |
|-------|---------|
| `.` | Empty cell |
| `#` | Wall |
| `P` | Player start |
| `1`–`4` | Boxes (B1–B4) |
| `a`–`d` | Targets (T1–T4) |
| `X` | Bomb |
| `B1`–`B4` | Boxes, human-readable form |
| `T1`–`T4` | Targets, human-readable form |

### Row Format
- **Spaced**: tokens separated by spaces: `. . # # # . . . .`
- **Compact**: 16 consecutive characters: `..........#####..`

Both are accepted. Rows must be exactly 16 tokens; there must be exactly 12 rows.

## Naming Convention
Use descriptive names: `hard_4box_deadlock.txt`, `hard_bomb_chain.txt`, etc.
The file stem becomes the Level name in test output.

## Import More Boxoban Maps

```powershell
python scripts\import_boxoban_hard_maps.py --limit 10 --scan 200 --max-expanded 120000
python -m pytest tests\test_hard_maps.py -v
```

## Recurring 30-Minute Checks

```powershell
python scripts\watch_optimization.py --interval-seconds 1800 --include-contest
```

Use `--once` for a single local verification run.
