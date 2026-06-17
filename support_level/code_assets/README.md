# code_assets

这里放本地长期保留的代码资产。

这层再分成两类：

- `projects/`
  单个源码项目资产，默认按标准源码基线管理
- `workspaces/`
  只有整体协同才有意义的工作区资产

当前可直接给上层的简短理解是：

- `projects/` 放单个源码项目或源码发布包，回答“本地有哪些代码基线、它们各自负责哪一段”
- `workspaces/` 放需要多仓协同才能成立的集成工作区，回答“哪条对象线需要按整体 workspace 去理解”

这层只负责回答：

- 本地有哪些代码资产
- 它们分别属于源码项目，还是工作区
- 它们真实放在什么位置

按链路粗分，当前内容大致包括：

- 启动固件链：`imx-atf`、`imx-mkimage`、`imx-oei`、`imx-optee-os`、`imx-sm`、`uboot-imx`、`real-time-edge-uboot`、`imx-scfw-porting-kit`
- Linux BSP 链：`linux-imx`、`real-time-edge-linux`、`meta-real-time-edge`
- M 核 / SDK 代码参考链：`mcuxsdk-core`
- Android 资产：`android`
- 集成工作区：`hmc-workspace`、`zephyr-workspace`

如果只是查代码资产位置或角色，先留在这层。
如果任务已经变成“我要编什么”，回 `../compile_targets/` 或 `compile`。
