# release_packages

这里放不能通过 Git checkout 切版本的厂商 release 包资产。

它和 `code_assets/` 的区别是：

- `code_assets/` 里的源码项目和工作区，可以按任务需要切 branch / tag / commit
- 这里的 release 包不能切版本，只能使用已经下载好的目标版本包
- 如果目标版本本地没有，不要拿相近版本代替，应让用户提供或下载官方对应 release 包

当前目录：

- `m_freertos_sdk/`
  `MCUX SDK / FreeRTOS SDK` 发布压缩包
- `scfw/`
  `i.MX8` 系列 `SCFW` porting kit release 包

使用规则：

1. 先确认目标 SoC / board / BSP 或软件栈要求的 release 包版本
2. 再检查本地是否已有对应版本
3. 本地有就使用本地包
4. 本地没有就停下来让用户提供或下载对应官方包
5. 解压、修改、编译或生成输出，放到 `../work/<case>/`，不要在这里原地污染 release 包

这里不负责：

- 选择最终编译对象
- 承担源码项目的 Git ref 管理
- 记录 case 级构建产物

这些分别交给 `compile_targets/`、`code_assets/` 和 `work/<case>/`。
