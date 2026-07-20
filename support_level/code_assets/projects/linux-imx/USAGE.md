# linux-imx

- 真实源码目录：`./linux-imx/`
- 最近观察分支（使用前重新核对）：`lf-6.12.y`
- 最近观察版本（使用前重新核对）：`lf-6.12.49-2.2.0`
- 主要链路：通用 `Linux BSP` 内核源码

## 角色

`linux-imx` 是通用 Linux BSP 内核源码入口。
它负责生成 Linux 侧产物，例如：

```text
Image
dtb
modules
```

本页只负责 `linux-imx` 项目自己的源码核对、内核构建命令和产物交接。
当前任务到底属于通用 Linux 还是 `Real-Time Edge Linux`，
先由：

- `../../../compile_targets/linux/README.md`
- 必要时 `../../../software_stacks/rte.md`

决定。

## 使用前提

进入本页前，至少先确认：

- 当前任务确实属于通用 `linux-imx`，不是 `real-time-edge-linux`
- 目标 SoC / board
- 目标 `dtb` 名称
- Linux 版本家族或目标 ref
- A-core / Linux side 工具链
- 最终只交付 Linux 侧产物，还是还要进入完整启动镜像链路

如果当前问题仍是启动链早期失败，不要默认从重编 Linux 开始；
先回到 `compile_targets/flashbin/` 或 `board-exec` 判断 owner。

## 共享源码规则

1. 先用 `git status --short --branch` 和 `git describe --tags --always --dirty` 核对当前 ref
2. 只读检查可直接在共享源码目录做
3. 要改内核、编译、生成 `Image` / `dtb` / modules，复制到 `../../../work/<case>/` 再做
4. 不要在共享源码目录里长期留下 `O=build` 或 modules staging 输出

## 本地线索

当前源码里可见的通用 i.MX arm64 defconfig 是：

```text
arch/arm64/configs/imx_v8_defconfig
```

当前源码里可见的代表性 i.MX9 dtb 包括：

```text
arch/arm64/boot/dts/freescale/imx943-evk.dts
arch/arm64/boot/dts/freescale/imx95-19x19-evk.dts
arch/arm64/boot/dts/freescale/imx93-14x14-evk.dts
```

这些只是源码中存在的候选文件。
实际 `dtb` 必须按当前板型、封装、DDR、carrier 和 case 目标确认。

## 工具链形态

本地 A-core Linux 工具链候选：

```bash
export CROSS_COMPILE=/home/ives/桌面/NXP_v2/support_level/toolchain/arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-
export ARCH=arm64
```

如果当前 case 指定其他 toolchain，以 case 要求为准。

## 构建命令形态

通用配置：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/linux-imx
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE O=build imx_v8_defconfig
```

构建常见内核产物：

```bash
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE O=build -j$(nproc) Image dtbs modules
```

只构建指定 dtb：

```bash
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE O=build freescale/<board>.dtb
```

安装 modules 到 staging 目录：

```bash
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE O=build INSTALL_MOD_PATH=modules-out modules_install
```

这些是命令形态，不是固定 case 配方。
实际 defconfig、dtb、module 范围和 staging 目录必须按当前 case 确认。

## 产物交接

使用 `O=build` 时，典型产物在：

```text
build/arch/arm64/boot/Image
build/arch/arm64/boot/dts/freescale/<board>.dtb
modules-out/lib/modules/<kernel-release>/
```

如果当前目标只是 Linux 侧交付，
这些产物可以直接进入当前 case 的 artifacts / handoff。

如果最终要生成可烧写启动镜像，
Linux 侧产物准备好以后还要回到：

```text
../../../compile_targets/flashbin/README.md
```

继续判断完整 boot image 输入集合。

## 不该在这里判断的事

- 不在这里决定当前任务是否属于 `Real-Time Edge Linux`
- 不在这里决定 `flash.bin` recipe
- 不在这里解释烧写、启动、登录或运行态验证
- 不在这里把“板子起不来”默认改写成“需要重编 Linux”

这些分别属于 `compile_targets/linux/`、`software_stacks/`、
`compile_targets/flashbin/` 和 `board-exec`。
