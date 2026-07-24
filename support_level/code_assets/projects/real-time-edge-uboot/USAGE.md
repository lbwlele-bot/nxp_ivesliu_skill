# real-time-edge-uboot

- 真实源码目录：`./real-time-edge-uboot/`
- 最近观察 ref：`baremetal-uboot_v2020.04` / `Real-Time-Edge-v2.0-baremetal-202107`，使用前重新核对
- 主要链路：`rte`、`U-Boot`、启动固件输入

这是 Real-Time Edge U-Boot 源码线的本地副本。

它只在当前软件栈已经确认需要 RTE U-Boot 时才看。
是否需要从通用 `uboot-imx` 切到这里，先由：

- `../../../software_stacks/rte.md`
- `../../../compile_targets/flashbin/README.md`

决定。

## 当前版本提醒

最近核对到当前本地副本还是较老的 `Real-Time-Edge-v2.0-baremetal-202107`
线，并且 `configs/` 下没有看到 `imx91`、`imx93`、`imx943`、`imx95`
这类 i.MX9 defconfig。

所以对 i.MX95 / i.MX943 的 RTE 3.3、RTE 3.4 任务，不要直接把当前目录
当作可用源码基线。应先核对目标 RTE 版本需要的 U-Boot branch / tag；
本地没有对应版本时，让用户提供或下载。

`meta-real-time-edge` 里可能有 RTE U-Boot 分支线索，例如
`REAL_TIME_EDGE_UBOOT_BRANCH`，但最终仍以当前 case 指定的软件栈版本为准。

## 什么时候看这里

- 当前任务明确属于 RTE U-Boot 线
- 需要查 RTE U-Boot 与通用 `uboot-imx` 的差异
- 需要按目标 RTE 版本核对 branch、tag、defconfig 或 boot flow
- 需要重建 RTE U-Boot 输入，再交给 `imx-mkimage` 打 `flash.bin`

## 使用规则

1. 先用 `git status --short --branch` 和 `git describe --tags --always --dirty`
   核对当前 ref。
2. 再确认当前 ref 是否就是目标 RTE 版本需要的源码线。
3. 只读查代码、配置、DTS 可以直接在共享源码目录做。
4. 要改代码、编译或生成产物，复制到 `../../../work/<case>/` 再做。
5. 如果目标版本缺失，不要拿当前旧副本硬代替。

## 构建形态

确认源码版本和 defconfig 都匹配以后，直接构建形态仍类似 U-Boot：

```bash
export CROSS_COMPILE=/home/ives/桌面/NXP_v2/support_level/toolchain/arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-

make CROSS_COMPILE=$CROSS_COMPILE O=build <defconfig>
make CROSS_COMPILE=$CROSS_COMPILE O=build -j$(nproc)
```

具体 defconfig、产物名称和交给 `imx-mkimage` 的输入，必须按目标 SoC、
RTE 版本和当前 case 核对。

## 边界

- 通用 U-Boot 源码线：看 `../uboot-imx/USAGE.md`
- RTE 版本和跨项目约束：看 `../../../software_stacks/rte.md`
- RTE Yocto layer、bbappend、branch 线索：看 `../meta-real-time-edge/USAGE.md`
- 最终 `flash.bin` 打包：看 `../../../compile_targets/flashbin/README.md`
- 上板、烧写、串口验证：进入 `board-exec`

一句话：这里回答“选中 RTE U-Boot 以后怎么核对源码线、怎么出 U-Boot 输入”，
不回答“所有 RTE 版本都能直接用当前本地副本编”。
