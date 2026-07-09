# imx-atf

- 真实源码目录：`./imx-atf/`
- 当前参考分支：`lf_v2.12`
- 当前参考版本：`lf-6.18.2-1.0.0`
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

`RTE` / `OP-TEE` 路径需要安全世界 dispatcher：

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
- `RTE` / `OP-TEE` 路径通常需要 `SPD=opteed`
- `i.MX95` generic Linux 旧验证路径要求构建前 `unset LDFLAGS` 和 `unset AS`
- `RTE` 路径需要同步 `meta-real-time-edge` 的 `ATF` patch 分桶时，只同步 `ATF` 自己的 patch
- 不要把整套 `meta-real-time-edge` patch 集直接灌进 `imx-atf`

## 已吸收：`imx943-flashbin` 输入角色

在旧 `imx943-flashbin` 里，`ATF` 是 `i.MX943 flashbin` 链的上游输入之一。

对 `i.MX943`：

- 通用 Linux 路径通常不要求 `SPD=opteed`
- `RTE` 路径要求 `SPD=opteed`
- 最终提供给 `imx-mkimage` 的关键产物是 `bl31.bin`

当前版本观察：

- 本地这份 `imx-atf` 是 `lf-6.18.2-1.0.0`
- 这一点和旧 skill 里 `RTE 3.4` 的期望家族一致

## 已吸收：`imx95-rte33-build-flashbin` 输入角色

对 `i.MX95 RTE 3.3 flash.bin`：

- `ATF` 不再只是共享 启动固件 输入
- 它还承担明确的安全世界差异项

关键点：

- 必须用 `SPD=opteed`
- 需要同步 `meta-real-time-edge` 的 `ATF` patch 分桶
- 最终仍然向 `imx-mkimage` 提供 `bl31.bin`

高风险误区：

- 不要把整个 `meta-real-time-edge` patch 集全灌进 `ATF`
- 这里只该吃 `ATF` 自己的 patch 分桶

## 待补全

- 相关旧 skill 的吸收结果
