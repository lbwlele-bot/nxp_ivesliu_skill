# imx-atf

- 真实源码目录：`./imx-atf/`
- 最近观察分支（使用前重新核对）：`lf_v2.12`
- 最近观察版本（使用前重新核对）：`lf-6.18.2-1.0.0`
- 主要链路：`启动固件`

## 使用规则

1. 先确认这次任务是不是确实落到 `ATF`
2. 先用 `git status --short --branch` 和 `git describe --tags --always --dirty` 核对当前 ref
3. 只读检查可直接在这里做
4. 要改、要编、要出产物，复制到 `../../../work/<case>/` 再做

## 构建前提

先钉死这些字段，再开始编：

- 目标 SoC：例如 `imx94` / `imx95`
- 软件栈：generic Linux 还是 `RTE` / `OP-TEE`
- 工具链：A-core side，优先显式传 `CROSS_COMPILE`
- 工作目录：只读检查可在共享源码做，构建和补丁应在 `../../../work/<case>/`

如果软件栈是 `RTE`，先读 `../../../software_stacks/rte.md`。
`RTE` 是否需要 `OP-TEE`、`SPD=opteed`、ATF patch bucket，
这些是软件线规则，不由本页单独决定。

本地可用 A-core 工具链候选：

```bash
export CROSS_COMPILE=/home/ives/桌面/NXP_v2/support_level/toolchain/arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-
```

## 典型构建命令

通用 `bl31.bin` baseline：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-atf
unset LDFLAGS
unset AS
make PLAT=imx95 bl31
```

`i.MX943` 在 ATF 平台名上对应 `imx94`：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-atf
unset LDFLAGS
unset AS
make PLAT=imx94 bl31
```

上层已经判定为 `RTE` / `OP-TEE` 路径时，ATF 局部构建通常需要安全世界 dispatcher：

```bash
cd /home/ives/桌面/NXP_v2/support_level/work/<case>/imx-atf
unset LDFLAGS
unset AS
make PLAT=imx95 SPD=opteed bl31
```

## 产物位置

典型产物：

```text
build/<plat>/release/bl31.bin
```

例如：

```text
build/imx95/release/bl31.bin
build/imx94/release/bl31.bin
```

`bl31.bin` 是 `imx-mkimage` 的上游输入。
单独编出 `bl31.bin` 不等于 `flash.bin` 已经完成。

## 构建边界

- generic Linux 通常不加 `SPD=opteed`
- 上层已经判定为 `RTE` / `OP-TEE` 路径时，ATF 局部动作通常包含 `SPD=opteed`
- `i.MX95` generic Linux 旧验证路径要求构建前 `unset LDFLAGS` 和 `unset AS`
- `RTE` 路径需要同步 `meta-real-time-edge` 的 `ATF` patch 分桶时，只同步 `ATF` 自己的 patch
- 不要把整套 `meta-real-time-edge` patch 集直接灌进 `imx-atf`

## 待补全

- 不同 SoC / LF 版本下的 ATF 平台名和产物差异
- ATF patch bucket 的本地实际目录结构
