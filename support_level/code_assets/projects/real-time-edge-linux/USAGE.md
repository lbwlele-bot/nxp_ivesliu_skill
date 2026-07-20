# real-time-edge-linux

- 真实源码目录：`./real-time-edge-linux/`
- 最近观察 ref：`detached HEAD` / `Real-Time-Edge-v3.3-202512`，使用前重新核对
- 主要链路：`rte`、`linux-bsp`

这是 Real-Time Edge Linux 内核源码线。

本页只负责这棵 Linux 源码自己的核对、局部修改、内核产物构建和交接。
当前任务是否应该选 RTE Linux，而不是通用 `linux-imx`，先由：

- `../../../compile_targets/linux/README.md`
- `../../../software_stacks/rte.md`

决定。

## 什么时候看这里

- 当前任务已经确认属于 `Real-Time Edge Linux`
- 需要查 RTE Linux 的 driver、Kconfig、defconfig 或 DTS
- 需要出 `Image`、`dtb`、modules 这类 Linux 侧产物
- 需要对比 RTE Linux 与通用 `linux-imx` 的源码差异

如果问题是 RTE 版本、boot image 输入集合、U-Boot 来源或 Yocto layer，
先回到 RTE 总规则或对应项目页，不要在这里反推整条 RTE 软件线。

## 本地线索

当前可见的 arm64 配置入口：

```text
arch/arm64/configs/imx_v8_defconfig
arch/arm64/configs/imx.config
```

最近核对到 `imx_v8_defconfig` 里存在 `CONFIG_PREEMPT_RT=y`。
这说明当前源码线带有 RT 内核配置线索，但实际配置仍以当前 case 的 defconfig /
fragment / Yocto 配置为准。

当前可见的 RTE 相关 DTS 命名线索包括：

```text
arch/arm64/boot/dts/freescale/imx943-evk-harpoon.dts
arch/arm64/boot/dts/freescale/imx943-evk-multicore-rtos.dts
arch/arm64/boot/dts/freescale/imx95-19x19-evk-harpoon.dts
arch/arm64/boot/dts/freescale/imx95-19x19-evk-multicore-rtos.dts
arch/arm64/boot/dts/freescale/imx95-19x19-evk-root.dts
arch/arm64/boot/dts/freescale/imx95-19x19-evk-inmate.dts
```

这些只是源码中存在的候选文件。
实际 `dtb` 必须按当前板型、封装、DDR、carrier、RTE 模式和 case 目标确认。

## 使用规则

1. 先用 `git status --short --branch` 和 `git describe --tags --always --dirty`
   核对当前 ref。
2. 只读查代码、配置、DTS 可以直接在共享源码目录做。
3. 要改内核、编译、生成 `Image` / `dtb` / modules，复制到
   `../../../work/<case>/` 再做。
4. 不要在共享源码目录里长期留下 `O=build`、modules staging 或 case patch。

## 构建形态

RTE Linux 仍然是 Linux 内核源码，直接构建形态和通用 `linux-imx` 类似：

```bash
export ARCH=arm64
export CROSS_COMPILE=/home/ives/桌面/NXP_v2/support_level/toolchain/arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-

make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE O=build imx_v8_defconfig
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE O=build -j$(nproc) Image dtbs modules
```

这些是命令形态，不是固定 case 配方。
实际 defconfig、fragment、dtb、toolchain 和 module 范围必须按当前 case 确认。

## 边界

- 通用 Linux 源码：`../linux-imx/USAGE.md`
- RTE 版本和跨项目约束：`../../../software_stacks/rte.md`
- RTE Yocto layer、bbappend、patch bucket：`../meta-real-time-edge/USAGE.md`
- `flash.bin` 打包：`../../../compile_targets/flashbin/README.md`
- 上板、烧写、串口验证：`board-exec`

一句话：这里回答“RTE Linux 内核源码怎么查、怎么出 Linux 侧产物”，
不回答“RTE 整套软件线怎么选、flash.bin 怎么组”。
