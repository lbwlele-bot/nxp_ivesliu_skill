# scfw

- 真实 release 包目录：`./imx-scfw-porting-kit-1.18.0/`
- 当前已落地版本：`1.18.0`
- 主要链路：`启动固件`

## 使用规则

1. 先确认任务是不是确实落到 `SCFW` patch、配置或重编
2. 先核对目标 SoC / silicon revision / BSP 版本对应的 `SCFW` release 包版本
3. 只读检查可直接在这里做
4. 要改、要编、要出产物，复制到 `../../work/<case>/` 再做

## 当前定位

这是 `i.MX8` 系列 `SCFW` 的 porting kit release 包资产入口。

它不是普通 Git 源码基线。
当前本地保存的是 NXP release 包 `imx-scfw-porting-kit-1.18.0`，
包内包含 `VERSION`、`SCR.txt` 和 `src/scfw_export_*.tar.gz` 等发布内容。

`SCFW` 有严格版本对应关系。
不能因为本地有一个 porting kit，就默认它适用于当前 SoC、silicon revision、
BSP release 或已有 `flash.bin` 链路。
使用前必须确认当前任务需要的官方 release 版本。

如果本地已经有目标版本 release 包，就直接使用本地包；
如果本地没有目标版本，不要临时猜路径或拿别的版本代替，
应让用户提供或下载对应官方 release 包后再继续。

当前优先服务的复用场景是：

- `i.MX8DXL` `SCFW` patch
- `SCFW` 构建输入和产物关系确认
- `flash.bin` / `flash_m4` 链路里的 `SCFW` 来源核对

它不负责：

- 板级下载和运行验证
- 客户 release 包的完整交付流程
- 其他版本 `SCFW` release 包的替代来源

这些动作应转到对应 case、`compile` 或 `board-exec`。
