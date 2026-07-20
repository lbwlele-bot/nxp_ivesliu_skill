# uboot-imx

- 真实源码目录：`./uboot-imx/`
- 最近观察 ref：`lf_v2025.04` / `lf-6.18.2-1.0.0`，使用前重新核对
- 主要链路：通用 `U-Boot` / 启动固件输入

这是通用 NXP i.MX U-Boot 源码线。

本页只负责 `uboot-imx` 自己的源码核对、局部修改、构建和产物交接。
当前任务是否应该走通用 `uboot-imx`，还是 `real-time-edge-uboot`，先由：

- `../../../software_stacks/rte.md`
- `../../../compile_targets/flashbin/README.md`

决定。

## 什么时候看这里

- 当前任务已经确认使用通用 `uboot-imx`
- 需要查 U-Boot board config、defconfig、DTS、env 或 boot flow
- 需要重建 U-Boot 输入，再交给 `imx-mkimage` 打 `flash.bin`

## 本地线索

当前源码里可见 i.MX9 defconfig，例如：

```text
configs/imx93_14x14_evk_defconfig
configs/imx943_evk_defconfig
configs/imx943_orangebox_defconfig
configs/imx95_19x19_evk_defconfig
configs/imx95_15x15_evk_defconfig
```

这些只是候选配置。实际 defconfig 必须按 SoC、板型、封装、DDR、
启动介质和当前软件栈确认。

## 使用规则

1. 先用 `git status --short --branch` 和 `git describe --tags --always --dirty`
   核对当前 ref。
2. 只读查代码、配置、DTS 可以直接在共享源码目录做。
3. 要改代码、编译或生成产物，复制到 `../../../work/<case>/` 再做。
4. 不要在共享源码目录里长期留下 `O=build` 或 case patch。

## 构建形态

U-Boot 常见直接构建形态：

```bash
export ARCH=arm64
export CROSS_COMPILE=/home/ives/桌面/NXP_v2/support_level/toolchain/arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-

make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE O=build <defconfig>
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE O=build -j$(nproc)
```

常见产物包括 `build/u-boot.bin`、`build/u-boot-nodtb.bin`、
`build/u-boot.dtb` 等，具体以目标 defconfig 和 SoC 打包要求为准。

如果最终要生成可烧写启动镜像，U-Boot 产物准备好以后回到：

```text
../../../compile_targets/flashbin/README.md
```

继续走 `imx-mkimage` 打包链路。

## 边界

- RTE 版本和是否改用 `real-time-edge-uboot`：看 `../../../software_stacks/rte.md`
- RTE U-Boot 源码线：看 `../real-time-edge-uboot/USAGE.md`
- 最终 `flash.bin` 打包：看 `../../../compile_targets/flashbin/README.md`
- 上板、烧写、串口验证：进入 `board-exec`

一句话：这里回答“通用 `uboot-imx` 怎么查、怎么出 U-Boot 输入”，
不回答“RTE 整套 boot image 应该怎么组”。
