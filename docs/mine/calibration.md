# 标定命令、可视化与结果

## 统一运行入口

```bash
cd /home/ros/lib/iKalibr
./docker/run.sh help
```

| 模式 | 行为 |
| --- | --- |
| `calibrate CONFIG_NAME` | Xvfb 虚拟显示，桌面不出现窗口；成功保存后自动关闭隐藏 viewer |
| `calibrate-gui CONFIG_NAME` | 桌面显示原生查看器；完成后保持窗口，关闭查看器后退出 |
| `sfm CONFIG_NAME` | 执行已导出的 COLMAP SfM 命令，不是完整标定 |
| `shell CONFIG_NAME` | 进入带挂载和资源限制的容器 shell |

配置文件位置：`/home/ros/lib/iKalibr/docker/calib-configs/<CONFIG_NAME>.yaml`。名称不带 `.yaml` 后缀。

| 可覆盖环境变量 | 默认值 |
| --- | --- |
| `IKALIBR_IMAGE` | `ikalibr:noetic-local` |
| `IKALIBR_DATASETS` | `/home/ros/dataset/calib` |
| `IKALIBR_RESULTS` | `/home/ros/dataset/calib/ikalibr-results` |

挂载关系：数据根目录 → `/datasets`（只读）；结果根目录 → `/results`（可写）；配置目录 → `/configs`（只读）；宿主机 `docker/` → `/helpers`（只读）。YAML 中使用的是容器路径。

## Robosense 已跑通的流程

### 数据和配置

原始文件：`/home/ros/dataset/robosense/mapping.bag`，约 2.1 GiB、98.47 秒。

| 数据项 | 内容 |
| --- | --- |
| LiDAR | `/rslidar_points`，`sensor_msgs/PointCloud2`，984 帧，约 10 Hz |
| IMU | `/rslidar_imu_data`，`sensor_msgs/Imu`，19,695 条，约 200 Hz |
| 点云字段 | `x/y/z/intensity/ring/timestamp`，其中 timestamp 是逐点绝对秒时间 |
| LiDAR 模型 | `RSLIDAR_POINTS` |
| IMU 模型 | `SENSOR_IMU_G`：角速度按 rad/s、加速度按 g 转换 |
| 参考 IMU | `/rslidar_imu_data` |
| IMU 内参初值 | 镜像内 `config/imu-intri.yaml`，单位映射、零偏置初值 |
| 标定时间段 | 从 bag 起点后 20 秒开始，持续 55 秒，即 20–75 秒 |
| NDT 分辨率 | 1.0 m |

原始 IMU 加速度模长约为 1，因此不能直接按 m/s² 的 `SENSOR_IMU` 读取。不要仅凭 `frame_id` 相同就认定 LiDAR 和 IMU 坐标轴定义相同。

当前成功配置是 `robosense-mapping-lowmem.yaml`。权重沿用模板初值，未作为该设备实测噪声参数验证。

### 第一步：准备降采样副本

本机已生成：`/home/ros/dataset/robosense/mapping-voxel10cm.bag`，约 375 MiB。已经存在时跳过本步骤。

需要从原始数据重建时执行以下命令；脚本拒绝覆盖已有目标文件：

```bash
cd /home/ros/lib/iKalibr

docker run --rm --pull=never \
  --cpus=2 --memory=1g --memory-swap=1g \
  --user "$(id -u):$(id -g)" \
  -e OMP_NUM_THREADS=2 -e OPENBLAS_NUM_THREADS=1 \
  -v /home/ros/dataset/robosense:/datasets:rw \
  -v /home/ros/lib/iKalibr/docker:/helpers:ro \
  ikalibr:noetic-local \
  python3 /helpers/thin-lidar-bag.py \
    /datasets/mapping.bag /datasets/mapping-voxel10cm.bag \
    --topic /rslidar_points --voxel 0.1
```

每帧每个 10 cm 体素保留一个原始点，不做质心平均；所选点的完整记录保留，包括 ring、intensity 和逐点 timestamp。IMU 不降采样，bag 记录时间和消息 header 保留。点云变为非组织形式，因此副本用于本标定流程，不替代所有下游用途的原始数据。

本次全部点数从 84,636,000 降到 14,813,628，减少约 82.5%。已核对所有 IMU 消息相等、话题消息数量一致，并抽查第一帧中每个输出点都是原始完整点记录。

### 第二步：标定

带桌面可视化：

```bash
cd /home/ros/lib/iKalibr

IKALIBR_DATASETS=/home/ros/dataset/robosense \
IKALIBR_RESULTS=/home/ros/dataset/robosense/ikalibr-results \
./docker/run.sh calibrate-gui robosense-mapping-lowmem
```

无桌面窗口：

```bash
cd /home/ros/lib/iKalibr

IKALIBR_DATASETS=/home/ros/dataset/robosense \
IKALIBR_RESULTS=/home/ros/dataset/robosense/ikalibr-results \
./docker/run.sh calibrate robosense-mapping-lowmem
```

启动时核对 `BagPath: /datasets/mapping-voxel10cm.bag`。`robosense-mapping-extended` 仍指向原始 bag，不能替代上述低内存配置。重复运行同一配置会复用结果目录，日志带时间戳，其他结果文件可能被覆盖；需要保留旧结果时先备份或更换 `IKALIBR_RESULTS`。

### 第三步：检查结果

本次输出目录：

```text
/home/ros/dataset/robosense/ikalibr-results/robosense-mapping-lowmem/
├── ikalibr_param.yaml
├── maps/lidar/
│   ├── surfel_map.pcd
│   └── gravity_aligned_map.pcd
├── splines/
│   ├── samples.yaml
│   └── knots.yaml
├── residuals/inertial_error/rslidar_imu_data/
│   ├── inertial_mes.yaml
│   └── aligned_mes_to_ref.yaml
├── ros-log/
└── run-20261122-095625.log
```

