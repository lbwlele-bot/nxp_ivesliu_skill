# m_freertos_sdk

这里放的是 `NXP MCUX SDK / FreeRTOS SDK` 发布压缩包资产。

它和 `source_code/` 不一样：

- 这里默认是厂商发布包
- 不是普通 Git clone 基线
- 不应被当成“缺了就自己去网上拉”的源码树

使用规则：

1. 先看本地 `m_freertos_sdk/` 里有没有目标板、目标版本的 SDK 压缩包
2. 如果没有，不要自行去网上下载
3. 先找用户要，或者让用户明确提供下载好的发布包
4. 解压、修改、编译，放到当前 `work/<case>/` 下做，不要在这里原地改

当前目录适合长期保留的内容：

- 原始 `.zip` / `.tar.gz` 发布包
- 必要时可附一个很短的版本说明

当前目录不适合长期保留的内容：

- 解压后被改动的工程
- 编译输出
- 临时 patch
- case 级日志

## 当前已吸收的 SDK 编译边界

这里虽然主要放的是 SDK 发布压缩包资产，
但和 SDK 编译直接相关、又不该写进某块板 `board_knowledge` 的规则，
也可以先在这里收编译边界，再由具体源码模块手册继续细化。

### `i.MX8DXL` `M4` 构建边界

对 `i.MX8DXL M4`：

- 除非明确要求 `NOR flash` 或其他 flash 链接构建方式，
  默认优先非 `flash` linker / build 方式
- 名字里带：
  `flash_debug`
  `flash_release`
  `*_flash.ld`
  默认视为 flash-linked
- 名字里带：
  `debug`
  `release`
  `*_ram.ld`
  默认视为 RAM / TCM 装载方式
- 如果当前目标是 `flash_m4` 打包产物，
  优先标准目标：
  `make SOC=iMX8DXL REV=A1 flash_m4`
- 不要默认直接调用 `mkimage_imx8`

这类内容属于 SDK / M 核编译边界，
不属于某一块板的板级默认事实。
