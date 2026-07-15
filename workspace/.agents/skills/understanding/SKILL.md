---
name: understanding
description: Use when starting an NXP i.MX workspace task or when a problem involves conceptual owner routing, flash.bin/uuu stage semantics, transport vs runtime, M core owner layers, or state-transition evidence before choosing support, compile, or board-exec.
---

# 理解入口层

## 使用方式

这里是必读入口页，但不是知识大全。

开工后先读这一页，用它判断：

- 当前问题属于哪个阶段
- 当前现象是在证明什么
- 当前 owner 应该落在哪一层
- 是否必须继续读取某个 `references/*.md`

读这一页之后只能有两种结果：

- 命中下方主题触发条件：必须继续读对应 reference，再决定下游 owner
- 未命中任何主题：立刻转到 `support`、`compile` 或 `board-exec`

不要因为读了入口页，就把整个 `references/` 目录都放进上下文。

## 这里不做什么

- 路径索引
- 命令清单
- 板级 recipe
- 具体编译步骤
- 资源位置查询
- 普通工具用法说明

这些分别交给：

- `support`
- `compile`
- `board-exec`
- 具体目录 README / 工具 `USAGE.md`

## 主题路由表

### `flash.bin` / `uuu` / transport vs runtime

触发条件：

- 问题涉及 `flash.bin`、boot-firmware、`uuu -b sd`
- 现象里出现 `SDPS`、`FB`、Fastboot relay、下载态到 `U-Boot` 的阶段切换
- 用户或日志把“传输成功”“烧写成功”“运行态成功”混在一起
- 同名产物在不同阶段扮演的角色不清楚

命中后必须读：

- `references/flashbin-stage-model.md`

读完后再决定进入：

- `support`
- `compile`
- `board-exec`

### `M` 核 / 异构核 owner 分层

触发条件：

- 问题涉及 `M` 核、`bootaux`、`remoteproc`、`rproc`
- 需要判断某个 payload 由 `flash.bin`、`U-Boot` 还是 Linux 接手
- 需要判断哪些核是保留核、哪些核属于当前 case 目标
- 现象看起来像“镜像在不在”，但真正问题可能是 owner layer 不清楚

命中后必须读：

- `references/mcore-owner-model.md`

读完后再决定进入：

- `support`
- `compile`
- `board-exec`

## 维护规则

新增理解如果足够重要，也优先拆成按需主题文档，
不要继续堆回这个入口页。

入口页只保留：

- 主题名称
- 触发条件
- 必读 reference
- 读完后可能进入的下游 owner
