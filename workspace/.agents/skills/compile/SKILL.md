---
name: compile
description: 编译阶段高层路由层（在本机 Ubuntu 上做）。当任务处于“准备产物/镜像”阶段，需要先理清运行链路、判断属于哪个编译对象、确定最小依赖集合，并把后续动作下沉到对应对象说明或项目手册时，加载本技能。典型触发：用户说“编译”“build”“构建”“出个镜像/固件”“做个 bootloader/uboot/kernel”“把某模块编出来”“bitbake/make/cmake ...”“yocto”“交叉编译”“产物从哪来”。注意：这是高层编译路由层，不是具体模块手册；板子物理操作（烧写/串口/启动/登录）在 `board-exec`。
---

# 编译阶段（高层路由层）

编译在当前 Ubuntu 主机上做。
本技能只负责先把编译任务收敛到正确编译对象和正确依赖集合，
不负责承载某一个项目自己的具体操作手册。

---

## 什么时候进入 compile

当任务已经明确落到“要准备产物”的阶段，再进入这里。

适用问题：

- 这次到底要准备哪类产物
- 这次到底属于哪个编译对象
- 这条运行链路最小需要哪些依赖
- 哪些共享基线或固定输入可以直接使用，哪些必须重编
- 这次应该进入哪个编译对象说明，以及后续哪些项目 `USAGE.md`

不适用问题：

- 资源放在哪
- 固定输入从哪来
- 工具链 / 固件 / SDK 目录怎么找
- 板子当前是什么状态、接下来能不能烧写/启动/登录

这些边界分别交给：

- `support`
- `board-exec`

---

## 先判断运行链路和编译对象

第一步不是跑命令，而是先理运行链路：

1. 哪些 CPU / 固件阶段会参与运行
2. 它们的先后关系和依赖关系是什么
3. 为让这条链路成立，最小需要准备哪些依赖
4. 哪些共享基线或固定输入可以直接使用，哪些必须重编

不要一上来就编整套；先收敛最小依赖集合。
也不要默认复用旧 `work/` 里的产物；
除非已经非常清楚那些产物的来源、版本、配置和生成过程都可控，
否则按需要重建，或回到共享基线重新出产物。

### 常见编译对象

- `flashbin`
- `linux`
- `m_freertos_sdk`
- `zephyr`
- `a55_rtos`

### 进入编译对象前必须钉死的守门项

- 当前软件栈 / 版本分支
- 打包目标
- 最终期望产物类别
- 工具链归属划分

这些字段属于跨项目构建身份。
如果这里没钉死，后面就不要让具体对象开始编。

### 先只保留到“编译对象 + 最小依赖集合”这一层

`compile` 先判断这次属于哪个编译对象，
以及通常会涉及哪些依赖，
不在这里直接展开具体构建配方。

例如：

- `flashbin`
  常见会涉及 `mkimage`、`ATF`、`U-Boot`、`OP-TEE`、`OEI`、`SMFW`、firmware、必要时 `M` 核 payload
- `linux`
  常见会涉及 Linux 源码项目、toolchain、必要时板级与打包边界
- `m_freertos_sdk`
  常见会涉及 SDK 发布包、`arm-none-eabi` 工具链、必要时再回看 `mcuxsdk` 源码资产
- `zephyr`
  常见会涉及 `zephyr-workspace` 工作区、`zephyr-sdk`、必要时回看板级边界
- `a55_rtos`
  常见会涉及 `heterogeneous-multicore` 主对象，以及同工作区里的 `zsdk` / `mcuxsdk` 联动输入

这里的目标只是决定：

- 这次属于哪个编译对象
- 最小依赖集合是什么
- 哪些只是依赖输入
- 哪些才是这次真正该进入的对象或项目

---

## 决定依赖集合后怎么下沉

一旦编译对象已经确定，`compile` 自己就不继续展开具体做法，
而是先把任务下沉到对应编译对象说明。

下沉规则：

- 资源位置、目录归属、固定输入位置
  先回 `support`
- 编译对象一旦确定
  先进入 `support_level/compile_targets/<target>/README.md`
- 某个源码项目随后被纳入本次范围
  再进入 `support_level/code_assets/projects/<project>/USAGE.md`
