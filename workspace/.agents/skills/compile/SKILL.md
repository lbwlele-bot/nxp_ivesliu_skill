---
name: compile
description: 编译阶段框架（在本机 Ubuntu 上做）。当任务处于“准备产物/镜像”阶段，需要理清运行链路、确定最小要编译或复用哪些模块，并在本机实际编译时，加载本技能。典型触发：用户说“编译”“build”“构建”“出个镜像/固件”“做个 bootloader/uboot/kernel”“把某模块编出来”“bitbake/make/cmake ...”“yocto”“交叉编译”“产物从哪来”“固件怎么出”。注意：这是编译阶段专用，跟板子物理操作（烧写/串口）无关，那部分在 board-exec。
---

# 编译阶段（本机 Ubuntu）

编译在当前 Ubuntu 主机上做。
本技能先给框架，具体某模块怎么编，后续再按模块逐步补。

---

## 先理运行链路

为达成客户目标，先回答：

1. 芯片里哪些 CPU / 固件阶段会参与运行
2. 这些阶段的先后和依赖关系是什么
3. 为让这条链路成立，最小需要准备哪些模块或镜像
4. 哪些能直接复用已有产物，哪些必须重新编

不要一上来就编全部；先框定最小集合。

---

## 源码与工具链在哪

代码相关支撑都在本机 `support-level`：

- `../support_level/source_code/`
- `../support_level/m_freertos_sdk/`
- `../support_level/toolchain/`
- `../support_level/firmware/`
- `../support_level/linux_document/`

对 toolchain / 固定二进制输入，不要只列目录。
优先再读：

- `../support_level/toolchain/README.md`
- `../support_level/firmware/README.md`
- `../support_level/m_freertos_sdk/README.md`

当前默认先用新的 `support_level/`。
只有在缺项追溯或核对来源时，才回看旧共享根。
无论在哪个根下用，都先实地看目录，确认版本和实际内容。

对 `m_freertos_sdk/`，先加一条特殊规则：

- 这里放的是 `MCUX SDK / FreeRTOS SDK` 发布压缩包资产
- 不是普通 clone 下来的源码树
- 如果本地没有目标版本，不要自己去网上下
- 先找用户要，或者让用户提供下载好的 SDK 发布包
- 解压、修改、编译，应在 `../support_level/work/<case>/` 里做

其中 `source_code/` 现在采用模块化结构：

```text
source_code/
  modules/
    <module>/
      USAGE.md
      <real-source-tree>/
  _to_absorb/
```

读取顺序：

1. 先判断当前任务实际落在哪些源码模块
2. 优先进入 `../support_level/source_code/modules/<module>/`
3. 先读该模块的 `USAGE.md`
4. 再进入旁边真实源码目录看实现、分支、构建方式

例如，如果任务落到 `i.MX943 flashbin` 这类 boot-firmware 链，
优先读取这些模块的 `USAGE.md`：

- `imx-mkimage`
- `imx-atf`
- `uboot-imx`
- `imx-oei`
- `imx-sm`
- `imx-optee-os`

再根据当前栈是 generic Linux 还是 `RTE`，决定是否还要看：

- `real-time-edge-uboot`

如果任务落到 `i.MX95 RTE 3.3 flash.bin`，优先读取：

- `imx-mkimage`
- `real-time-edge-uboot`
- `imx-atf`
- `imx-optee-os`
- `imx-oei`
- `imx-sm`

然后回头确认：

- `../support_level/toolchain/README.md`
- `../support_level/firmware/README.md`

并且先明确这几个高风险字段：

- `REV`
- `flash_a55` 还是 `flash_all`
- A-core / M-core toolchain owner 是否分清
- `tee.bin` 是否来自 `tee-raw.bin`
- `SMFW` config 是否明确是 `configs/other/mx95rte.cfg`
- `OEI` 是否真的是 `MIMX95(B0)`
- 当前最终 `flash.bin` 选的是不是脚本声明的 final 输出

