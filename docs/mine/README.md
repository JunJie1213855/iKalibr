# iKalibr 本机部署与标定记录

更新日期：2026-11-22。项目目录：`/home/ros/lib/iKalibr`。

本文档记录本机已经完成的 Docker 部署、标定操作和故障处理，以实际脚本、配置、内核记录和结果文件为依据。

## 阅读入口

| 文档 | 内容 |
| --- | --- |
| [Docker 构建与维护](/home/ros/lib/iKalibr/docs/mine/docker-build.md) | 现有 Noetic 镜像、资源限制、依赖恢复、源码补丁和构建命令 |
| [标定命令与可视化](/home/ros/lib/iKalibr/docs/mine/calibration.md) | Robosense 成功流程、其他数据集、GUI、输出目录及最终参数含义 |
| [故障排查与内存问题](/home/ros/lib/iKalibr/docs/mine/troubleshooting.md) | 旋转初始化失败、6/12 GiB OOM、点云降采样、版权检查和日志目录问题 |

## 当前可用状态

- 运行环境：Docker 内 ROS1 Noetic；项目使用 catkin、roscpp 和 rosbag。
- 本地镜像：`ikalibr:noetic-local`。基础镜像使用本机已有的 `osrf/ros:noetic-desktop-full`；不拉取 Docker 镜像。
- 构建限制：容器 2 CPU / 6 GiB；依赖最多 2 线程，主程序 1 线程。
- 当前运行限制：4 CPU / 12 GiB，求解线程 4，不额外使用容器 swap。这是上限，不是内存预留。
- 已确认完成：LI-CALIB Court-01；Robosense `mapping.bag` 的降采样副本、20–75 秒 LiDAR–IMU 标定。
- Robosense 成功日志：`/home/ros/dataset/robosense/ikalibr-results/robosense-mapping-lowmem/run-20261122-095625.log`。
- Robosense 最终参数：`/home/ros/dataset/robosense/ikalibr-results/robosense-mapping-lowmem/ikalibr_param.yaml`。

完成标定以日志中的 `solving and outputting finished!!! Everything is fine!!!` 和最终参数文件为依据。初始化阶段打印的参数不能当作最终结果；程序跑完也不等于已完成独立精度验证。

## Robosense 日常运行命令

降采样副本已经存在时，直接执行：

```bash
cd /home/ros/lib/iKalibr

IKALIBR_DATASETS=/home/ros/dataset/robosense \
IKALIBR_RESULTS=/home/ros/dataset/robosense/ikalibr-results \
./docker/run.sh calibrate-gui robosense-mapping-lowmem
```

启动后必须看到：

```text
DataStream::BagPath: /datasets/mapping-voxel10cm.bag
DataStream::BeginTime: 20
DataStream::Duration: 55
DataStream::OutputPath: /results/robosense-mapping-lowmem
```

如果显示 `/datasets/mapping.bag` 或输出目录仍是 `robosense-mapping-extended`，说明还在使用原始数据配置。该配置曾在点面关联阶段耗尽内存。

标定命令由用户自行执行，构建和文档整理不自动触发标定。

## Robosense 最终外参的 SE(3) 矩阵

以下矩阵由本次最终 `ikalibr_param.yaml` 中的 `SO3_LkToBr` 和 `POS_LkInBr` 转换得到，方向为 **LiDAR `/rslidar_points` → 参考 IMU `/rslidar_imu_data`**。

原始四元数顺序为 `(qx, qy, qz, qw)`：

```text
q = (-0.703595601348132, 0.7106002144172402,
      0.0004243025452270329, 0.0006204845551900097)
t = (-0.01069957022759913, -0.00760779590277242, -0.007922101887971761) m
```

采用列向量，齐次变换矩阵 `T_IMU_LiDAR = [R, t; 0, 1] ∈ SE(3)` 为：

```text
T_IMU_LiDAR =
[
  [-0.0099056895, -0.9999508969,  0.0002847581, -0.0106995702],
  [-0.9999498438,  0.0099060995,  0.0014761594, -0.0076077959],
  [-0.0014789077, -0.0002701214, -0.9999988699, -0.0079221019],
  [ 0.0000000000,  0.0000000000,  0.0000000000,  1.0000000000]
]
```

使用方式：

```text
p_IMU = R * p_LiDAR + t
[p_IMU; 1] = T_IMU_LiDAR * [p_LiDAR; 1]
```

平移单位为米。若目标软件需要 **IMU → LiDAR**，应使用逆矩阵：`T_LiDAR_IMU = [R^T, -R^T*t; 0, 1]`。

使用未舍入数值检查时，`det(R) ≈ 1`、`||R^T R - I|| ≈ 6.4e-16`；上面的显示矩阵保留 10 位小数，数值使用时优先从原始四元数生成旋转矩阵。

时间偏移独立于 SE(3) 矩阵：

```text
t_reference_IMU = t_LiDAR + 0.01429440806010043 s
```

即 LiDAR 时间加约 **14.294 ms**。接入其他算法前，应核对其外参方向、四元数顺序和时间补偿符号。这些数值是本次标定结果，尚未经过独立精度验证。
