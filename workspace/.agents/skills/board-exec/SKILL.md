---
name: board-exec
description: 板级执行阶段高层路由层（在本机 Ubuntu 上做）。当任务已经进入“把产物弄上板并验证”阶段，需要烧写镜像、操作板控或串口工具、抓串口日志、判断板子当前实际运行到哪一步时，加载本技能。典型触发：用户说“烧板子”“烧写/刷镜像”“刷机”“下载镜像到板子”“uuu”“bcu”“烧卡”“进下载模式”“复位板子/切启动模式”“读串口”“抓串口/看串口日志”“上板验证”“板子起不来/卡住/不启动”。注意：这是板级执行高层路由层，不是具体工具手册，也不是具体板型手册；编译/出产物那部分在 `compile`。
---

# 板级执行阶段（高层路由层）

板子物理连在本机 Ubuntu，
所以烧写、板控、串口、USB 枚举检查都在本机做。

本技能只负责把板级任务收敛到：

- 当前板状态
- 目标板状态
- 允许的下一步动作
- 该下沉到哪个工具手册
- 该下沉到哪个板级知识文档

它不负责承载某一个工具自己的操作手册，
也不负责承载某一块板自己的默认串口、默认下载态、特殊风险和特例动作。

---

## 进入后先做什么

第一步不是立刻发命令，
而是先把当前板状态和目标板状态说清。

至少先确认：

- 当前板型
- 芯片版本 / 板 revision / DDR
- 当前 boot mode
- 目标存储
- 当前是否上电
- 当前最强的状态信号是什么

这里的重点是：

- 不把命令当计划
- 不把旧观察当当前事实
- 不把某个局部成功误判成整板状态已经推进

如果当前任务属于真实 case，
还要先看当前 case 下是否已经存在：

- `README.md`
- `logs/`
- `state/handoff.yaml`
- `state/ledger.yaml`

也就是说，`board-exec` 进入后先读上下文，
不是先急着动板。

---

## board-exec 与 `handoff` / `ledger`

`board-exec` 是第一阶段状态维护的核心 hook 点。

它在这套机制里要做的不是维护一套大状态机，
而是按固定节奏做三件事：

1. 读取当前 case 的交接与历史上下文
2. 用 fresh probe 判断当前最强动态事实
3. 把这次为继续推进必须保留的最小事实回写到 `ledger`

### 1. 先读 `handoff`

如果当前 case 已经存在：

- `../support_level/work/<case>/state/handoff.yaml`

则先按它理解：

- 这次要消费什么产物
- 预期怎么消费
- 哪些前提必须先满足
- 上板后优先验证什么

`board-exec` 可以消费 `handoff`，
但不代替 `compile` 重写交接内容。

如果 `handoff` 描述了多个顶层写入产物，
它们是一套不可静默混用的部署组合。
执行前必须：

- 核对所有要写入产物的实际路径、大小和 hash
- 核对 Image、DTB、module 等各自的目标路径
- 区分真正单独写入的产物和已经 `embedded_in` boot image 的组件
- 任一文件缺失、hash 不符或组合身份不清时停止写入，回到 `compile`

M 核、SCFW、BL31 等组件如果已经嵌入 `flash.bin`，
只记录其构建来源和组件 hash，
不能误当成额外的独立板级写入动作。

### 2. `ledger` 只记最小动态事实

如果当前 case 已经进入真实板级执行，
`board-exec` 负责生成或更新：

- `../support_level/work/<case>/state/ledger.yaml`

这里记录的不是整板总状态机，
而是当前 case 为继续推进必须记住的最小动态事实。

第一阶段推荐最小模板只保留：

- `focus`
- `current_fact`
- `evidence`
- `next_action`
- `notes`
- `last_action` 可选

原始串口、命令输出、USB 枚举和工具返回，
仍然留在 `logs/`，
不要拿 `ledger` 代替原始证据。

### 3. 固定执行节奏

对任何会改变板状态的动作，
都按下面顺序：

1. 读当前 case 上下文
2. 读 `handoff`
3. fresh probe 当前最强状态信号
4. 更新一次 `ledger`
5. 执行动作
6. 动作后再次 fresh probe
7. 再更新 `ledger`
8. 保存原始输出到 `logs/`

这里最硬的规则是：

- old logs 不能直接覆盖当前事实
- 单次命令成功不等于状态迁移成功
- `uuu` / reset / 串口沉默，都不能单独拿来宣布下一阶段已经成立

---

## 当前要写死的板级硬规则

这里先不追求完整“状态机”。
当前上层只写死两类真正会决定动作的规则：

- `CPU0` / 板控阶段规则
- 异构核 owner 规则

### 0. `bcu` / `uuu` 权限规则

本机所有 `bcu` 和 `uuu` 调用都固定使用非交互 sudo：

```bash
sudo -n ../support_level/tools/bcu/bcu ...
sudo -n ../support_level/tools/uuu/1.5.243/uuu ...
```

