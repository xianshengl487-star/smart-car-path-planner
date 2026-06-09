# 路径规划算法优化版本汇总

## Baseline → v20 性能对比

| Level | Baseline (exp) | v20 (exp) | 改善 |
|-------|---------------|-----------|------|
| 101 | 36 | 33 | -8.3% |
| 102 | 41 | 38 | -7.3% |
| 103 | 4,960 | 2,916 | **-41.2%** |
| 104 | 7,664 | 5,244 | **-31.6%** |
| 105 | 20,939 | 13,384 | **-36.1%** |
| 106 | 34,572 | 19,700 | **-43.0%** |
| **Total** | **68,212** | **41,315** | **-39.4%** |

## 20轮优化列表

| 版本 | 标题 | 核心改动 |
|------|------|----------|
| v01 | Baseline | 匈牙利启发式 + 冻结死锁 + 自适应扩容 + 改进炸弹启发式 |
| v02 | Deadlock Precheck | O(1)死锁单元格检查 + 冻结死锁仅2+箱子时检查 |
| v03 | Heuristic Pruning | 匈牙利暴力枚举剪枝 + 死锁frozenset + stance优化 |
| v04 | Inline Hot Path | 内联墙壁边界检查 + is_remaining_goal优化 + frozenset死锁 |
| v05 | Max(Sum,Assignment) | max(简单求和, 最小分配)更紧启发式 (103:-4.1%, 106:-5.8%) |
| v06 | Corridor Push Board | 箱子走廊宏推 - 1宽隧道单次扩展滑到尽头 (104:-9.3%) |
| v07 | Corridor Push Bombs | solve_bombs走廊宏推 (103:-25.8%, 105:-29.1%, 106:-31.4%) |
| v08 | Wall-Line Deadlock | _is_deadlocked_dynamic增加墙壁线死锁检测 |
| v09 | Goal Tie-Break | 优先级函数增加目标距离分数 (104:-20.2%) |
| v10 | Stance Tightened | 更紧stance下界 - 4个方向取min |
| v11 | Frozen Refined | 冻结死锁实现清理 + 固定点迭代 |
| v12 | Heuristic Cleanup | 启发式清理 + 目标距离分数0.01权重 |
| v13 | Walls Frozen Cache | solve_bombs缓存walls_frozen避免重复frozenset转换 |
| v14 | Bomb Tie-Break | solve_bombs目标距离分数 + stance下界清理 (103:-11.2%, 105:-6.7%, 106:-10.7%) |
| v15 | Priority Lazy | h=0时跳过stance_lower_bound和goal_prox计算 |
| v16 | Simple Bomb Heuristic | 简化_heuristic_dynamic为直接Manhattan (103:-6.1%) |
| v17 | Push Dist Inline | _precompute_push_distances内联board.inside() |
| v18 | Explosion Inline | 内联边界检查 + 移除_is_boundary_wall |
| v19 | Heuristic Cleanup | 移除死代码_bomb_heuristic + 清理启发式 |
| v20 | Final Cleanup | 移除未使用的函数和导入, 代码精简 |

## 关键优化技术

1. **匈牙利匹配启发式**: 箱子→目标最小代价分配, max(sum, assignment)保证可采纳
2. **走廊宏推**: 1宽隧道中箱子一次滑到尽头, 大幅减少迷宫类地图扩展数
3. **冻结死锁检测**: 固定点迭代检测多箱子互相卡死的组
4. **目标距离分数**: 优先级函数的tie-breaking, 引导搜索到更接近目标的状态
5. **自适应扩容**: 接近完成时自动增加搜索预算

## 运行方式

```bash
# 运行所有关卡
python main.py --all --no-gui

# 运行基准测试
python bench.py

# 运行测试
python -m pytest tests/ -v
```
