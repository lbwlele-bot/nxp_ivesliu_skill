---
name: understanding
description: 理解层。用于沉淀那些真正高阶、会改变判断方式的抽象理解，而不是浅层提示、路径索引或命令清单。这里应该放从旧 skill 和实际 case 中抽出来的结构性认知：例如 boot-firmware / flash.bin 的本质、uuu 烧写背后的阶段切换、M 核启动归属层、同名产物在不同阶段扮演的不同角色、以及哪些观测其实是在证明“状态迁移”而不是“文件内容”。当需要先站在更高一层理解系统，再决定进入 compile / board-exec / support 时，使用这个技能。
---

# 理解层

## 使用方式

当任务还没分清：

- 当前问题属于哪个阶段
- 当前现象是在证明什么
- 当前 owner 应该落在哪一层

先读这里。

这层只做高阶分类，不做：

- 路径索引
- 命令清单
- 板级 recipe
- 具体编译步骤

读完这里后，再按当前问题按需进入主题文档，不要每次都整包展开。

## 当前重要主题

- `flash.bin` / `uuu` / relay / transport vs runtime`
  读：
  `references/flashbin-stage-model.md`
- `M` 核启动 owner 分层
  读：
  `references/mcore-owner-model.md`

新增理解如果足够重要，也优先拆成按需主题文档，
不要继续堆回这个入口页。
