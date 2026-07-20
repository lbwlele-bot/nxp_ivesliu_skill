# NXP_v2 施工手册

## 1. 这份手册解决什么问题

`ARCHITECTURE.md` 说明的是当前系统“为什么这样分层、现在如何工作”。

这份手册解决的是另一类问题：

- 如果别人手里只有 GitHub 仓库
- 没有现成镜像、源码树、工具链、板级经验和 case 沉淀
- 没有任何历史系统可直接继承

那他应该怎样从零规划、搭建、使用并逐步长出一套类似系统。

所以这不是当前仓库的目录说明书，
而是一份“从无到有施工”的实施方案。

---

## 2. 先明确：你要搭的不是“资料堆”，而是“系统”

从零搭建时，最容易犯的错不是少几个 README，
而是一开始就把：

- 下载的镜像
- clone 的源码
- 工具链
- case 临时目录
- 板级经验
- 执行规则

全混在一起。

这套系统之所以能工作，不是因为它“东西多”，
而是因为它把几类东西拆开了：

1. 控制面
   规定入口规则、skill 分工和系统架构
2. 支撑资源面
   放镜像、资料、代码资产、工具、SDK、firmware、case
3. 当前任务执行面
   每个 case 的过程、日志、产物、交接材料
4. 系统生长面
   待归纳的高价值信息

如果搭建者一开始就把这个边界想清楚，
后面系统会越长越稳。
如果一开始没拆开，
后面只会不断靠记忆和人工习惯勉强维持。

---

## 3. 施工总原则

### 3.1 先搭骨架，再填资产

不要先下载一堆源码、镜像、toolchain，再回头想怎么组织。
先把目录和 owner 设计出来，再按需要往里填。

### 3.2 先搭“入口”，不要先写“命令大全”

从零开始时，最值钱的是：

- 这类问题先去哪里
- 哪层负责判断 owner
- 哪层负责找资源
- 哪层负责具体执行

不是一上来就写满构建命令和烧写命令。

### 3.3 先支持一个真实任务闭环

不要试图第一天就把所有芯片、所有板、所有软件栈都抽象好。
先支持一个真实任务从：

- 需求确认
- 资源定位
- 编译对象确认
- 板级执行
- 日志反馈
- case 沉淀

完整闭环。

闭环跑通以后，再从这个 case 长出系统。

### 3.4 先沉淀结构，再沉淀细节

一开始最值得沉淀的是：

- owner 边界
- 目录分层
- 共享基线与 case 的边界
- 板级状态推进原则
- 高价值信息如何进入系统

这些比“某条命令怎么敲”更重要。

### 3.5 Git 只保存系统知识，不保存重资产本体

如果一个新系统从第一天起就把下载资产、源码树本体、toolchain、SDK 解压内容都进 Git，
后面几乎必然失控。

从零搭建时就要决定：

- Git 保存控制面和知识入口
- 重资产只保留本地

---

## 4. 施工目标图

从零施工的最终目标，不是复制当前目录名字，
而是长出下面这套能力：

### 4.1 用户能做到

- 拿到一个问题后，知道先看哪里
- 不靠记忆就能找到本地资源
- 知道当前问题属于理解、资源定位、编译还是板级执行
- 能把过程沉淀到 case
- 能把高价值信息留给后续系统生长

### 4.2 系统能做到

- 控制面轻量、可进 Git
- 资源面稳定、有 owner
- 共享基线和 case 不混
- 代码资产、编译对象、板级知识彼此分层
- 新增一块板或一条对象线时，不必重做一套架构

### 4.3 维护者能做到

- 看架构文档就知道系统怎么规划
- 看 README 就知道怎么使用
- 看 `support_level` 就知道资源怎么分布
- 看 case 就能恢复过程
- 看待归纳区就能知道系统下一步该怎么长

---

## 5. 从零施工的推荐阶段

建议按下面顺序搭，不要跳步。

### 阶段 0：确定系统边界

先回答这些问题：

- 这套系统主要服务什么类型的问题
- 它服务的是单个项目，还是长期板级开发工作
- 它运行在本机，还是多人共享服务器
- Git 仓库里要不要放下载资产
- case 过程是否要长期保留
- 后续是否要从执行过程抽象出长期规则

