# m_freertos_sdk

这里放的是 `NXP MCUX SDK / FreeRTOS SDK` 发布压缩包资产。

它属于 `release_packages/`，和 `code_assets/projects/` /
`code_assets/workspaces/` 不一样：

- 这里默认是厂商发布包
- 不是普通 Git clone 基线
- 不能通过 checkout / tag / branch 切换版本
- 不应被当成“缺了就自己去网上拉”的源码树

使用规则：

1. 先确认目标板、目标 SDK 版本和当前软件栈要求
2. 再看本地是否已有对应 SDK 压缩包
3. 如果没有，不要自行拿其他版本代替
4. 先找用户要，或者让用户明确提供下载好的官方发布包
5. 解压、修改、编译，放到当前 `work/<case>/` 下做，不要在这里原地改

当前目录适合长期保留的内容：

- 原始 `.zip` / `.tar.gz` 发布包
- `PACKAGES.yaml`：公开 M SDK 清单可选择的包 ID、版本、SoC/board/core role、
  SHA-256 和已知工具链约束
- 必要时可附一个很短的版本说明

当前目录不适合长期保留的内容：

- 解压后被改动的工程
- 编译输出
- 临时 patch
- case 级日志

## 当前已吸收的 SDK 编译边界

这里虽然主要放的是 SDK 发布压缩包资产，
但和 SDK 编译直接相关、又不该写进某块板 `board_knowledge` 的规则，
也可以先在这里收编译边界，再由 `compile_targets/m_freertos_sdk/`
继续细化。

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

## 包登记和导入边界

`PACKAGES.yaml` 当前记录本目录已知的九个 SDK 压缩包及增强验证信息。它不是
唯一准入名单：compile-tool 只检查本轮选中的包；未登记的新包必须由用户提供到
当前 case，并在公开清单中填写路径、SDK release 和信任理由。工具记录实际
SHA-256 为本次软件身份，但只把与已知目录哈希一致的包标为
`catalog_verified`。版本与目录结构冲突仍会阻断，不能按相近文件名猜版本。

厂商预编译镜像通过 `prebuilt_import/vendor_package` 选择压缩包内的精确成员，
状态记录为 `catalog_verified`。用户自己提供的文件不进入本目录，必须先放入
当前 case，并以预期 SHA-256 和信任理由走 `user_supplied`；这类状态只表示
用户声明，不提升为厂商验证。
