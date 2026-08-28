# m_freertos_sdk

这是 M 核 SDK 的独立 producer。它先生产带身份的 ELF/BIN，随后才由
imx-mkimage、Linux remoteproc 或其它 consumer 选择需要的格式。

## 唯一公开编译入口

把本目录 `COMPILE_CHECKLIST.yaml` 复制到当前 case 的固定位置：

```text
records/compile/m_freertos_sdk/compile.yaml
```

AI 只填写 SDK 包、编译器、具名 jobs 和 `intent.scope/reason`，然后提交：

```bash
compile-tool prepare <case>/records/compile/m_freertos_sdk/compile.yaml
compile-tool run <case>/records/compile/m_freertos_sdk/compile.yaml
```

不能填写 raw command、backend、任意输出路径或内部 manifest/request。
工具根据本轮实际 SDK 包和 job 生成全部命令、环境变量及发布路径。

SDK 包不是 AI 可以自动获取的 Git 源码。本地没有目标包时，`prepare` 固定返回
`USER_INPUT_REQUIRED`，列出包 ID、版本和期望放置位置；AI 必须停下来找用户要，
或者请用户登录 NXP 下载后放入当前 case。用户提供的新包可在 `sdk` 中增加
`archive`、`sdk_release` 和 `trust_reason`，无需先修改全局 `PACKAGES.yaml`。
工具只检查本轮选中的包并自动记录实际 SHA-256；已知目录哈希一致时标记为
`catalog_verified`，否则标记为 `user_attested`，不伪装成已知厂商包验证。

一张清单可以声明多个 job，例如 `m33s`、`m70`、`m71`。每个 job 独立维护
状态；`intent.scope` 只重建或导入本轮选择的 job，范围外 job 必须已有可复用
成功状态。

## 来源和产物

- `source_build`：必须从同一 job 发布 `<job>.elf` 和 `<job>.bin`，分别导出
  `nxp.mcore.elf` 与 `nxp.mcore.bin`。
- `prebuilt_import/vendor_package`：只允许导入本轮已确认 SDK 压缩包中的明确
  成员；工具校验选中包和成员，允许只有 BIN。包来自已知目录时为
  `catalog_verified`，来自用户新提供文件时继承 `user_attested`。
- `prebuilt_import/user_supplied`：文件必须位于当前 case，清单填写预期
  SHA-256 和信任理由；状态标为 `user_attested`，不声称厂商验证。

artifact identity 至少包含 `soc`、`board`、`core`、`core_role`、
`application`、`build_configuration`、`sdk_release` 和 `origin`。Linux
remoteproc 后续可以消费 ELF；flash.bin 只允许消费 `nxp.mcore.bin`。

## backend 硬规则

- SDK `2.x`：legacy。
- YYMM `<= 25.09`：legacy。
- YYMM `>= 25.12`：MCUX West。
- `25.10/25.11`或无法解析的版本：阻断；用户新提供包无需预先登记，但必须
  明确 SDK release、case 内路径和信任理由。
- 版本选择与压缩包结构不一致：阻断。

legacy 必须存在精确的
`boards/.../<core>/armgcc/build_<configuration>.sh`，工具执行该脚本并解析
项目声明的 ELF/BIN。West 必须包含 `.west/config`、`manifests/west.yml`、
MCUX West build 扩展和匹配 job 的 `example.yml`；工具生成受控
`west build`，将 `board@core` 拆为 `-b <board>` 与 `-Dcore_id=<core>`，并用
`-p always` 隔离失败缓存。

工具自动设置 `ARMGCC_DIR` 并记录编译器身份。当前
`SDK_2_9_0_EVK-MIMX8DXL` 源码构建仍强制 GCC 9.2.1；预编译导入不伪装成
本地构建，也不要求为了导入 BIN 重新编译 SDK。

## 与 flash.bin 的边界

M producer 只负责产出 M 核 artifact。imx-mkimage 的 `soc.mak` 决定当前 recipe
实际需要哪些 M 镜像和文件名，compile-tool 再补 producer identity：

- 当前源码的 i.MX95 `flash_all` 由 `soc.mak` 得出 `core_role=m7` 的 BIN；
- 当前源码的 i.MX94 `flash_all` 由 `soc.mak` 得出 `m33s`、`m70`、`m71` BIN；
- recipe 内部固定落位为 `m7_image.bin`、`m33s_image.bin`、
  `m70_image.bin`、`m71_image.bin`，AI 不能改名。

可信预编译 BIN 也必须先经过本清单导入，不能作为 mkimage 裸文件输入。
producer 成功不等于 flash.bin 已经打包成功，更不等于 M 核已上板运行。

相关资产：

- `../../release_packages/m_freertos_sdk/PACKAGES.yaml`
- `../../release_packages/m_freertos_sdk/`
- `../../toolchain/`
- 必要时回看 `../../code_assets/projects/mcuxsdk-core/`