如果这些问题没想清楚，目录结构再漂亮也会返工。

对类似 `NXP_v2` 的系统，建议默认答案是：

- 服务长期板级开发工作，不是单次项目
- 运行在本机工作区
- Git 只放轻量控制面
- case 过程要长期保留
- 执行中暴露出的高价值信息要进入后续系统生长

### 阶段 1：先建最小目录骨架

先建：

```text
repo-root/
  README.md
  .gitignore
  workspace/
    AGENTS.md
    ARCHITECTURE.md
    CONSTRUCTION.md
    .agents/skills/
  support_level/
    README.md
    code_assets/
    compile_targets/
    board_knowledge/
    work/
    to_absorb/
```

一开始不要急着建太多细目录。
先保证“骨架对、owner 对、阅读路径对”。

### 阶段 2：建立四个主 owner

建议先固定四个主 skill：

- `understanding`
- `support`
- `compile`
- `board-exec`

理由不是“这四个名字好听”，
而是它们分别对应了最稳定的四类 unresolved step：

- 问题本质还没分清
- 资源在哪里还没分清
- 编译对象还没分清
- 板状态还没分清

如果从零开始的人想自己改名，也可以，
但 owner 角色最好不要缺。

### 阶段 3：建立支撑资源层

在 `support_level/` 下，不要按“来源”乱堆，
而要按“角色”分：

- 镜像与现成烧写输入
- 硬件资料
- 代码资产
- 编译对象入口
- 工具链
- 固定 firmware
- 主机工具
- 板级知识
- case
- 待归纳高价值信息

也就是说，先问“这东西在系统里承担什么角色”，
再决定它放哪个目录。

### 阶段 4：确定 Git 边界

这是最关键的一步之一。

建议在最早期就把 `.gitignore` 规则定下来：

Git 跟踪：

- 入口规则
- 架构文档
- skill
- README
- `USAGE.md`
- 板级知识文档

Git 默认不跟踪：

- 下载来的镜像
- SDK 压缩包内容
- toolchain 实体
- 源码树本体
- firmware blob
- case 运行产物

从零开始的人如果不先定这个边界，
后面通常会走到两种坏结果之一：

- 仓库里全是大文件和下载内容
- 仓库里什么都没有，只剩口头知识

### 阶段 5：先落一个真实对象线

不要一开始就同时搭：

- Linux
- `flash.bin`
- Zephyr
- M 核 SDK
- A 核 RTOS
- Android

先选一条最常见、最能代表真实工作方式的对象线。

建议优先级：

1. `flashbin`
2. `linux`
3. `board bring-up`
4. `m_freertos_sdk`
5. `zephyr`
6. `a55_rtos`

理由：

- `flashbin` 最容易暴露 owner 分层、输入边界和工具链 split
- `linux` 最容易暴露源码基线 vs case 派生
- 板级 bring-up 最容易暴露动态事实、允许动作和强信号优先原则

### 阶段 6：先支持一个真实 case 闭环

在 `support_level/work/` 下落一个真实 case。

case 推荐最小结构：

- `README.md`
- `records/`
- `logs/`
- `artifacts/`
- `state/`

其中 `state/` 只在真实 case 需要跨阶段推进时启用，常见实例是：

- `handoff.yaml`
- `ledger.yaml`

不要等系统成熟后才开始记 case。
系统本来就是靠 case 长出来的。

### 阶段 7：建立系统生长机制

从零开始时，维护者通常会想：

- 这个经验是不是要直接写进 skill
- 这个坑是不是要直接改到 README

正确做法不是立刻改正式系统，
而是先建一个待归纳区：

- `support_level/to_absorb/`

把新发现先放进去，保留：

- 来源 case
- 证据或原始线索
- 可复用结论
- 未来建议吸收到哪一层

这一步会决定系统后面是不是能长期演化。

---

## 6. 推荐目录蓝图

下面不是强制名字，而是推荐形态。

### 6.1 Git 控制面

```text
workspace/
  AGENTS.md
  ARCHITECTURE.md
  CONSTRUCTION.md
  .agents/skills/
    understanding/SKILL.md
    support/SKILL.md
    compile/SKILL.md
    board-exec/SKILL.md
```

### 6.2 资源面

