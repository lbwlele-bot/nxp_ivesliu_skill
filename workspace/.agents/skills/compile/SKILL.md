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

如果当前软件栈是 `RTE 3.3`、`RTE 3.4`、`Real-Time Edge`
这类跨项目软件线，先进入
`support_level/software_stacks/rte.md`。
不要直接跳到 `imx-atf`、`imx-sm`、`U-Boot` 或 `linux`
单个项目文档里推断整条 RTE 链路。

## 统一编译执行入口

源码阅读、依赖分析、编译对象判断和命令规划不需要调用工具。
只有准备进入真实编译或软件状态评估时，才进入：

- `../support_level/tools/compile-tool/USAGE.md`
- `../support_level/tools/compile-tool/compile-tool`

### flashbin

项目自治模型当前在 OEI、ATF、U-Boot、OP-TEE、SMFW 和 imx-mkimage
使用单清单入口：

```text
records/compile/imx-oei/compile.yaml
records/compile/imx-atf/compile.yaml
records/compile/uboot-imx/compile.yaml
records/compile/imx-optee-os/compile.yaml
records/compile/imx-sm/compile.yaml
records/compile/imx-mkimage/compile.yaml
records/compile/m_freertos_sdk/compile.yaml
```

从项目 `COMPILE_CHECKLIST.yaml` 复制并填写，然后只执行
`prepare <compile.yaml> -> run <compile.yaml>`。profile、manifest、assessment 和 request
是工具内部实现，不由 AI 维护。producer 成功后，consumer 清单通过
同 case `checklist + artifact` 引用其具名产物。工具校验 producer 成功
状态、hash、type 和身份参数。imx-mkimage 的输入由当前 recipe contract
选择，不把上游项目的编译规则重新塞回 mkimage。

该模型当前没有自动跨 manifest 编排，必须显式先 producer、后 consumer。
AHAB/DDR 固定资产已在当前 i.MX94/i.MX95 覆盖组合中绑定
role、落位和 SHA-256。M payload 已通过 M SDK 公共清单成为独立 producer，
含 M payload 的 mkimage recipe 只能消费其 `nxp.mcore.bin`；SCFW
release-package producer 尚未完成迁移，因此旧 flashbin 深度模式继续兼容；
不能混称为已经完成全量迁移。

flashbin 首先在当前 case 准备：

- `records/compile-manifest.yaml`
- `records/compile-request.yaml`

manifest 必须按 `compile-tool/SOFTWARE_STATE_SCHEMA.md`
覆盖 dependency profile 中的全部候选组件；
未使用组件填写 `not_applicable + reason`。

流程固定为：

1. 执行 `compile-tool requirements <manifest>`，确认当前 component
   触发的受约束参数清单
2. 执行 `compile-tool assess <manifest>`
3. 如果是 `ACQUIRE_REQUIRED`，完整展示源码准备命令，
   再以同一 hash 执行 `compile-tool acquire`
4. 重新 `assess`，读取 `MATCHED / CHANGES_OBSERVED` 状态摘要
5. 由 LLM 根据任务目标和工程判断决定是否重编，并在 schema v2 request
   的 `decision.scope/reason` 中声明直接变更组件和理由
6. 请求按 `compile-tool/REQUEST_SCHEMA.md` 绑定 manifest 和 assessment；
   unit 只能位于 scope 或其显式下游
7. 执行 `compile-tool prepare <request>`
8. 在 commentary 中向用户完整展示 `prepare` 输出的受约束参数、
   assessment、LLM 决策范围、工作目录、环境变量和原始命令
9. 无需逐次等待用户确认，执行 `compile-tool run <request>`

`state/software-state.yaml` 只能由工具生成。
不要手工填写 hash、把失败产物标成成功，或绕过 decision scope
增加无关平级组件。

managed Git 的 case source 只承载源码身份。普通 out-of-tree 构建的 cwd
必须位于源码树外；命中 `isolated_git` policy 的 in-tree component 必须使用
compile-tool 显示的 `build/.compile-tool/<target>/<component>/source/`。
不要通过 `.gitignore` 或 manifest 生成路径白名单隐藏构建生成物。

只要源码、配置、工具链、产物、依赖图或受约束参数发生变化，
旧 assessment hash 就失效；必须重新 assessment 和 prepare。

不要全局要求 SoC、silicon revision、封装、板型、DDR 和软件版本。
参数是否允许 assumption/default，或者必须询问用户，
以 compile target、源码项目或 workspace 旁边的 `COMPILE_POLICY.yaml`
为机器权威。

