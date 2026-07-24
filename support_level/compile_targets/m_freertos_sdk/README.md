# m_freertos_sdk

这是 `M` 核 `FreeRTOS SDK` 编译对象。

它的默认编译入口不是普通 Git 源码项目，
而是 `MCUX SDK / FreeRTOS SDK` 发布包。

这个对象有双重身份：

- 它可以是独立可验证的 `M` 核应用产物，
  后续由 U-Boot、Linux remoteproc 或其他板级路径加载
- 它也可以只是 `flashbin` 链路的一个 payload 输入，
  最终仍要回到 `../flashbin/` 产出完整 `flash.bin`

常见依赖：

- `../../release_packages/m_freertos_sdk/`
- `../../toolchain/`
- 必要时再回看：
  `../../code_assets/projects/mcuxsdk-core/`

正常进入方式：

- 先确认目标板和目标版本的 SDK 发布包是否已经在本地
- 再确认本次成功标准是“独立 M 核产物”还是“作为 `flash.bin` 输入”
- 再把 SDK 解压到 `../../work/<case>/`
- 真正做 case 构建时，从 case 目录里的 SDK 工程开始

如果作为独立产物：

- 这里负责产出可被后续加载路径消费的 M 核二进制
- 后续如何通过 U-Boot、Linux remoteproc 或其他方式加载，
  属于 `board-exec` 或对应板级知识的范围

如果作为 `flash.bin` 输入：

- 这里只负责把 M 核 payload 编出来
- payload 准备好后必须回到 `../flashbin/`
- 由 `flashbin` 再选择合适的 `soc.mak` recipe，
  打出完整可烧写的 `flash.bin`

## 已验证工具链注意事项

`SDK_2_9_0_EVK-MIMX8DXL` 的 `power_mode_switch` readme 要求
`GCC ARM Embedded 9.2.1`。本机已验证：

- `gcc-arm-none-eabi-9-2019-q4-major` 可成功构建 `build_debug.sh`
- `arm-gnu-toolchain-14.3.rel1-x86_64-arm-none-eabi` 会在
  `devices/MIMX8DL1/utilities/fsl_sbrk.c` 报 `unknown type name 'caddr_t'`

因此该 SDK 的 DXL demo 默认优先用旧 GCC 9.2.1 lane，
不要为了“工具链更新”直接替换到 14.x。

不要这样用：

- 不要默认从 `../../code_assets/projects/mcuxsdk-core/` 直接起编译
- 不要缺包就自己去网上拉，先找用户要或确认本地已有包
- 不要在 `../../release_packages/m_freertos_sdk/` 原地修改或生成输出
- 不要把 M 核 payload 编译成功等同于整条启动镜像链路已经完成
