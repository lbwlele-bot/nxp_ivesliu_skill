# zephyr

这是 Zephyr 编译对象。

当前本地要特别区分两件事：

- 有 Zephyr 工作区可以拿来编
- 也有某些 workspace 内部带着一份 `zephyr/`，但那不等于它就是默认编译入口

当前本地默认 Zephyr 编译入口：

- `../../code_assets/workspaces/zephyr-workspace/`

常见依赖：

- `../../code_assets/workspaces/zephyr-workspace/`
- `../../toolchain/zephyr-sdk-1.0.1/`
- 必要时再回看 `../../board_knowledge/`

当前输入边界：

- `../../code_assets/workspaces/hmc-workspace/zsdk/` 里虽然也带有 `zephyr/`
- 但它属于 `a55_rtos / heterogeneous-multicore` 工作区的联动输入
- 不应默认把它当成当前 Zephyr 编译入口

正常进入方式：

- 先由 `compile` 判断任务是不是纯 Zephyr 对象
- 如果是，就优先进入 `../../code_assets/workspaces/zephyr-workspace/README.md`
- 再根据具体任务决定是否继续进入 `zephyr/` 工作区

## compile-tool 状态边界

真实构建前，在当前 case 的 `records/compile/zephyr/manifest.yaml`
中显式列出本次实际使用的仓、app、board、配置、工具和输出。
多仓来源可使用 `managed_git_set`，但工具不解析 west manifest，
不自动执行 `west update`，也不补入 manifest 未列出的仓。

`west build` 仍作为完整原始命令展示和执行。是否使用 `-p always`
由项目规则和本次工程判断决定，compile-tool 不改写命令。

不要这样用：

- 不要只因为在 `hmc` 里看到了 `zephyr/`，就从那里开始编
- 不要把 `a55_rtos` 工作区和纯 Zephyr 编译对象混为一谈
