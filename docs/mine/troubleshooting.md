# 故障排查与内存问题记录

## 本次排查过程

| 阶段 | 输入与设置 | 结果及依据 |
| --- | --- | --- |
| 初次 Robosense | 原始 bag，40–70 s，NDT 0.5 m | 外参旋转初始化失败 |
| NDT 对照 | 同一时间段，NDT 1.0 m | 仍失败，说明单改分辨率没有解决问题 |
| 加诊断日志 | 同一时间段、同一阈值 | NDT 采样日志均报告收敛；第三奇异值最终 0.243811，未满足 `> 0.25` |
| 扩展时间段 | 原始 bag，20–75 s，NDT 1.0 m，6 GiB | 通过初始化，在第一轮批量优化准备阶段触发容器 OOM |
| 提高运行上限 | 4 CPU / 12 GiB，仍用原始 bag | 一次触发宿主机整体 OOM；后续重跑触发 12 GiB 容器 OOM |
| 最终有效流程 | 10 cm 点云降采样副本，20–75 s，NDT 1.0 m，4 CPU / 12 GiB | 完成求解及地图、样条、对齐惯性测量输出，参数文件已生成 |

对应配置：

| 配置名 | BagPath | 用途 |
| --- | --- | --- |
| `robosense-mapping` | `/datasets/mapping.bag` | 最初 30 秒、NDT 0.5 m |
| `robosense-mapping-ndt1` | `/datasets/mapping.bag` | 30 秒、NDT 1.0 m 对照 |
| `robosense-mapping-extended` | `/datasets/mapping.bag` | 55 秒，旋转初始化能通过，但原始点云内存过高 |
| `robosense-mapping-lowmem` | `/datasets/mapping-voxel10cm.bag` | 本次成功配置，55 秒 |

## 为什么 `exit code -9`

`-9` 表示进程收到 SIGKILL。仅凭这一数字不能断言是 OOM，也可能是手动强制终止；本次由内核记录确认了内存原因。

查询：

```bash
journalctl -k --since '30 minutes ago' --no-pager \
  | rg -i 'oom-kill:|Killed process|Memory cgroup out of memory|Out of memory'

docker stats --no-stream
```

本次关键记录（宿主机本地时间）：

| 时间 | 内核证据 | 解释 |
| --- | --- | --- |
| 2026-11-22 17:38:19 | `CONSTRAINT_MEMCG`，`Memory cgroup out of memory`，anon-rss 6,205,684 kB | 达到 6 GiB 容器内存限制 |
| 2026-11-22 17:47:38 | `CONSTRAINT_NONE`，`global_oom`，anon-rss 10,067,952 kB | 宿主机整体内存不足，容器尚未用满 12 GiB 也可能被杀 |
| 2026-11-22 17:54:13 | `CONSTRAINT_MEMCG`，anon-rss 12,483,964 kB | 仍用原始 bag，达到 12 GiB 容器限制 |

这些 RSS 数字是被杀进程的匿名内存，不是完整容器账单；容器还有共享内存、页缓存等开销。主机约 15.5 GiB RAM，桌面与其他进程也要内存，因此提高容器上限不能保证安全通过。

`--rm` 会在退出后删除运行容器，事后不一定还能通过 `docker inspect` 查询它的 OOM 状态。此时用内核日志中的完整容器 ID 与 roslaunch 主机名/运行日志匹配。

## 为什么 bag 只有 2.1 GiB，进程却能用十几 GiB

磁盘消息大小不等于算法工作内存。当前实现会同时或阶段性持有：

1. 从消息转换后的 PCL 点云。点类型包含时间戳并有内存对齐开销。
2. 原始扫描、去畸变扫描、变换到地图坐标的扫描，以及全局地图副本。
3. NDT 点云、空间索引、surfel 树和可视化实体。
4. 点面对应关系中的时间、向量、平面参数、权重、共享指针和容器开销。
5. 随后的优化问题、残差与求解器工作区。

本次被杀位置在点面关联附近，尚未完成第一轮批量优化；不能把它简单归因于 Ceres 矩阵太大。

源码依据：

- `src/solver/calib_solver_init_prep_bo_impl.cpp`：生成去畸变帧在地图中的副本，并累加到全局地图。
- `src/solver/calib_solver_da_impl.cpp` 的 `DataAssociationForLiDARs()`：使用 dense map 创建关联器；逐帧累积所有 `PointToSurfelCorr`，全部收集后才抽样。
- `src/config/configor.cpp`：每扫描目标关联数 `PointToSurfelCountInScan = 200`。这个目标不会阻止抽样前的大量对应关系先占用内存。
- `include/factor/data_correspondence.h`：每条对应关系包含多个 double/Eigen 向量等信息。

因此，“最终每帧只用约 200 条约束”不能解释为“全流程只分配这么多内存”。`Prior::MapDownSample` 在相关函数里主要用于地图显示采样；关联器仍接收 dense map，单改显示采样参数也不能保证降低关联峰值。

