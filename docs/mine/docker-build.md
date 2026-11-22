# Docker 构建与维护

## 本机路径和资源设置

| 项目 | 当前值 |
| --- | --- |
| 源码 | `/home/ros/lib/iKalibr` |
| 基础镜像 | 本机已有 `osrf/ros:noetic-desktop-full` |
| 运行镜像 | `ikalibr:noetic-local` |
| 构建容器 | `ikalibr-noetic-builder` |
| 容器工作空间 | `/opt/ikalibr_ws` |
| 容器源码 | `/opt/ikalibr_ws/src/ikalibr` |
| 构建限制 | 2 CPU、6 GiB、无额外 swap |
| 编译并行度 | 依赖最多 2；主程序 1，禁用 Unity Build |
| 运行限制 | 4 CPU、12 GiB、`ThreadsToUse: 4`、`OMP_NUM_THREADS=4`、`OPENBLAS_NUM_THREADS=1` |

构建和运行的限制分别由 `docker/build-image.sh` 与 `docker/run.sh` 管理。后来调整的是运行上限，构建仍保持更保守的设置。Docker 的 CPU 配额限制总 CPU 使用量，不代表进程只会创建四个线程；GUI、ROS、驱动和数学库仍可能创建其他线程。

`--memory=12g --memory-swap=12g` 表示内存上限 12 GiB，不给容器额外 swap 空间。主机自身仍可能使用 swap；容器上限也不能保证主机一定有足够可用内存。

## 构建或继续构建

```bash
cd /home/ros/lib/iKalibr

# 只检查已有镜像，不拉取。
docker image inspect osrf/ros:noetic-desktop-full

./docker/build-image.sh

docker image inspect ikalibr:noetic-local --format '{{.Id}}'
```

构建脚本会复用受限的 builder，准备依赖、编译、停止 builder，再提交为运行镜像。编译中断后可以再次执行同一命令；脚本不会启动数据集标定。

所有 `docker run` 使用 `--pull=never`。这不等于完全离线构建：`prepare.sh` 会执行 apt 更新/安装，并在依赖不存在时下载源码。

当前 `prepare.sh` 只在容器里没有项目源码时复制宿主机源码，因此复用 builder 时不要假定宿主机任意源码修改都会自动同步。`patch-*.py` 会直接修改容器内对应源码。修改 YAML、运行脚本或帮助脚本通常不需要重建镜像，因为它们运行时通过挂载读取。

## 依赖和来源记录

原项目部分 CTraj、veta、tiny-viewer 上游地址在本次搭建时无法获取，因此使用公开备份恢复：

```text
仓库：https://github.com/TQK123/iKalibr-note
固定提交：d4349fa1794d6550873722240945ad9705bd162d
```

本次恢复时核对过备份中的主项目 `src/`、`include/` 与本项目的一致性。恢复来源由脚本显式记录，没有通过关闭版权检查绕过启动。

| 依赖 | 固定版本或提交 |
| --- | --- |
| Eigen | 3.4.0 |
| Ceres | 2.2.0，shared，关闭 CUDA |
| Sophus | 1.22.10，basic logging |
| spdlog | 1.12.0 |
| magic_enum | 0.9.6 |
| Pangolin | v0.8，关闭示例、工具、Python 和视频构建 |
| ufomap | `b9de35475d78ec9523493f7e7383cce48030ab9f` |
| opengv | `91f4b19c73450833a40e463ad3648aae80b3a7f3` |
| CTraj / veta / tiny-viewer | 上述固定备份提交中的版本 |

其他依赖通过 apt 安装，包括 ROS Noetic Velodyne、OpenCV、PCL、yaml-cpp、cereal、COLMAP、Xvfb、xauth 和 Mesa。具体安装项以 `docker/prepare.sh` 为准。

## 脚本职责与容器内补丁

| 文件 | 作用 |
| --- | --- |
| `docker/build-image.sh` | 检查已有基础镜像、限制构建资源、提交运行镜像、做加载检查 |
| `docker/prepare.sh` | apt 依赖、项目初始化复制、缺失依赖源码恢复 |
| `docker/compile.sh` | 依赖编译、catkin 编译、执行补丁 |
| `docker/patch-container.py` | 非 Unity 编译的显式头文件、inline 声明修正、无窗口 viewer 自动退出开关 |
| `docker/patch-viewer.py` | 查看器四分区细黑框及左上角固定标题 |
| `docker/patch-diagnostics.py` | 增加 `[INIT-DIAG]` 日志，不改变算法或初始化阈值 |
| `docker/entrypoint.sh` | 加载 Noetic 和 catkin 环境，创建可写 ROS 目录 |
| `docker/check-startup.py` | 库加载、静态初始化与可写目录检查，不标定 |
| `docker/check-configs.py` | 数据路径、话题、部分自定义消息 MD5 和线程数检查，不标定 |

为降低模板编译内存，主程序使用单线程、关闭 Unity Build；随之补全了独立编译单元所需头文件，并移除两个仅在其他 `.cpp` 中定义的函数声明上的 `inline`。补丁作用于容器源码，宿主机算法源码保持原样。

## 日志和镜像归档

构建、启动检查和诊断构建日志位于：

```text
/home/ros/lib/iKalibr/docker/logs/
```

`docker/logs/` 被 Git 忽略。需要归档当前可运行镜像时，先确认目标文件不存在，再执行：

```bash
docker image inspect ikalibr:noetic-local --format '{{.Id}}'
docker save -o /home/ros/ikalibr-noetic-local-20261122.tar ikalibr:noetic-local
```

以后恢复：

```bash
docker load -i /home/ros/ikalibr-noetic-local-20261122.tar
```

这两条是归档操作说明，编写本文档时没有自动执行。镜像归档之外还应保存宿主机的 `docker/` 目录，因为配置和运行辅助脚本从这里挂载。
