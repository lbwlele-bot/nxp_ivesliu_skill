# NXP_v2 施工手册 V2

## 1. 这份手册只回答什么

这份手册不再展开“从零搭一个完整系统”的泛化背景。

它只回答一个问题：

- `project state` 这套机制，怎么嵌进我们当前 `NXP_v2` 系统

当前现行入口和主 owner 不变，仍然以：

- [AGENTS.md](/home/ives/桌面/NXP_v2/workspace/AGENTS.md)
- [ARCHITECTURE.md](/home/ives/桌面/NXP_v2/workspace/ARCHITECTURE.md)

为准。

这次 V2 只补一层控制约定，不重做主架构。

---

## 2. 第一阶段到底改什么

第一阶段只改 5 个落点：

1. [AGENTS.md](/home/ives/桌面/NXP_v2/workspace/AGENTS.md)
   增加全局状态维护规则。
2. [.agents/skills/support/SKILL.md](/home/ives/桌面/NXP_v2/workspace/.agents/skills/support/SKILL.md)
   增加 case 容器准备与状态文件定位规则。
3. [.agents/skills/compile/SKILL.md](/home/ives/桌面/NXP_v2/workspace/.agents/skills/compile/SKILL.md)
   增加 `compile -> board-exec` handoff 生成规则与最小模板 owner。
4. [.agents/skills/board-exec/SKILL.md](/home/ives/桌面/NXP_v2/workspace/.agents/skills/board-exec/SKILL.md)
   增加板级动作前后读写 ledger 的规则与最小模板 owner。
5. 当前 case 目录
   定义运行时实例落点，供真实 case 进入执行阶段时落盘。

第一阶段不做这些事：

- 不新增第五个主 owner
- 不先做独立 `project-state` skill
- 不先做服务化、数据库或自动执行引擎
- 不先把 schema 设计成很重的校验系统
- 不把 `compile` 和 `board-exec` 合并成一个总控层

一句话概括：

- 这次不是“做一个状态机程序”
- 而是“给现有入口和现有 skill 补状态维护协议”

---

## 3. 状态机制怎么嵌进现有系统

### 3.1 基本原则

- `project state` 不是第五个主 owner
- 当前 unresolved step 仍然先在 `understanding` / `support` / `compile` / `board-exec` 之间路由
- 状态不放全局，不放 skill 内部，放具体 case 目录
- 谁产生日志和新事实，谁负责把本层该落的内容写回 case

### 3.2 状态文件放哪里

以下路径统一站在当前 `workspace/` 视角：

```text
../support_level/work/<case>/
  README.md
  state/
    handoff.yaml
    ledger.yaml
  logs/
  journal/
    timeline.md   # 可选
```

这里描述的是运行时实例落点，
不是施工阶段必须先手工创建的一批文件。

也就是说：

- 现在施工阶段先定义规则、owner 和最小模板
- 只有真实 case 跑到对应阶段时，才在这里生成具体实例

真实 case 进入跨阶段推进后，
第一阶段最小必需的是：

- `README.md`
- `state/handoff.yaml`
- `state/ledger.yaml`
- `logs/`

`journal/timeline.md` 可先保留为可选。
如果某次 case 需要额外解释判断过程，再写它。

### 3.3 `handoff` 机制是什么

`handoff` 是 `compile` 写给 `board-exec` 的交接机制。

在施工阶段，我们现在要定义的是：

- 什么情况下需要 `handoff`
- `compile` 如何生成它
- `compile` 持有怎样的最小模板
- `board-exec` 如何消费它

不是现在就去手工创建一批真实 `handoff.yaml`。

真实 case 只有在从 `compile` 切到 `board-exec` 时，
才会在当前 case 下生成或更新 `state/handoff.yaml`。

它至少要能回答：

- 这次产物是什么
- 产物从哪来
- 这次准备交给板上哪一步去消费
- 上板前提是什么
- 上板时优先要验证什么

第一阶段不要求复杂 schema，
但 `compile` 持有的最小模板至少要能表达：

- producer 是哪个 owner
- artifacts 是什么
- 预期交给哪个执行阶段消费
- preconditions
- verification focus

### 3.4 `ledger` 机制是什么

`ledger` 是 `board-exec` 维护的 case 级动态事实摘要。

在施工阶段，我们现在要定义的是：

- 什么情况下需要 `ledger`
- `board-exec` 如何读取和更新它
- `board-exec` 持有怎样的最小模板
- 哪些内容该写进 `ledger`，哪些仍然留在 `logs/`