成功日志在 2026-11-22 的运行中输出了完成标记，最终地图、样条和对齐惯性测量均已保存。容器日志时间与桌面本地时间可能相差 8 小时，定位故障时应结合容器 ID 和运行 ID。

最终 YAML 中的 LiDAR 到参考 IMU 参数：

```text
topic: /rslidar_points
quaternion (qx, qy, qz, qw):
  (-0.703595601348132, 0.7106002144172402,
    0.0004243025452270329, 0.0006204845551900097)
translation (m):
  (-0.01069957022759913, -0.00760779590277242, -0.007922101887971761)
time offset (s): 0.01429440806010043
```

空间方向按本项目命名为 `SO3_LkToBr`、`POS_LkInBr`：

```text
p_Br = R_LkToBr * p_Lk + POS_LkInBr
```

时间方向可由 `src/solver/calib_solver_common_impl.cpp` 的 `CurLkToW()` 核对：

```text
t_reference_IMU = t_LiDAR + TO_LkToBr
```

因此本次是把 LiDAR 时间加约 14.294 ms 后查询参考 IMU 轨迹。转给其他 LIO 软件时，应核对其外参方向、四元数顺序和时间补偿符号，必要时求逆。以上为本次计算结果，不是独立测量的真值；几何一致性、残差与重复标定稳定性仍应结合应用检查。

## 其他已有数据集命令

默认数据根目录是 `/home/ros/dataset/calib`：

```bash
cd /home/ros/lib/iKalibr

# LI-CALIB：每个序列使用对应配置和 IMU 内参。
./docker/run.sh calibrate li-court-01
./docker/run.sh calibrate li-court-02
./docker/run.sh calibrate li-court-03
./docker/run.sh calibrate li-garage-01

# iKalibr 数据，仅 LiDAR + 雷达 + IMU。
./docker/run.sh calibrate ikalibr-data-lidar-radar-imu
./docker/run.sh calibrate ikalibr-data-1-lidar-radar-imu

# 含相机的完整配置：首次导出图像，再 SfM，再重新标定。
./docker/run.sh calibrate ikalibr-data-full
./docker/run.sh sfm ikalibr-data-full
./docker/run.sh calibrate ikalibr-data-full

./docker/run.sh calibrate ikalibr-data-1-full
./docker/run.sh sfm ikalibr-data-1-full
./docker/run.sh calibrate ikalibr-data-1-full

# VECtor，相同三步流程。
./docker/run.sh calibrate vector-small
./docker/run.sh sfm vector-small
./docker/run.sh calibrate vector-small

./docker/run.sh calibrate vector-large
./docker/run.sh sfm vector-large
./docker/run.sh calibrate vector-large
```

需要 GUI 时将对应 `calibrate` 改成 `calibrate-gui`。含相机配置第一次因要求先做 SfM 而退出，不代表完整标定成功。`run-sfm.py` 只选择导出的 COLMAP 路线，并限制 CPU 线程；是否完成取决于图像匹配和数据质量。其他配置已准备不代表所有序列均已跑通。

VECtor 使用原始畸变图像对应内参；不能套用零畸变图像的内参示例。iKalibr 自定义雷达消息按 MD5 检查后使用 `AWR1843BOOST_CUSTOM`。5 小时静态 IMU 噪声数据和离散相机标定图片没有纳入上述命令。

## GUI 和已有结果绘图

GUI 需要在本机图形桌面终端运行，有 `DISPLAY`、X11/XWayland socket 和当前用户的 xauth cookie。脚本通过临时 cookie 授权，不使用 `xhost +`，通过 Mesa 软件渲染，不依赖容器 GPU 直通。

四个分区标题及黑色细框固定在屏幕坐标：

| 位置 | 标题与含义 |
| --- | --- |
| 左上 | Sensors / extrinsics：传感器外参 |
| 右上 | Continuous-time trajectory：连续时间轨迹 |
| 左下 | Map：地图 |
| 右下 | Data association：数据关联 |

`Ctrl+S` 保存场景截图到该次输出目录；`w/s/a/d` 调整坐标系或样条显示比例，具体以窗口提示为准。GUI 模式保存结果后保留窗口，因此继续占用一定 CPU 和内存；窗口保留不代表还在优化。

对已有 LiDAR 结果绘制轨迹和传感器外参，不重新标定：

```bash
cd /home/ros/lib/iKalibr

PYTHONNOUSERSITE=1 OPENBLAS_NUM_THREADS=1 \
python3 docker/plot-results.py \
  /home/ros/dataset/robosense/ikalibr-results/robosense-mapping-lowmem
```

输出到该结果目录的 `visualizations/trajectory.png` 和 `visualizations/sensor_extrinsics.png`。需要宿主机 numpy、matplotlib、PyYAML；本机设置 `PYTHONNOUSERSITE=1` 是为了避免用户安装与系统安装的 matplotlib/mplot3d 版本混用。

## 关闭残留 GUI / 容器

先查实际名称和命令，再只关闭目标容器：

```bash
docker ps --format '{{.ID}}  {{.Names}}  {{.Image}}  {{.Command}}'

# 将容器名替换为上一步确认的标定容器名。
docker stop -t 5 <容器名>
```

等待 5 秒仍不退出时 Docker 会强制结束。结果通过宿主机目录挂载保存，停止容器不会删除已经保存的输出。不要使用“停止所有容器”或广泛的 `pkill`，以免影响其他工作。
