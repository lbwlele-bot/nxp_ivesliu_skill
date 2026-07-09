# linux-imx

- 真实源码目录：`./linux-imx/`
- 当前参考分支：`lf-6.12.y`
- 当前参考版本：`lf-6.12.49-2.2.0`
- 主要链路：`linux-bsp`

## 使用规则

1. 先确认任务是不是落到通用 `linux-imx` BSP 内核线
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 要改内核、编译、出 `Image/dtb/modules`，复制到 `../../../work/<case>/` 再做

## 构建前提

先钉死这些字段，再开始编：

- 当前任务确实属于通用 `linux-imx`，不是 `real-time-edge-linux`
- 目标板型和目标 `dtb` 名称明确
- 工具链属于 A-core / Linux side
- 工作目录是 `../../../work/<case>/` 里的 case-local copy

本地可用 A-core Linux 工具链：

```bash
export CROSS_COMPILE=/home/ives/桌面/NXP_v2/support_level/toolchain/arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-
export ARCH=arm64
```

## 典型构建命令

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
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE O=build freescale/imx943-evk.dtb
```

安装 modules 到 staging 目录：

```bash
make ARCH=arm64 CROSS_COMPILE=$CROSS_COMPILE O=build INSTALL_MOD_PATH=modules-out modules_install
```

## 产物位置

使用 `O=build` 时，典型产物在：

```text
build/arch/arm64/boot/Image
build/arch/arm64/boot/dts/freescale/<board>.dtb
modules-out/lib/modules/<kernel-release>/
```

不使用 `O=build` 时，产物会落在源码树内：

```text
arch/arm64/boot/Image
arch/arm64/boot/dts/freescale/<board>.dtb
```

## 构建边界

- `linux-imx` 负责 `Image`、`dtb`、`.ko`
- `linux-imx` 不负责上板传输、启动、登录或运行态证明
- `RTE` Linux 先切到 `real-time-edge-linux`，不要在这里强行套用通用 Linux 路径
- 如果当前问题仍是启动链早期失败，不要默认通过重编 Linux 解决

## 已吸收：`imx943-linux` 输入角色

对 `i.MX943` Linux 内核侧链路：

- `linux-imx` 是通用 Linux 的板级通用内核源码候选之一
- 它负责的是：
  `Image`
  `dtb`
  `.ko`
- 不负责：
  上板写入传输
  运行态验证

关键边界：

- 如果上层只说 `RTE`，没有 version，不要替它选 branch
- 如果当前问题其实还是启动链早期失败，不要为了板子起不来就默认重编 Linux

## 第一轮吸收后的链路认知

- 通用 Linux：
  更偏向 `linux-imx`
- `RTE`：
  要再看是不是应切到 `real-time-edge-linux` 和 `meta-real-time-edge`

所以这里当前能稳定吸收的是：

- 内核侧产物边界
- 通用 Linux 侧的源码归属语义

还不是所有 `i.MX943` Linux 链路的唯一源码答案

## 待补全

- 相关旧 skill 的吸收结果
