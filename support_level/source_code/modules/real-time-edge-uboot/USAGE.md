# real-time-edge-uboot

- 真实源码目录：`./real-time-edge-uboot/`
- 当前参考分支：`baremetal-uboot_v2020.04`
- 当前参考版本：`Real-Time-Edge-v2.0-baremetal-202107`
- 主要链路：`boot-firmware`

## 使用规则

1. 先确认任务是不是落到 `Real-Time Edge` 的 `U-Boot` 线
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 要改、要编、要出产物，复制到 `../../work/<case>/` 再做

## 已吸收：`imx943-flashbin` 输入角色

在旧 `imx943-flashbin` 里，`real-time-edge-uboot` 不是所有 lane 都要读，
但在 `RTE` 路径里需要作为重要候选输入来判断，而不是默认只看 `uboot-imx`。

对 `i.MX943`：

- generic Linux 更偏向 board-generic `uboot-imx`
- `RTE 3.3` / `RTE 3.4` 需要额外判断是否应转到 `Real-Time Edge` 的 `U-Boot` 线

当前版本观察：

- 本地这份 `real-time-edge-uboot` 目前是 `Real-Time-Edge-v2.0-baremetal-202107`
- 但旧 `imx943-flashbin` 里 `RTE 3.4` 的参考 `U-Boot` 更接近 `uboot_v2025.04-3.4.0`

这说明：

- 当前这份 `real-time-edge-uboot` 还不能直接充当 `i.MX943 RTE 3.4 flashbin` 的现成长期基线
- 后续还要继续从 `_to_absorb/` 或其他已复制资产里拆出更合适的版本

## 已吸收：`imx95-rte33-build-flashbin` 输入角色

对 `i.MX95 RTE 3.3 flash.bin`：

- `U-Boot` owner 明确落在 `real-time-edge-uboot`
- 而不是通用 `uboot-imx`

关键点：

- 已验证旧 skill 使用的是 `Real-Time-Edge-v3.3-uboot-202512` 这一条线
- 它属于 case delta，不应和 generic Linux 的 `uboot-imx` 混看
- 对这条 lane，A-core side 的 toolchain family 也要明确落在
  Linux-targeted `aarch64-none-linux-gnu`

当前版本缺口：

- 本地这份 `real-time-edge-uboot` 目前还是 `Real-Time-Edge-v2.0-baremetal-202107`
- 还没对齐到旧 skill 里 `i.MX95 RTE 3.3` 需要的版本

所以当前能沉淀的是：

- owner 归属
- lane 选择规则
- A-core toolchain owner 归属

还不能把当前目录直接当成那条 validated lane 的现成源码基线

## 待补全

- 不同 RTE 版本下的用法
- 和 `flash.bin` 打包链的关系
- 相关旧 skill 的吸收结果
