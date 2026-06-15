# uboot-imx

- 真实源码目录：`./uboot-imx/`
- 当前参考分支：`lf_v2025.04`
- 当前参考版本：`lf-6.18.2-1.0.0`
- 主要链路：`boot-firmware`

## 使用规则

1. 先确认任务是不是落到通用 `uboot-imx`
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 要改、要编、要出产物，复制到 `../../work/<case>/` 再做

## 已吸收：`imx943-flashbin` 输入角色

在旧 `imx943-flashbin` 里，`U-Boot` 是 `flash.bin` 的核心输入之一。

对 `i.MX943`：

- generic Linux 常走 board-generic `flash_a55`
- `RTE` 可能走 `flash_a55`，也可能在验证过的 `3.4` 路径里走 `flash_all`
- 这条链里既要注意通用 `uboot-imx`，也要注意某些 `RTE` lane 可能改用 `real-time-edge-uboot`

当前版本观察：

- 本地这份 `uboot-imx` 是 `lf-6.18.2-1.0.0`
- 但旧 `RTE 3.4` lane 的 `U-Boot` 参考更接近 `real-time-edge-uboot`
- 所以 `i.MX943 flashbin` 任务里，不能不分栈地直接默认只看这一份 `uboot-imx`

## 待补全

- 不同芯片/版本的构建命令
- 典型 defconfig / 产物
- 相关旧 skill 的吸收结果