- 某个工作区被纳入本次范围
  进入 `support_level/code_assets/workspaces/<workspace>/README.md`
- 具体板 revision、板级基线、板级风险
  进入 `support_level/board_knowledge/<board>/README.md`

文档分工要明确：

- 每一层目录下的 `README.md` 是描述文档
  负责说明这一层里有什么、怎么分布、下一步该往哪一层走
- 每个源码项目或具体工具旁边的 `USAGE.md` 是操作手册
  负责这个项目或工具自己怎么用、怎么编、怎么检查
- 每个编译对象目录下的 `README.md` 负责说明：
  它依赖什么
  正常从哪里开始编
  哪些目录不能直接拿来编

也就是说，目录层看 `README.md`，项目层看 `USAGE.md`。

### 共享基线 vs case 构建

- 共享基线原则上保持可还原
- 源码浏览、版本核对，以及可逆的 checkout / tag / branch 切换，可以直接在共享基线里做
- 只要要改、要编、要生成输出，就进 `../support_level/work/<case>/`
- `../support_level/work/<case>/` 是当前 case 的构建和临时产物目录，不应默认拿旧 case 产物继续复用

特别注意：

- 不要因为某个 workspace 里带着 `zephyr/` 或 `mcuxsdk/`
  就默认从那里开始编
- 对 `a55_rtos`，`heterogeneous-multicore` 是主对象；
  同工作区里的 `zsdk/`、`mcuxsdk/` 只是联动输入
- 对 `zephyr`，不要默认从 `hmc-workspace/zsdk/` 开始

也就是说：

- `compile` 负责决定要不要动这个编译对象
- 对象一旦确定，先由该对象 `README.md` 接手
- 真正落到源码项目时，再由对应项目 `USAGE.md` 接手

不要把“只是为了方便”而把单项目操作手册留在上层。

### 与其他层的边界

- 当前缺的是资源位置、固定输入、共享资产路径
  回 `support`
- 当前缺的是烧写、启动、登录、运行态验证
  回 `board-exec`
- 当前缺的是板 revision、板级默认形态、板级风险
  进对应 `board_knowledge`

---

## compile 与 `handoff`

`compile` 不是状态管理器，
这里只补一个很小的跨阶段交接动作：

- 当这次编译已经明确要切到 `board-exec`
- 且已经形成可被板级执行阶段消费的产物集合

则 `compile` 负责在当前 case 下生成或更新 `handoff` 实例。

站在当前 `workspace/` 视角，
默认落点是：

- `../support_level/work/<case>/state/handoff.yaml`

### 什么时候需要 `handoff`

需要的场景是：

- 当前任务不止于“本地产物准备”
- 下一步已经明确要进入 `board-exec`
- 后续上板动作不能只靠对话上下文维持

不需要的场景是：

- 只是分析编译链路
- 只是确认依赖集合
- 只是本地编译但还没进入板级执行

### `compile` 对 `handoff` 的 owner 边界

`compile` 只负责写自己真正有 authority 的内容：

- 这次可交付的产物是什么
- 产物从哪来、放在哪
- 预期交给哪个执行阶段去消费
- 上板前提里，哪些是编译阶段已经明确知道的
- 上板后优先验证什么

`compile` 不负责写：

- 板当前实际运行到哪一步
- 板当前允许做什么动作
- 板已经成功进入下一阶段

### `compile` 持有的最小 `handoff` 模板

第一阶段不追求重 schema，
但最小模板至少要能表达：

- `producer`
- `artifacts`
- `target_step`
- `preconditions`
- `verification_focus`

---

## compile 自己最终产出什么

`compile` 最终只应该产出这些高层判断结果：

- 目标运行链路
- 当前所属编译对象
- 最小依赖清单
- 本次会进入哪个编译对象 `README.md`
- 本次后续会进入哪些项目 `USAGE.md`
- 哪些输入仍需用户或 `support` 提供
- 哪些步骤后续要切到 `board-exec`
- 如果已经明确要切到 `board-exec`，当前 `handoff` 应该怎样生成或更新

如果这些高层结论还没稳定，
说明还不该进入具体项目操作手册。
