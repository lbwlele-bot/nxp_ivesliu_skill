# NXP_v2 架构升级说明 V2

## 1. 这份文档是什么

这份文档不是当前系统主手册的直接替代品。

它的角色是：

- 对现有 `NXP_v2` 架构的 **V2 升级说明**
- 解释这次为什么要引入 `project state`
- 解释它和现有四个主 owner 的关系
- 解释这次升级改变什么，不改变什么

这份文档**不是**：

- 旧版 [ARCHITECTURE.md](/home/ives/桌面/NXP_v2/workspace/ARCHITECTURE.md) 的直接替身
- 当前系统的唯一 authoritative source
- 施工手册
- 工具手册

当前系统的现行入口规则，仍然以：

- [AGENTS.md](/home/ives/桌面/NXP_v2/workspace/AGENTS.md)
- [ARCHITECTURE.md](/home/ives/桌面/NXP_v2/workspace/ARCHITECTURE.md)

为准。

这份 V2 文档只负责说明：

- 这次新增的控制面升级是什么
- 它应该如何挂接到现有系统
- 它和现有 owner 边界怎么配合

---

## 2. V2 要解决的问题

现有 `NXP_v2` 已经有清晰的主 owner 分层：

- `understanding`
- `support`
- `compile`
- `board-exec`

这套分层可以解决“当前 unresolved step 属于哪一层”的问题，
但它还没有稳定解决另一类问题：

- 当前 case 的关键事实如何持续保留
- `compile` 到 `board-exec` 之间如何稳定交接
- agent 如何避免只靠对话上下文记住当前进展
- 同一个 case 经过多轮试验、重启、重编后，下一位 reader 如何快速恢复当前状态

换句话说，现有系统更强的是：

- owner 路由
- 资源定位
- 编译对象判断
- 板级动作判断

而这次 V2 想补强的是：

- case 级事实维护
- 交接对象显式化
- 证据与判断的稳定落盘

所以这次升级不是要重做四主层，
而是要在四主层之上补一个更稳定的控制面约定。

---

## 3. V2 的核心升级点

V2 的核心不是“再增加一个主流程层”，
而是增加一组跨层控制概念。

### 3.1 引入 `project state`

这里的 `project state` 指的是：

- 当前项目为了继续推进，系统需要显式维护的总体控制状态

它不是单指板状态。

其中板级状态只是一个子域。

### 3.2 引入 case 级状态账本

V2 认为当前 case 不应只保留：

- 日志
- 产物
- 脚本
- 补丁

还应保留一份更稳定的控制面事实，
用来回答“现在我们到底知道什么”。

这里要强调：

- 施工阶段先定义机制、owner 和最小模板
- 真实 `ledger` 实例只在真实 case 运行时落到 case 目录
- 它不应先被设计成一份覆盖所有 CPU / 所有启动链的大状态表

### 3.3 引入显式交接对象

`compile` 到 `board-exec` 之间，
当前最容易靠口头和上下文记忆维持。

V2 建议把这种交接显式化，
形成可落盘、可复查、可被 agent 直接读取的 case 级交接对象。

这里同样要强调：

- 施工阶段先定义 `handoff` 的生成规则和最小模板
- 模板 owner 在 `compile`
- 真实 `handoff` 实例只在 case 真正从 `compile` 切到 `board-exec` 时生成

### 3.4 引入“事实 -> 证据 -> 判断”的维护方式

V2 不建议维护一个大而全状态机。

它建议维护的是：

- 当前事实
- 当前证据
- 基于证据的派生判断
- 基于判断允许的下一步动作

这样可以减少：

- 只凭命令返回值脑补状态
- 只凭旧日志脑补当前事实
- 只凭串口沉默就误判板子状态

---

## 4. V2 的机制模型

V2 这一阶段不追求一套覆盖所有 case 的硬状态机。

它更接近三类机制拼起来的控制面：

### 4.1 路由机制

它回答：

- 当前 unresolved step 属于哪一层
- 当前 owner 是谁
- 当前问题是在理解、资源、编译还是板级执行阶段

这部分继续由现有四个主 owner 负责，
不是 V2 新增的重点。

### 4.2 交接机制

它回答：

- `compile` 什么时候需要向 `board-exec` 交接
- 交接对象至少要表达什么
- 交接模板由谁拥有

在 V2 第一阶段：

- `compile` owns `handoff`
- `handoff` 是交接机制，不是施工阶段必须先手工创建的实例
- 真实 `handoff` 只在 case 真正进入跨阶段执行时生成

### 4.3 动态事实机制

它回答：

- 当前 case 为继续推进必须记住的最小动态事实是什么
- 这些事实凭什么成立
- 下一步允许且推荐做什么

在 V2 第一阶段：

- `board-exec` owns `ledger`
- `ledger` 不是整板总状态机
- `ledger` 只保留当前 case 最关键的动态事实
- 推荐最小视图是 `focus / current_fact / evidence / next_action / notes`

### 4.4 证据原则

V2 的关键不是状态名越多越好，
而是当前判断是否真的有新鲜证据支撑。

所以它强调：

- 旧观察不能自动覆盖当前 fresh probe
- 某个动作成功不等于后续阶段已经成立
- 原始证据继续留在 `logs/`
- `ledger` 只写摘要，不替代原始日志

---

## 5. V2 与现有 owner 的关系

这一章是 V2 最容易被误解的地方。

### 5.1 四个主 owner 不变

V2 不改变当前系统的四个主 owner：

- `understanding`
- `support`
- `compile`
- `board-exec`

当前 unresolved step 仍然先按 [AGENTS.md](/home/ives/桌面/NXP_v2/workspace/AGENTS.md) 路由，
而不是先进入一个新层。