当前 OEI 和 imx-mkimage/flashbin 的 `silicon_revision`
是 `must_ask_user`：不知道就停下来问用户；
manifest 中必须记录 `source: user`，对应 make 命令必须显式包含同值
`REV=<value>`，不能依赖项目默认值。

SMFW rebuild 还必须声明 `smfw_config`，并按 policy 执行：
删除 `configs/<smfw_config>/` 生成目录、`make really-clean`、
`make config=<smfw_config> cfg`、`make config=<smfw_config> all`。
不能删除 `.cfg` 源文件或整个 `configs/`。

### M SDK 公共清单与其他 compile target

M FreeRTOS 已使用独立公共清单：

- 模板：`../support_level/compile_targets/m_freertos_sdk/COMPILE_CHECKLIST.yaml`
- case：`records/compile/m_freertos_sdk/compile.yaml`
- 一张清单可含多个具名 job；每个 job 独立状态
- AI 只填 package/compiler/job/intent，不填 backend、命令、输出路径或内部请求
- source build 同源发布 ELF+BIN；prebuilt import 只校验、复制和发布

Linux、Zephyr、A55 RTOS 和后续普通 target
使用通用 schema v2 状态单元，在当前 case 准备：

- `records/compile/<target>/manifest.yaml`
- `records/compile/<target>/request.yaml`

调用流程仍是 `assess -> 必要时 acquire -> prepare -> run`。
manifest 只列本次实际需要的 component、明确来源、配置、工具、
watched inputs、产物和已知依赖。工具只传播 manifest 明确写出的
`depends_on`，不解析 Makefile、Kbuild 或 west manifest，也不补猜未知依赖。

普通通用状态单元只能使用 `rebuild`；公开清单生成的受控预编译单元可使用
`import`。文件级增量和 `west build` 是否使用
`-p always` 仍由项目手册和工程判断决定。普通组件使用 clean、mrproper、
really-clean 或递归强制删除时，必须在 request 中显式说明 destructive 理由。
新增普通 target 默认只增加 manifest，不为它新增 Python profile。

schema v1 只保留给尚未纳入软件状态维护的临时命令；
它只做请求形状和原始命令校验，不更新 `software-state.yaml`，
也不应用 component 参数规则。

在本工作区的规范流程中，
不直接执行裸 `make`、`cmake`、`ninja`、`bitbake`
或其它真实编译命令。
这些原始命令仍由当前 compile target、项目 `USAGE.md`
和工程判断决定，`compile-tool` 只负责显式展示、绑定和执行，
不生成 recipe，也不解析 Makefile。

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
- 跨项目软件栈身份，例如 `RTE`
  先进入 `support_level/software_stacks/<stack>.md`
- 编译对象一旦确定
  先进入 `support_level/compile_targets/<target>/README.md`
- 某个源码项目随后被纳入本次范围
  再进入 `support_level/code_assets/projects/<project>/USAGE.md`
- 某个工作区被纳入本次范围
  进入 `support_level/code_assets/workspaces/<workspace>/README.md`
- 具体板 revision、板级基线、板级风险
  进入 `support_level/board_knowledge/<board>/README.md`

如果目标目录旁边已经有 `RELATION.yaml` 或 `<id>.RELATION.yaml`，
先读它作为机器索引，再进入 README / USAGE：

- 用 `owner` 确认当前阶段是否仍归 `compile`
- 用 `relations` 快速列出候选下沉对象
- 用 `case_required_for` 判断是否必须进入 `work/<case>/`
- 用 `warnings` 避免把 recipe、软件线、源码项目混成一层

但具体构建命令、版本核对和输入输出契约仍以 README / USAGE 为准。

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

- 这次作为一个完整部署组合交付的产物是什么
- 每个产物从哪来、放在哪、大小和 hash 是什么
- 顶层写入产物的消费方式和目标路径
- M 核、SCFW、BL31 等组件是否已经嵌入某个顶层 boot image
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
- `artifacts`：路径、大小、hash
- `consumption`：顶层产物的写入方式/目标，以及组件的 `embedded_in` 关系
- `target_step`
- `preconditions`
- `verification_focus`

同一个 `handoff` 中列出的顶层写入产物构成一套部署组合。
不能把其中某个 `flash.bin`、Image、DTB 或 module
静默替换成其它实验版本。

默认不再单独创建重复的 `deployment.yaml`；
部署组合仍由现有 `state/handoff.yaml` 表达。

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
