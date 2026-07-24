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

## 基准优先原则

处理任何调试、移植、定制或问题复现任务时，
先建立当前环境下最小、可信、可重复的运行基准，
再引入目标改动。

- 对当前版本明确支持的 release demo、标准镜像、默认配置和已验证产物，
  优先把它们视为参考基准
- 在基准尚未跑通前，不为迎合当前现象而修改原本应当工作的逻辑
- 基准失败时，先检查版本、板型、构建、打包、加载、权限、工具和观察链路，
  不直接假设默认实现存在逻辑错误
- 基准成立后，每次只引入完成目标所必需的最小变化，
  并保留修改前后的 A/B 证据
- 已验证正常的层保持不动；问题定位沿证据逐层收敛，
  不因某个现象不明确就同时怀疑和修改所有层

release demo 不是绝对不会有缺陷，
但修改它的默认逻辑必须建立在明确证据上，
不能作为 bring-up 失败时的第一反应。

如果当前任务无法建立原始基准，
应明确记录原因和缺失条件，
不能把未经验证的状态当作基准继续向下修改。

简化成一句话：

> 先证明参考系统，再改变参考系统；先建立基准，再解释差异。

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
