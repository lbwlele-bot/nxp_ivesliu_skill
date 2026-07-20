# a55_rtos

这是 `A55` / `A` 核 `RTOS` 编译对象。

当前本地这条线的关键点不是“仓库在哪”，
而是要先钉死主对象和联动输入的边界。

这个对象面向的是 A 核 RTOS / HMC 这条产物线，
不是 `flash.bin` 打包 recipe 的别名。
如果最终需要把它和启动固件一起做成可烧写镜像，
它应先作为本对象产出，再交给 `../flashbin/` 处理最终打包。

当前主对象：

- `../../code_assets/workspaces/hmc-workspace/heterogeneous-multicore/`

当前联动输入：

- `../../code_assets/workspaces/hmc-workspace/zsdk/`
- `../../code_assets/workspaces/hmc-workspace/mcuxsdk/`
- `../../toolchain/`

必须写死的规则：

- `heterogeneous-multicore` 是这条线的主对象
- `zsdk/`、`mcuxsdk/` 是同一工作区里的联动输入
- 即使 `hmc` 目录下面带有 `zephyr/`、`mcuxsdk`，也不能据此推导出：
  - `zephyr` 应该从这里编
  - `mcuxsdk` 应该从这里编

正常进入方式：

- 先由 `compile` 判断任务是否真的是 `A55 RTOS / HMC` 对象
- 再确认本次成功标准是独立 A 核 RTOS 产物，
  还是要继续进入完整 `flash.bin` 链路
- 如果是，再进入 `../../code_assets/workspaces/hmc-workspace/README.md`
- 再由该工作区和 `heterogeneous-multicore` 本体决定具体构建动作

与 `flashbin` 的关系：

- `a55_rtos` 负责 A 核 RTOS / HMC 自己的构建入口和联动输入边界
- 如果该产物需要进入 boot image，
  后续回到 `../flashbin/` 决定完整输入集合和 `soc.mak` recipe
- 不要从 “A55 RTOS” 这个对象名直接推出 `flash_a55`

什么时候不该留在这里：

- 如果任务其实是在编纯 Zephyr 应用，转去 `../zephyr/`
- 如果任务其实是在编 `M` 核 SDK 工程，转去 `../m_freertos_sdk/`
- 如果任务其实是在打完整 `flash.bin`，转去 `../flashbin/`