### 5.2 `project state` 不是第五个主 owner

`project state` 的角色不是：

- 接管当前问题
- 代替 `compile`
- 代替 `board-exec`
- 成为新的统一入口

它的角色是：

- 为当前 owner 提供稳定的 case 控制面约定
- 规定哪些事实应该显式保留
- 规定交接对象应该怎样表达

### 5.3 当前问题仍然归现有 owner 处理

例如：

- 问题本质没分清，仍然归 `understanding`
- 资源位置没分清，仍然归 `support`
- 编译对象没分清，仍然归 `compile`
- 板状态没分清，仍然归 `board-exec`

V2 只要求：

- 当前 owner 在处理自己这一层问题时，
  能把关键事实更稳定地留在 case 里

### 5.4 谁维护项目进展

V2 不建议引入一个单独角色全程悬在上方维护一切。

更稳的责任模型是：

- 当前活跃 owner 负责回写自己这一层带来的状态变化
- `project state` 负责规定这些状态应该怎样落盘

也就是说：

- `compile` 负责自己的交接事实和 `handoff` 模板
- `board-exec` 负责自己的动态事实和 `ledger` 模板
- `support` 负责资源和来源上下文
- `understanding` 负责高层模型修正

---

## 6. V2 的规则 owner 边界

V2 最重要的不是“多一个概念”，
而是不能把规则 owner 搞乱。

### 6.1 `project state` 拥有什么

`project state` 拥有的是控制面约定，例如：

- case 状态账本的角色
- 交接对象的角色
- 哪类信息该落在账本
- 哪类信息该落在交接对象
- 模板 owner 和运行时实例的边界

它不拥有：

- 编译对象判断规则
- 板级动作守门规则
- 某块板的默认恢复动作
- 所有字段的最终统一 schema

### 6.2 `compile` 拥有什么

`compile` 继续拥有：

- 编译对象路由
- 最小依赖集合判断
- 构建身份收敛
- 何时切到 `board-exec`

这些规则仍然应以现有 `compile` skill 和其下游文档为准。

V2 只是建议把其中一部分高层判断，
未来再显式落成 case 级交接对象。

第一阶段里，
`compile` 还额外拥有：

- `handoff` 的最小模板
- `handoff` 的生成时机

### 6.3 `board-exec` 拥有什么

`board-exec` 继续拥有：

- 当前板状态 / 目标板状态判断
- 当前最强状态信号判断
- 阶段守门规则
- 异构核 owner 约束
- 当前允许的下一步板级动作

这些规则仍然应以现有 `board-exec` skill 和其下游文档为准。

V2 不改写它的主职责，
只希望让它读取到更稳定的 case 交接事实。

第一阶段里，
`board-exec` 还额外拥有：

- `ledger` 的最小模板
- `ledger` 的更新节奏
- fresh probe 优先于旧上下文的规则

### 6.4 `board_knowledge` 拥有什么

某块板的默认事实和特例，继续留在板知识层，例如：

- 默认串口
- 默认下载态识别方式
- 固定保留核
- 某板专属恢复动作
- revision 特定风险

这些不应被吸进 `project state`。

### 6.5 case 临时规则放哪里

当前 case 里临时成立、但还没证明值得升级成共享规则的内容，
应当先留在 case 本身。

等被多次证明可复用后，
再决定是否提升到：

- `compile`
- `board-exec`
- `board_knowledge`
- `to_absorb/`

---

## 7. V2 的升级范围

这章用来避免“现状”和“提案”继续混写。

### 7.1 本次明确新增

V2 本次明确新增的是：

- `project state` 作为跨层控制概念
- case 级状态账本的架构地位
- case 级交接对象的架构地位
- “事实 -> 证据 -> 判断” 的控制面思路
- `project state` 与现有四主 owner 的边界定义
- 模板 owner 与运行时实例的边界定义

### 7.2 保持现状不变

V2 当前不改变这些东西：

- 四个主 owner skill
- [AGENTS.md](/home/ives/桌面/NXP_v2/workspace/AGENTS.md) 的入口路由
- `workspace` 与 `../support_level/` 的层级边界
- `compile` 当前已承诺的正式输出边界
- `board-exec` 当前已承诺的正式输出边界
- 板特例继续留在 `board_knowledge`

### 7.3 第二阶段再考虑

下面这些不是本次必须落地的现状项：

- 把 handoff 做成稳定 schema
- 用统一 schema 覆盖所有 CPU / 所有 case
- 给 case 状态账本加自动校验
- 增加辅助 `project-state` skill
- 增加读写账本的辅助脚本

也就是说，它们属于：

- V2 方向上的增强项

而不是：

- 当前系统已经完成的既有 contract

---

## 8. 阅读与配套文档

建议按问题类型来选文档，而不是把 V2 文档误当主入口。

### 8.1 看现行系统怎么工作

先读：

- [AGENTS.md](/home/ives/桌面/NXP_v2/workspace/AGENTS.md)
- [ARCHITECTURE.md](/home/ives/桌面/NXP_v2/workspace/ARCHITECTURE.md)

### 8.2 看这次 V2 为什么要升级

读：

- [ARCHITECTURE_V2.md](/home/ives/桌面/NXP_v2/workspace/ARCHITECTURE_V2.md)

### 8.3 看 V2 具体怎么施工落地

读：

- [CONSTRUCTION_V2.md](/home/ives/桌面/NXP_v2/workspace/CONSTRUCTION_V2.md)

### 8.4 看具体执行

继续按现有入口下沉到：

- `understanding`
- `support`
- `compile`
- `board-exec`

而不是把这份 V2 文档当成新的统一操作手册。