这是执行层硬规则，适用于：

- help / version
- 只读 probe、`get_boot_mode`、`-lsusb`
- boot mode 切换和 reset
- 下载、烧写和 FAT 写入

不允许先运行普通用户命令再观察是否失败，也不允许在 `sudo -n` 失败后回退
到普通用户命令。`sudo -n` 失败时，当前结论是主机权限前提不成立，应保存错误
并停止该工具动作。

### 1. `CPU0` / 板控阶段规则

至少先分清当前更像下面哪一类：

- `serial download`
- `U-Boot fastboot / FB`
- `U-Boot shell`
- `Linux-up`
- `unknown`

这里不是为了画图，
而是为了限制“此刻到底允许做什么动作”。

硬规则：

1. 只有当前证据能证明板子还在 `serial download`，才允许 first-stage
   `sudo -n ../support_level/tools/uuu/1.5.243/uuu -b sd <flash.bin>`
2. 只有当前证据能证明已经进入 `FB`，才允许复用当前会话做 second-stage 写入
3. 只有当前证据能证明已经进入 `U-Boot`，才允许继续做 `env`、`dtb`、高层 `boot` 命令或由 `U-Boot` 接手的后续启动动作
4. 只有当前证据能证明已经 `Linux-up`，才允许继续谈 `rproc`、网络、应用层和 Linux 侧运行态验证
5. `uuu` 成功、reset 成功、串口安静，都不能单独拿来跳过阶段判断
6. 如果当前阶段证据不够，就先补探测，不硬推下一步

### 2. 异构核 owner 规则

多核异构问题里，
当前更重要的不是给每个核造很多状态名，
而是先写清：

- 哪些核是保留核，默认不能乱动
- 这次 case 真正要碰的是哪些核
- 当前目标 payload 预计由谁接手

这里的 `owner` 只先收最小集合：

- `flash.bin`
- `U-Boot`
- `Linux rproc`
- `Linux`
- `reserved`
- `unknown`

硬规则：

1. 不默认把所有异构核都当成“可自由使用”
2. 先确认板型文档里有没有固定保留核，再决定哪些核允许进入当前 case
3. 在 `CPU0` 启动阶段还没判断清楚前，不提前宣称某个异构核已经可以接手
4. 对当前 case 触碰的核，至少说清：
   目标核
   当前 payload
   预计 owner
   是否已经有运行态证据
5. 板型特有的保留核、默认 owner 和已验证启动路径，留在对应 `board_knowledge/<board>/README.md`

### 3. 卡住时先回到可控态

如果板子卡住、串口安静或当前阶段不清楚，
先做两件事：

- 回头找当前板型最强的状态信号
- 回头找当前板型已验证的恢复动作

是否默认使用 `bcu`，
不在上层统一写死。

- 支持且已验证 `bcu` 的板，`bcu` 可以是恢复到可控态的默认动作之一
- 不以 `bcu` 为默认路径的板，恢复动作要按该板自己的 `board_knowledge` 执行

### 4. Reset 规则不得跨板继承

reset 是板型和实物相关能力，不能因为某一块板验证成功或失败，
就把结论传播到其它 SoC / EVK。

拿到并连接一块具体实物板后：

1. 先识别准确 board profile
2. 读取该板 `board_knowledge/<board>/README.md` 和 `RELATION.yaml`
3. 向用户确认这块实物板是否允许 BCU / 自动 reset
4. 用户确认前，不主动执行自动 reset

当前 i.MX8DXL 不是绝对 manual-reset-only，而是按证据目标受限：

- 需要 M4 `if01` 早期日志时，BCU 会占用同一 interface，必须使用用户人工 reset
- 明确不验收 M4 日志、只抓 A-core 和 SCFW 时，当前实物已验证可使用 BCU reset

这个条件规则不能套到 i.MX93、i.MX943 或其它板；其它板继续按各自板级知识
和现场确认执行。

---

## 文档怎么下沉

`board-exec` 只保留独立于工具和具体板型的板级执行原则。

一旦问题已经落到某个工具或某块板的具体知识，
就不要继续留在上层。

如果目标板或目标工具旁边已有 `RELATION.yaml`，
先读它做快速索引，再读对应 README / USAGE：

- 用板型 `RELATION.yaml` 确认可用工具、case 边界和稳定 warning
- 用工具 `RELATION.yaml` 确认工具 owner、关联板型和会改变板状态的动作
- 具体串口 role 事实读 `tools/serial-console/profiles/<board>/serial.yaml`
- 具体命令和参数仍读工具 `USAGE.md`

`RELATION.yaml` 不替代 fresh probe。
任何会改变板状态的动作，仍按本页前后探测和记录规则执行。

### 工具问题怎么下沉

如果当前问题是在问：

- 某个工具怎么调用
- 参数怎么选
- 哪类文件该走哪种写法
- 某个工具自己的风险边界是什么

