# a55_rtos

这是 `A55` / `A` 核 `RTOS` 编译对象。

当前本地这条线的关键点不是“仓库在哪”，
而是要先钉死主对象和联动输入的边界。

当前主对象：

- `../../code_assets/workspaces/rte-hmc-latest/heterogeneous-multicore/`

当前联动输入：

- `../../code_assets/workspaces/rte-hmc-latest/zsdk/`
- `../../code_assets/workspaces/rte-hmc-latest/mcuxsdk/`
- `../../toolchain/`

必须写死的规则：

- `heterogeneous-multicore` 是这条线的主对象
- `zsdk/`、`mcuxsdk/` 是同一工作区里的联动输入
- 即使 `hmc` 目录下面带有 `zephyr/`、`mcuxsdk`，也不能据此推导出：
  - `zephyr` 应该从这里编
  - `mcuxsdk` 应该从这里编

正常进入方式：

- 先由 `compile` 判断任务是否真的是 `A55 RTOS / HMC` 对象
- 如果是，再进入 `../../code_assets/workspaces/rte-hmc-latest/README.md`
- 再由该工作区和 `heterogeneous-multicore` 本体决定具体构建动作

什么时候不该留在这里：

- 如果任务其实是在编纯 Zephyr 应用，转去 `../zephyr/`
- 如果任务其实是在编 `M` 核 SDK 工程，转去 `../m_freertos_sdk/`