```text
support_level/
  README.md
  Image/
  SoC_material/
  board_knowledge/
  code_assets/
    README.md
    projects/
    workspaces/
  compile_targets/
  software_stacks/
  release_packages/
  firmware/
  linux_document/
  toolchain/
  tools/
  work/
  to_absorb/
```

### 6.3 code_assets 子结构

```text
code_assets/
  projects/
    <project>/
      USAGE.md
      <real-source-tree or manifest>
  workspaces/
    <workspace>/
      README.md
      <workspace payload>
```

### 6.4 compile_targets 子结构

```text
compile_targets/
  flashbin/README.md
  linux/README.md
  m_freertos_sdk/README.md
  zephyr/README.md
  a55_rtos/README.md
```

### 6.5 software_stacks 子结构

```text
software_stacks/
  README.md
  rte.md
```

`software_stacks/` 是跨项目软件线入口。
遇到 `RTE`、`Real-Time Edge`、`RTE 3.3`、`RTE 3.4`
这类会同时改变 ATF、OP-TEE、SMFW、U-Boot、Linux 和
`flash.bin` 输入集合的需求，先进入这里，
再下沉到 `compile_targets/` 或具体源码项目。

### 6.6 release_packages 子结构

```text
release_packages/
  README.md
  m_freertos_sdk/
    README.md
    <SDK release archives>
  scfw/
    README.md
    <SCFW release packages>
```

### 6.7 case 子结构

```text
work/
  <date-chip-issue>/
    README.md
    records/
    logs/
    artifacts/
    state/
      handoff.yaml
      ledger.yaml
```

### 6.6 待归纳区子结构

这一层可以先很轻：

```text
to_absorb/
  README.md
  <date-topic>.md
```

不需要一开始就设计成复杂数据库。
每条记录至少写清来源 case、证据或原始线索、可复用结论、建议吸收层。

---

## 7. 施工时每一层该写什么

### 7.1 `AGENTS.md` 该写什么

应该写：

- 系统服务什么工作
- 主 skill 是谁
- case 放哪里
- 高价值信息放哪里
- 共享基线与 case 的边界
- Git 边界

不应该写：

- 具体命令大全
- 各个项目的构建 recipe
- 某块板的特殊细节

### 7.2 `ARCHITECTURE.md` 该写什么

应该写：

- 系统定位
- 设计思路
- 分层与 owner
- 资源模型
- code/assets/compile/case 的边界
- Git 边界

不应该写：

- 某次迁移台账
- 已经过时的并行重建计划
- 具体 case 过程

### 7.3 `README.md` 该写什么

应该写：

- 这个仓库是什么
- 先看哪里
- 顶层结构是什么
- `workspace/` 和 `support_level/` 分别负责什么
- 怎么开始用

不应该写：

- 太多内部迁移史
- 过度抽象的哲学
- 大段与实际目录脱节的口号

### 7.4 `support_level/README.md` 该写什么

应该写：

- 当前有哪些一级目录
- 它们各自负责什么
- 阅读顺序和下沉方向

不应该写：

- 具体编译命令
- 具体板级操作命令

### 7.5 `USAGE.md` 该写什么

应该写：

- 这个项目真实承担哪条链路
- 当前参考 ref / version
- 什么时候该看它
- 什么时候不该从它开始
- case 里需要改或编时该怎么派生

不应该写：

- 与它无关的全系统规则
- 大量其它模块的 owner

---

## 8. 没有历史资产时怎么起步

这是最关键的现实问题。

如果没有 `v1/NXP`，没有预下载资产，没有旧经验，
不要试图一次性复制当前 `NXP_v2` 的资产丰富度。

正确起步方式是：

### 8.1 先搭“空系统”

先只有：

- 目录
- README
- skill
- Git 边界

这时系统还没有丰富资产，但已经有结构。

### 8.2 再按真实任务引入第一批资产

例如第一次做 `i.MX95 flashbin`，
就只引入这次真的需要的：

- 一个源码项目
- 一个 workspace
- 一套 toolchain
- 一份 firmware
- 一个 case

不要“为了完整”把全家桶都拉进来。

### 8.3 每引入一类资产，就补对应入口文档

例如：

- 新增一个工具链
  补 `toolchain/README.md`
- 新增一个源码项目
  补 `code_assets/projects/<project>/USAGE.md`