就进入：

- `support_level/tools/README.md`
- 对应工具目录里的 `USAGE.md`

也就是说：

- 目录层 `README.md`
  负责说明当前有哪些工具、工具放在哪里
- 工具旁边的 `USAGE.md`
  负责这个工具自己的操作手册

### 串口工具统一入口

本工作区串口执行统一走：

- `support_level/tools/serial-console/USAGE.md`

不要在 `board-exec` 里直接展开 `picocom`、`screen`、`minicom`、
`cat /dev/ttyUSB*` 或临场 Python 片段。

原因是串口动作不只是“打开一个口”：

- 要按板型 role 选择串口，不盲扫四个口
- 要能抓原始 log 到当前 case `logs/`
- 要能发送命令
- 要能等待 `U-Boot` 三秒倒计时并自动发回车
- 要把串口参数和主机侧准备动作收敛到一个工具入口

具体哪块板哪个 role 对应哪个串口，
不写在 `board-exec`，
进入对应：

- `support_level/tools/serial-console/profiles/<board>/README.md`
- `support_level/tools/serial-console/profiles/<board>/serial.yaml`

### 板型问题怎么下沉

如果当前问题是在问：

- 某块板默认串口是什么
- 默认下载态怎么识别
- 板 revision 有什么差异
- 某块板有哪些高风险已知事实
- 某个 reset / boot-mode / relay 特例是不是只属于某块板

就进入：

- `support_level/board_knowledge/<board>/README.md`

也就是说：

- `board_knowledge` 目录层
  负责说明当前有哪些板型知识
- 每块板自己的 `README.md`
  负责该板的 boot mode、reset、loader、已验证基线和非串口风险
- `tools/serial-console/profiles/<board>/`
  负责随工具发布的串口说明和机器可读 role 映射

---

## 上层只保留哪些板级执行原则

下面这些可以保留在 `board-exec`，
因为它们不依赖某一个工具，也不只属于某一块板。

### 1. 先分产物类别，再选板级动作

至少先分清：

- `raw_boot_image`
  例如 `flash.bin`
- `fat_runtime_file`
  例如 `Image`、`dtb`、`.ko`

不要在产物类别没分清时，
就先决定烧写动作。

### 2. 某个动作成功，不等于后续阶段已经成立

无论是烧写成功、reset 成功，还是某个下载动作成功，
都不能自动推出板子已经到了：

- `U-Boot`
- Linux
- 可登录状态

后面还要继续做独立的阶段验证。

### 3. 烧写成功和运行态证明不是一回事

把产物成功送到板上，
只说明板级动作本身成立。

它不自动证明：

- Linux 一定能起
- 登录一定可行
- 某个运行态 payload 一定已经接管

### 4. 板子至少要分阶段判断

板级执行不能只分“烧成功 / 没烧成功”。

至少还要继续判断板子究竟停在：

- 下载态
- `U-Boot`
- Linux 已启动但未确认可登录
- 已登录 shell

### 5. 串口安静时，先回头看强信号

如果板级动作之后串口安静，
不要先默认：

- 串口号错了
- 波特率错了
- 板子死了

先回头确认更强的状态信号，
例如 boot mode、USB 枚举、下载态身份，或者其他已验证板控信号。

### 6. 板级验证要分层交接

如果当前未解决的是：

- 板子还在下载态，还是已经进 `U-Boot`
- 还在 `U-Boot`，还是已经开始 Linux boot

那问题还属于启动阶段判断。

只有当 Linux login 真的是最后一个未解决步骤时，
才应把问题交给登录验证。

### 7. 网络和应用层必须在 Linux-up 之后

像下面这些问题，
都不应抢在启动和登录验证前面：

- 主机共享网络
- 板侧 IP / DNS
- Linux 上的应用层运行

前提必须是：

- 板子已经被证明 Linux-up
- 当前未解决步骤已经不是下载态 / `U-Boot` / 登录

---

## 板级执行的大致顺序

1. 先确认当前 case 上下文与目标状态
2. 如果存在 `handoff`，先读交接内容
3. fresh probe 当前最强状态信号
4. 根据问题性质，下沉到工具手册或板级知识
5. 执行板级动作
6. 动作后重新探测并更新 `ledger`
7. 继续判断是还停在板级执行层，还是应该交给登录验证、网络层或应用层

---

## board-exec 自己最终产出什么

`board-exec` 最终只应该产出这些高层结果：

- 当前板状态
- 目标板状态
- 当前最强状态信号
- 下一步允许的板级动作
- 当前 `CPU0` 所处阶段
- 当前 case 允许触碰的异构核和它们的 owner 约束
- 当前 case 的最小动态事实摘要（`ledger`）
- 本次要进入哪个工具 `USAGE.md`
- 本次要进入哪个板型 `README.md`
- 动作后应该回到哪一层继续判断