不是现在就去手工创建一批真实 `ledger.yaml`。

真实 case 只有在进入真实板级执行时，
才会在当前 case 下生成或更新 `state/ledger.yaml`。

`ledger` 不是整板状态机，也不是固定绑定 A55 `ROM -> U-Boot -> Linux` 的大状态表。

它只负责保留：

- 当前 case 正在推进哪条线
- 当前最关键的动态事实是什么
- 这条事实最强的证据是什么
- 下一步允许且推荐做什么
- 当前不能忘的约束或提醒是什么

第一阶段推荐 `board-exec` 持有的最小模板是：

- `focus`
- `current_fact`
- `evidence`
- `next_action`
- `notes`
- `last_action` 可选

### 3.5 谁负责写什么

#### `support`

只负责：

- 建立或复用当前 case
- 告诉 agent 当前状态文件放哪
- 把资源上下文和 case 路径说清楚

它不负责：

- 判断当前板级动态事实
- 维护 handoff 模板或内容
- 代替 `board-exec` 写运行态结论

#### `compile`

负责：

- 定义并持有 `handoff` 的最小模板
- 当真实 case 已经明确要切到 `board-exec` 时，生成或更新 `state/handoff.yaml`
- 把“这次编出来的是什么、准备交给谁、下一步怎么验证”写清楚

它不负责：

- 判断板当前实际运行到哪一步
- 用编译成功去替代板级验证成功

#### `board-exec`

负责：

1. 动板前先读当前 case 状态
2. 如果存在 `handoff`，先按它理解这次要消费什么
3. 重新探测当前最强状态信号
4. 根据 fresh probe 更新 `ledger`
5. 执行动作
6. 动作后重新探测
7. 再更新 `ledger`
8. 保存原始输出到 `logs/`

它是第一阶段状态维护的核心 hook 点。

它同时负责：

- 定义并持有 `ledger` 的最小模板
- 保证 `ledger` 只记录当前 case 最重要的动态事实

#### `understanding`

不负责逐步维护 case 状态文件。

它负责的是：

- 修正文档层模型
- 修正 owner 边界理解
- 修正那些会影响后续判断方式的高层抽象

### 3.6 `AGENTS.md` 里最终要出现什么

`AGENTS.md` 不需要写状态文件细节大全，
但要加几条全局规则：

- 当前任务如果进入真实 case，状态落在当前 case 下
- `compile` 是 `handoff` 的 owner，`board-exec` 是 `ledger` 的 owner
- 真实 case 从 `compile` 切到 `board-exec` 时，必须形成可读 handoff
- `board-exec` 在板级动作前后必须重新探测并回写 ledger
- 板级动作不能只靠旧日志或上下文脑补状态
- 当前活跃 owner 负责维护本层新增事实的一致性

---

## 4. 第一阶段施工顺序

按下面顺序做，不要反过来：

1. 先改 `AGENTS.md`
   把全局状态维护规则钉住。
2. 再改 `support/SKILL.md`
   让 agent 能稳定建立或复用 case，并知道状态文件在哪。
3. 再改 `compile/SKILL.md`
   把 handoff 生成规则和最小模板挂到编译阶段收尾。
4. 再改 `board-exec/SKILL.md`
   把“读 handoff -> fresh probe -> 动作 -> fresh probe -> 回写 ledger”挂进板级执行流程。
5. 最后选一个真实 case 验证闭环
   至少证明：
   - `compile` 能按规则生成 handoff 实例
   - `board-exec` 能按规则读取 handoff 并更新 ledger
   - 动板前后能稳定回写最小动态事实

---

## 5. 第一阶段不该做重的地方

如果后面出现下面这些倾向，说明又做重了：

- 想先发明一个统一状态机框架
- 想让所有任务都先经过一个 `project-state` 总入口
- 想在没有真实 case 前先把 schema 设计满
- 想在施工阶段先手工造很多 `handoff.yaml` / `ledger.yaml` 实例文件
- 想把 `support` 变成每一步都要记账的中央调度员
- 想把 `ledger` 做成覆盖所有 CPU / 所有启动链的大状态表

第一阶段的正确目标很简单：

- 让 `compile -> board-exec` 交接稳定
- 让板级动作前后的状态感知稳定
- 让 case 断点恢复不再只靠对话上下文

做到这三件事，这次 V2 就算落地了。
