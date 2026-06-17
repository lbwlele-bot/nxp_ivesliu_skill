# workspaces

这里放有长期价值的多模块集成工作区。

它和 `projects/` 的区别是：

- `projects/` 适合按单个源码项目长期管理
- 这里适合整体协同才有意义的源码工作区

当前已保留的工作区包括：

- `zephyr-workspace`
  当前本地默认的 Zephyr 工作区入口
- `hmc-workspace`
  `heterogeneous-multicore / zsdk / mcuxsdk` 的集成工作区入口

使用规则：

- 先读对应工作区自己的 `README.md`
- 确认这个工作区在当前任务里承担什么角色
- 如果任务只是查源码资产，优先回到 `../projects/`
- 如果任务已经变成“我要编什么”，优先回 `../../compile_targets/` 或 `compile`