如果某资产还在 `source_code/_to_absorb/`，说明它还没被吸收到长期模块结构里。
这时不要把它当成稳定长期入口，而要先说明它仍处于待拆状态。

对这条 lane，再补三条守门规则：

- 不要静默把 `flash_all` 改成 `flash_a55`
- 不要把 `OEI` / `SMFW` 吃成 A-core toolchain
- 不要只看到 `tee.bin` 存在，就当 secure-world 链已经正确闭环

## 当前已吸收的 compile-side lanes

### 1. `i.MX943` Linux kernel-side lane

这一层当前已经吸收到新骨架里的稳定边界是：

- generic Linux 和 `RTE` 分支在 lane 内区分
- `RTE` 必须显式带 version
- owner 负责的产物是：
  `Image`
  `dtb`
  `.ko`
- owner 不负责 deploy transport 或 runtime proof

### 2. `i.MX943` `M-core RTOS` lane

当前第一轮已吸收的稳定边界：

- `M7_0`
- `M7_1`
- `M33S`

是统一 owner。

- `RTE 3.4`
  validated
- `RTE 3.3`
  unsupported / unvalidated

对这条 lane，owner 负责把 payload contract 说清：

- `m70_image.bin`
- `m71_image.bin`
- `m33s_image.bin`

然后再交给 `flash_all` packaging 语义。

### 3. `i.MX943` `A55 RTOS` lane

当前第一轮已吸收的稳定边界：

- `Zephyr on A55`
- released-core `RTE` A55 RTOS

必须先分 stack branch，
再分 `compile` / `run`。

如果只是 bootstrap / source readiness，
会落到 host bootstrap helper；
如果已经是 board-specific A55 RTOS lane，
就按 board owner 往下走。

### 4. `Real-Time Edge Linux` source/bootstrap lane

对 `real-time-edge-linux`：

- reusable source baseline 和 case-local mutable copy 必须分开
- tag / toolchain family 要显式映射
- shared baseline 不在只读根里直接 build

### 5. heterogeneous-multicore / released-core bootstrap lane

对 released-core `A55 RTOS`：

- west workspace bootstrap
- toolchain bootstrap
- case-local copy before build

已经先吸收成 compile-side 认知，
不再把它混成 board-runtime 或 deploy lane。

### 6. Zephyr host bootstrap lane

Zephyr 这条 lane 当前第一轮已吸收的是 host bootstrap owner，
不是 board-runtime owner。

核心边界：

- fresh host environment
- shared latest workspace
- case-local build workspace
- validated SDK path

它证明的是：

- host 可以开始 Zephyr build

不是：

- 板子 runtime 已经成立

---

## 编译怎么做

- 直接在本机源码目录或当前 `work/<case>/` 下执行 `make`、`cmake`、`bitbake` 等命令
- 只读源码、确认版本、grep，可以直接在共享源码基线里做
- 要改动、构建、生成输出，就复制到当前 `../support_level/work/<case>/` 再动，别污染共享基线
- 对模块化源码，默认先消费 `USAGE.md` 里的最小操作说明，再决定是否需要深读源码
- 对 output-affecting lane，优先把 build identity 写清再跑命令：
  `REV`
  `LPDDR_TYPE`
  package target
  toolchain owner

边界：

- 本技能不负责烧写和上板验证，那是 `board-exec` 的事
- 如果当前缺的不是编译，而是资源位置或固定输入来源，先回 `support-level`

---

## 编译阶段产出

- 目标运行链路
- 最小要编译/复用的模块清单
- 每个模块的来源、状态
- 本次实际读取了哪些模块的 `USAGE.md`
- 产物放在哪个 `work/<case>/` 目录
- 哪些步骤超出当前能力、需要用户介入

---

## 待补全

- 各模块如 SMFW、U-Boot、kernel、M 核 RTOS 的具体编译方法
- 哪些模块适合保持共享只读基线，哪些模块应该先复制到 case 再编
