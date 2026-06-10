# 路径规划算法优化 — 50轮迭代总结

## 最终结果

- **41/41 测试通过**
- **43/54 导入的 Sokoban 关卡求解成功 (79.6%)**
- **6/6 内置复杂关卡全部求解成功**

## 求解率演进

| 阶段 | 求解率 | 改进 |
|------|--------|------|
| 初始 baseline (死锁 bug) | 39/54 (72.2%) | — |
| 修复 corner deadlock (`or`→`and`) | 39/54 | 修复错误剪枝 |
| 修复 wall-line deadlock (移除过度激进检查) | 42/54 (77.8%) | +3 关卡 |
| 移除 zone precheck (简单死锁区域太激进) | 43/54 (79.6%) | +1 关卡 |

## 关键 Bug 修复

### 1. Corner deadlock 检测逻辑错误
**问题**: `(up or down) and (left or right)` 判断为死锁
**修复**: `(up and left) or (up and right) or (down and left) or (down and right)`

原逻辑错误地将 `up=True, right=True` (箱子上方和右方有墙) 判定为死锁，
但实际上箱子可以向下和向左移动。正确的角落检测需要一个角的两面都被堵住。

### 2. Wall-line deadlock 过度激进
**问题**: `(left and right) and goal[1] != col` 判断为死锁
**修复**: 移除此检查

箱子在一个窄通道中 (`left=True, right=True`) 并不意味着死锁——
箱子可以向上/向下移动到开阔区域再到达目标。这个检查导致大量误判。

### 3. 简单死锁区域预计算过于激进
**问题**: `compute_simple_deadlock_zone` 从目标反向 BFS 标记不可达位置
**修复**: 在 `solve_board` 中移除此预检查

反向 BFS 在某些布局中无法正确识别可达路径（如需要穿过窄通道到达的位置）。

### 4. 导入地图 Flood-Fill 修复
**问题**: 非标准 Sokoban 地图的边界外有 `.` 格子
**修复**: 从边界 flood-fill，将所有外部格子标记为 `#`

## 版本列表 (26 个)

| 版本 | 核心改动 |
|------|----------|
| v00_baseline | Corner+2x2死锁, 匈牙利启发式, 走廊宏推 |
| v01-v20 | 20轮算法优化 (匈牙利剪枝, frozenset优化, 目标tie-breaking, 自适应扩容等) |
| v00-v05 (iter50) | 5轮参数调优 (expansion limit 50K-400K) |

## 导入的 Sokoban 关卡

- `sokoban_raw/`: 19 关卡 (KnightofLuna/sokoban-solver)
- `sokoban_raw2/`: 70 关卡 (Alonso-del-Arte/sokoban-levels: ExtremelyEasy, FrustratinglyDifficult, IllustrativeLevels, Laborious, SeeminglyHard)

## 运行方式

```bash
# 全部测试
python -m pytest tests/ -v

# 基准测试
python bench.py

# 求解所有关卡
python iter50.py

# 运行内置关卡
python main.py --all --no-gui
```
