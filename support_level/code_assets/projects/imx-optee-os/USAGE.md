# imx-optee-os

- 真实源码目录：`./imx-optee-os/`
- 最近观察分支（使用前重新核对）：`lf-6.12.49_2.2.0`
- 最近观察版本（使用前重新核对）：`lf-6.12.49-2.2.0`
- 主要链路：`OP-TEE` / `flash.bin` 上游输入

## 角色

`imx-optee-os` 用来生成 OP-TEE secure world 镜像。
在当前 `flash.bin` 链路里，它通常提供：

```text
tee-raw.bin
```

对外参与 `imx-mkimage` 打包时，RTE 链路通常要求把它转换或复制为：

```text
tee.bin
```

是否需要 OP-TEE、是否必须走 `tee-raw.bin -> tee.bin`，
先由：

- `../../../software_stacks/rte.md`
- `../../../compile_targets/flashbin/README.md`

决定。

本页只负责 OP-TEE 项目自己的源码核对、构建命令形态和产物交接。

## 使用前提

进入本页前，至少先确认：

- 目标 SoC / board
- 软件栈和版本家族
- `PLATFORM` / `PLATFORM_FLAVOR`
- A-core 工具链
- 是否需要调试配置
- 最终是否作为 `flash.bin` 输入交给 `imx-mkimage`

如果任务属于 `RTE`，先读 `../../../software_stacks/rte.md`。
如果目标是完整 `flash.bin`，先从 `../../../compile_targets/flashbin/README.md`
确认完整输入集合。

## 共享源码规则

1. 先用 `git status --short --branch` 和 `git describe --tags --always --dirty` 核对当前 ref
2. 只读检查可直接在共享源码目录做
3. 要改、要编、要生成输出，复制到 `../../../work/<case>/` 再做
4. 不要在共享源码目录里长期留下构建输出

## 平台线索

本地源码的 i.MX 平台目录是：

```text
core/arch/arm/plat-imx/
```

当前源码里可见的 i.MX9 flavor 包括：

```text
mx95evk
mx943evk
```

这些来自 `core/arch/arm/plat-imx/conf.mk`。
选择 flavor 时必须按当前 SoC、板型和软件栈核对，
不要只按名字猜。

## 构建命令形态

命令形态通常是：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-optee-os
make PLATFORM=imx PLATFORM_FLAVOR=<flavor> \
  CROSS_COMPILE=<aarch32-prefix> \
  CROSS_COMPILE64=<aarch64-prefix>
```

例如 i.MX95 flavor：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-optee-os
make PLATFORM=imx PLATFORM_FLAVOR=mx95evk \
  CROSS_COMPILE=<aarch32-prefix> \
  CROSS_COMPILE64=<aarch64-prefix>
```

例如 i.MX943 flavor：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-optee-os
make PLATFORM=imx PLATFORM_FLAVOR=mx943evk \
  CROSS_COMPILE=<aarch32-prefix> \
  CROSS_COMPILE64=<aarch64-prefix>
```

这些是命令形态，不是固定 case 配方。
具体工具链、debug 选项、输出目录和额外配置要按当前 case 确认。

## 产物交接

核心产物是：

```text
tee-raw.bin
```

如果当前 `flash.bin` 链路要求 `tee.bin`，
需要在当前 case 里保留 `tee-raw.bin -> tee.bin` 的来源关系，
再把 `tee.bin` 交给当前 case 的 `imx-mkimage` 工作目录。

不要只检查 `tee.bin` 是否存在；
还要确认它确实来自本次选定源码、版本、配置和 `tee-raw.bin`。

## 不该在这里判断的事

- 不在这里决定 generic Linux 是否需要 OP-TEE
- 不在这里决定 RTE 是否必须带 OP-TEE
- 不在这里决定 `ATF` 是否要 `SPD=opteed`
- 不在这里决定完整 `flash.bin` 输入集合
- 不在这里解释 `uuu`、烧写或运行态验证

这些分别属于 `software_stacks/`、`compile_targets/flashbin/`、
`imx-atf/USAGE.md`、`tools/uuu/` 和 `board-exec`。