- 新增一个板级默认事实
  补 `board_knowledge/<board>/README.md`

### 8.4 第一个真实闭环跑通后，再推广同类对象

例如：

- 先把 `flashbin` 线跑通
- 再抽它的共性，长成 `compile_targets/flashbin/`

而不是先凭空写一个“通用 flashbin 框架”。

---

## 9. 推荐施工顺序

如果今天要让别人照着 GitHub 从零搭，
推荐严格按下面顺序：

1. 建 Git 仓库
2. 建 `workspace/` 和 `support_level/` 两大面
3. 写 `AGENTS.md`
4. 写 `ARCHITECTURE.md`
5. 写这份 `CONSTRUCTION.md`
6. 定 `.gitignore`
7. 建四个主 skill 骨架
8. 建 `support_level/README.md`
9. 建 `code_assets/`、`compile_targets/`、`board_knowledge/`、`work/`、`to_absorb/`
10. 选一条真实对象线做第一次落地
11. 选一个真实 case 跑完整闭环
12. 从 case 抽第一轮高价值信息
13. 再扩第二条对象线或第二块板

这套顺序的核心思想是：

- 先有控制面
- 再有支撑面
- 再有真实 case
- 最后才有系统性抽象

---

## 10. 每一阶段的验收标准

### 阶段 A：骨架建成

验收标准：

- 新人能看 `README` 知道仓库大概干什么
- 看 `AGENTS` 知道先读哪里
- 看 `ARCHITECTURE` 知道系统怎么分层
- 看 `support_level/README` 知道资源面怎么分

### 阶段 B：第一条对象线建成

验收标准：

- 能回答“我要编什么”
- 能回答“从哪里开始编”
- 能回答“哪些目录只是输入”
- 能把构建动作放进 case，而不是污染共享基线

### 阶段 C：第一块板建成

验收标准：

- 能回答当前默认串口、默认下载态、默认强信号顺序
- 能区分 transport success 和 runtime success
- 能按板级状态推进，不按命令冲动推进

### 阶段 D：第一轮系统生长建成

验收标准：

- 执行中能把高价值信息留到 `to_absorb`
- 后续能从 `to_absorb` 回看来源 case、证据和可复用结论
- 正式 skill/README 的改动有明确来源

---

## 11. 最容易失败的地方

### 11.1 把资源目录当执行入口

症状：

- 看见源码就开始编
- 看见 workspace 就从里面找命令
- 看见镜像就直接烧

修正：

- 先经 `support`
- 编译先经 `compile`
- 板子先经 `board-exec`

### 11.2 把共享基线当 case 工作区

症状：

- 在共享源码里直接打 patch
- 在共享 workspace 里直接构建
- 把临时脚本和日志直接留在共享目录

修正：

- 共享基线只读/可逆操作
- 真正 case 行为放 `work/<case>/`

### 11.3 太早追求“大而全”

症状：

- 一开始就想覆盖所有芯片
- 所有对象线都同时建
- 文档先写成大全

修正：

- 先做一条对象线
- 先做一个真实 case
- 先验证闭环，再扩规模

### 11.4 把旧经验直接当正式系统

症状：

- 某次成功命令直接写进总入口
- 单个 case 的偶然路径变成全局默认

修正：

- 先放 `to_absorb`
- 等跨 case 证明后再吸收

### 11.5 把 Git 当备份盘

症状：

- 仓库越来越大
- 二进制和下载资产满天飞
- 结构文档反而看不出来

修正：

- Git 只保留控制面和知识入口
- 重资产只留本地

---

## 12. 对照当前 NXP_v2，施工者应学到什么

如果别人只看你现在的架构手册和 GitHub 仓库，
最该学到的不是某个目录名字，而是这几个核心思想：

1. 系统要先拆 owner，再谈命令
2. 控制面和重资源面必须分开
3. 共享基线和 case 工作区必须分开
4. case 不只是临时目录，而是系统未来的证据源
5. 高价值信息要先进入待归纳区，再进入正式系统
6. Git 保存的是“系统如何工作”，不是“资产本体”
7. 真正稳固的系统，是从真实 case 闭环一点点长出来的

如果施工者把这七点学到了，
即使目录名和当前 `NXP_v2` 不完全一样，
他也能搭出一套同样能长期工作的系统。
