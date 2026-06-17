# zephyr

这是 Zephyr 编译对象。

当前本地要特别区分两件事：

- 有 Zephyr 工作区可以拿来编
- 也有某些 workspace 内部带着一份 `zephyr/`，但那不等于它就是默认编译入口

当前本地默认 Zephyr 编译入口：

- `../../code_assets/workspaces/rte33-zsdk/`

常见依赖：

- `../../code_assets/workspaces/rte33-zsdk/`
- `../../toolchain/zephyr-sdk-1.0.1/`
- 必要时再回看 `../../board_knowledge/`

当前输入边界：

- `../../code_assets/workspaces/rte-hmc-latest/zsdk/` 里虽然也带有 `zephyr/`
- 但它属于 `a55_rtos / heterogeneous-multicore` 工作区的联动输入
- 不应默认把它当成当前 Zephyr 编译入口

正常进入方式：

- 先由 `compile` 判断任务是不是纯 Zephyr 对象
- 如果是，就优先进入 `../../code_assets/workspaces/rte33-zsdk/README.md`
- 再根据具体任务决定是否继续进入 `zephyr/` 工作区

不要这样用：

- 不要只因为在 `hmc` 里看到了 `zephyr/`，就从那里开始编
- 不要把 `a55_rtos` 工作区和纯 Zephyr 编译对象混为一谈
