---
name: understanding
description: 理解层。用于沉淀那些真正高阶、会改变判断方式的抽象理解，而不是浅层提示、路径索引或命令清单。这里应该放从旧 skill 和实际 case 中抽出来的结构性认知：例如 boot-firmware / flash.bin 的本质、uuu 烧写背后的阶段切换、M 核启动归属层、同名产物在不同阶段扮演的不同角色、以及哪些观测其实是在证明“状态迁移”而不是“文件内容”。当需要先站在更高一层理解系统，再决定进入 compile / board-exec / support-level 时，使用这个技能。
---

# 理解层

这个 skill 不再承担“开场总手册”的职责。
那部分已经并进 `AGENTS.md`。

这里也不应该放：

- 路径索引
- 浅层 checklist
- 命令清单
- “先问版本再问板子”这种过于表层的提示

这里应该放的是：

- 改变判断方式的抽象模型
- 能跨多个芯片 / 多个旧 skill 复用的结构性理解
- 看起来像经验，实质上决定 owner layer、artifact identity、state transition 的高阶认知

---

## 这层到底放什么

只放下面这类内容：

### 1. 运行本体层理解

例如：

- `flash.bin` 本质上是什么，不是什么
- `uuu -b sd` 实际证明了哪种状态迁移
- `M` 核启动这件事，可能由哪一层拥有
- 同一个文件名为什么不能直接推出它的运行角色

### 2. 阶段归属层理解

例如：

- 某个问题到底属于 `boot-firmware`、`linux-bsp`、`board-runtime`，还是只是 transport
- 某个现象是在证明“产物内容”，还是在证明“链路已经切换到下一阶段”
- 什么时候同一条命令在不同状态下，语义已经完全不同

### 3. 观测解释层理解

例如：

- USB 枚举变化在 boot 链里意味着什么
- 串口上看到的日志，究竟是在证明 ROM、U-Boot、Fastboot、Linux，还是只是沿用了上一个 session
- 为什么有时“烧录成功”其实只证明 transport 通了，不证明 runtime 所属关系对了

---

## 当前应沉淀的高阶抽象

下面这些是现在已经应该明确写进理解层的东西。

### 1. `flash.bin` 不是普通文件，而是阶段切换载体

不要把 `flash.bin` 仅仅理解成“一个待烧录文件”。

更准确地说，`flash.bin` 往往同时承担几种角色：

- boot-firmware 组件打包产物
- ROM 下载阶段的入口载体
- 把板子带到 `U-Boot` / `Fastboot` 能力的前置基线
- 后续更多写入动作能够成立的前提

所以讨论 `flash.bin` 时，先问的不是“这个文件在哪”，而是：

- 这个 `flash.bin` 由谁消费
- 它把系统从哪个阶段带到哪个阶段
- 它建立的是“最终运行态”，还是“下一阶段的可操作态”

### 2. `uuu -b sd <flash.bin>` 的本质，经常是“建立 Fastboot 会话”

在很多 lane 里，第一次：

```bash
uuu -b sd <flash.bin>
```

它的重要意义不只是把某个镜像写进去，
而是把板子从：

- `SDPS`

带到：

- `U-Boot`
- `Fastboot`
- 或至少是一个可继续通过 `FB` 操作的状态

所以第一次 `uuu -b sd` 的真正价值，经常是：

- 建立可继续烧录的运行时 relay

而不是“这一次就已经完成了所有最终内容”。

### 3. 第二次 `uuu -b sd`，有时依赖的不是第二个镜像里带没带 `U-Boot`

这是一个必须长期保留的高阶理解。

当第一次 `uuu -b sd flash.bin` 已经把板子带到了 live `Fastboot` session，
那么第二次：

```bash
uuu -b sd <another-flash-image>
```

之所以还能成功，
往往依赖的是：

- 第一次建立起来的 `U-Boot/Fastboot` 会话还活着

而不一定依赖：

- 第二个镜像本身再次提供完整 `U-Boot`

这意味着：

- 同样是 `uuu -b sd`
- 第一次和第二次的语义并不相同

第一次更像：

- `ROM/SDPS -> U-Boot/Fastboot`

第二次更像：

- `reuse existing Fastboot session for another write`

这也是为什么像 `i.MX8DXL` 那种两级 relay 不能被低级地理解成“连续烧两个同类 flash.bin”。

### 4. `flash.bin` 的身份，要和 transport / runtime 分开看

一个产物至少有三种身份：

- artifact identity
  它是什么打包产物
- transport identity
  它通过什么通道被送进去
- runtime identity
  它最终由谁接管、在哪个阶段生效

同一个 `flash.bin`：

- 在 `uuu` 看来，可能只是一个 raw boot image input
- 在 ROM 看来，是下载入口
- 在 `U-Boot/Fastboot` 语境里，可能是建立后续 relay 的基础
- 在最终运行链里，又可能只是更大运行结构里的起点

所以不能从“文件名一样”直接推出“运行角色一样”。

### 5. `M` 核启动，不是单一路径问题，而是 owner layer 问题

`M` 核能不能起来，首先不是“镜像有没有烧进去”这么简单。

更高一层要先问：

- 这次是谁拥有 `M` 核启动动作

常见 owner 有三层：

- `flash.bin` / boot-firmware 层
  启动职责在更早期打包和 boot flow 中
- `U-Boot` 层
  例如 `bootaux` 这类由 `U-Boot` 明确接管的启动
- Linux 层
  例如 `remoteproc` / `rproc`

这三层的差异会直接改变：

- 产物该怎么打包
- 要不要资源表
- 验证点该看哪里
- 失败时该怪 boot-firmware、U-Boot，还是 Linux runtime

所以“M 核起不来”不是单一问题，而是：

- `M` 核启动 owner 还没先分类

### 6. 同名现象，不代表同一证明强度

例如：

- 都看到 `uuu -b sd` 成功返回
- 都看到串口上有 `U-Boot`
- 都看到某个镜像被写进去了

这些表象不能自动证明同一件事。

真正要分的是：

- 这是在证明 transport 通了
- 还是在证明 stage 切换成功了
- 还是在证明 runtime owner 已经接管了

如果这三层没拆开，后面就会把：

- “能烧”
- “能启动”
- “M 核由谁启动”

混成一个问题。

---

## 与其他层的边界

- `AGENTS.md`
  放总手册和当前迁移约束
- `understanding`
  放高阶抽象、结构性理解、阶段归属模型
- `support-level`
  放资料和资源入口
- `compile`
  放模块化源码读取与编译阶段框架
- `board-exec`
  放真实板级执行

不要把下面这些东西再塞回这里：

- 资源路径
- 工具位置
- 一次性 case 命令
- 板级 recipe
- 浅层问答模板

---

## 当前最适合继续吸收的方向

就当前迁移状态，理解层最值得继续吸收的不是零散技巧，
而是 `flash.bin` 家族的共同抽象。

优先继续从下面几条旧 skill 提炼：

- `imx943-flashbin`
- `imx95-rte33-build-flashbin`
- `imx93-generic-deploy-cycle`
- `imx8dxl-board-control`

目标不是把它们的命令搬过来，
而是把它们背后共同成立的东西抽出来：

- `flash.bin` 的阶段角色
- `uuu` 的阶段切换本质
- `Fastboot` relay 的复用条件
- `M` 核启动 owner 的分层模型