htop 若显示多个同名线程，RES 通常是共享的进程内存，不能把每行的 RES 相加。CPU 配额或线程数主要控制并行度，也不会消除密集点云的存储需求。

## 已有效的内存解决方案

在进入标定前，对每帧点云做 10 cm 体素筛选，每格保留一个真实点，避免将逐点时间戳平均掉。对应工具：

```text
/home/ros/lib/iKalibr/docker/thin-lidar-bag.py
```

原始 bag 保持不变，副本为：

```text
/home/ros/dataset/robosense/mapping-voxel10cm.bag
```

全数据点数从 84,636,000 降到 14,813,628，文件约 375 MiB。逐点时间戳和 IMU 时间连续性保留，空间采样密度发生变化。运行成功证明这次数据与配置可在当前环境完成，不代表所有场景都适合相同体素大小。

必须使用 `robosense-mapping-lowmem`，并检查启动输出：

```text
DataStream::BagPath: /datasets/mapping-voxel10cm.bag
DataStream::OutputPath: /results/robosense-mapping-lowmem
```

本次曾在生成副本之后继续运行 `robosense-mapping-extended`，完整日志明确仍读取 `/datasets/mapping.bag`，因此没有获得降采样的内存收益。不要只看“副本文件已经存在”，要看本次运行实际加载的配置与 BagPath。

没有记录成功运行的精确峰值内存，因此本文不声称其固定低于某个更小容量。后续可在用户运行时使用 `docker stats` 记录；不再通过无上限增加 RAM 或 swap 掩盖数据规模问题。

## 旋转初始化失败如何判断

原始提示：

```text
initialize rotation 'SO3_LkToBr' failed,
this may be related to the 'NDTResolution' of lidar odometer.
```

这是一条泛化错误，不能直接推断“分辨率一定错误”。源码 `src/core/rotation_estimator.cpp` 使用 SVD，检查有效旋转对的数量和第三奇异值；本次实际未通过的判据为 `cov(2) > 0.25`。

诊断补丁记录：

```text
[INIT-DIAG] NDT frame=..., converged=..., source points=...,
map points=..., fitness=..., step angle=..., step translation=...
[INIT-DIAG] rotation pairs=..., singular values=[...], required third > 0.25
```

40–70 秒时第三奇异值最终是 0.243811。扩大到 20–75 秒后通过初始化。本次没有降低 0.25 阈值，也没有跳过检查。

NDT 的 `converged=true` 只表示其数值停止判据满足，不能单独证明配准正确。奇异值过阈值也不等于外参已准确；后续仍需优化和结果检查。

## 版权检查启动失败

曾出现：

```text
Do not tamper with the Copyright of iKalibr in file '...'
```

原因是早期补丁把新增 `#include` 插在文件第一行之前，破坏了启动检查对文件前 11 行版权标识的读取。解决方式是把新增 include 移到完整原始版权声明之后，保留检查，不禁用检查函数。

当前 `patch-container.py` 会处理该问题并保持幂等。不能通过删除声明或关闭版权检查来“修复”。

## ROS 日志目录无法写入

曾出现 `/tmp/.ros/log` 不存在或不可写。当前入口脚本预建、检查可写的 `ROS_HOME` 和 `ROS_LOG_DIR`；运行脚本把日志指向：

```text
/results/<配置名>/ros-log/
```

容器按宿主用户 UID/GID 运行。出现权限错误时检查宿主结果目录的属主和挂载，不应改成所有文件全局可写。

## GUI 不退出、required 节点提示与成功判断

- GUI 模式不设置自动关闭环境变量，保存结果后等待用户看图，属于设计行为。
- 无窗口模式设置 `IKALIBR_AUTO_CLOSE_VIEWER=1`，在保存完成后关闭隐藏 viewer。
- Ctrl+C 多次后终端可能先退出，但容器或 viewer 仍存活。查 `docker ps`，只对确认的标定容器执行 `docker stop -t 5 <容器名>`。
- launch 中标定节点是 `required=true`，因此出现 `REQUIRED process ... has died` 不一定是失败；若是 `finished cleanly` 且有完整成功标记与参数文件，可能只是正常收尾。
- `exit code -9` 配合上述 OOM 内核记录则是失败，初始化参数不可用。
- 上游主程序可能捕获异常后返回 0，不能只看退出码。`run.sh` 同时检查完成标记和参数文件。

新建临时 xauth 文件前已加 `touch` 和权限设置，消除了初次 GUI 命令中的 `Xauthority does not exist` 提示；它不是此前旋转初始化失败的原因。

## 结果检查

本次成功运行输出过初始化平移约 `(-0.427, -0.012, -0.102) m`，而最终 YAML 平移约 `(-0.01070, -0.00761, -0.00792) m`。这说明应读取最终文件，不能截取中间日志当作标定结果。

`residuals/inertial_error/` 中保存的是惯性测量及对齐结果，不应仅凭目录名称把所有内容都当作最终优化残差统计。轨迹、外参和点云可视化用于检查几何关系，也不能替代独立精度评估。
