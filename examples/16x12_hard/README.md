# 16x12 Hard Map Examples

This folder contains selected high-difficulty 16-column x 12-row examples copied
from `hard_maps/`.

They are meant as ready-to-run examples for:

- PC Python solver demos.
- Android map paste/import tests.
- STM32-style performance simulation.
- GitHub README high-difficulty showcases.

Run one example:

```powershell
python main.py --hard-map hard_16x12_high_expand_083.txt --no-gui
```

Run all canonical hard maps:

```powershell
python main.py --hard-map-all --no-gui
```

All files use the MapTextCodec format:

```text
rows=12 cols=16 level=5083 heading=R recognition=false scanBombs=false allowBombPush=false
```

The coordinate convention is still 16 columns by 12 rows, with the car located
inside the grid exactly as encoded by the `P` token.
