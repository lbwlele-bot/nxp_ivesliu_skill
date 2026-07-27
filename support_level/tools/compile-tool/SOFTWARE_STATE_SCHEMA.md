# Flashbin Software State Schema

## Compile Manifest

manifest 固定放在：

```text
work/<case>/records/compile-manifest.yaml
```

最小根结构：

```yaml
schema_version: 1
case: <case-directory-name>
case_root: /absolute/path/to/work/<case>
target: flashbin

identity:
  soc: <value>
  silicon_revision: <value>
  chip_package: <value>
  board: <value>
  ddr: <value>
  software_release: <value>

identity_notes: {}
components: {}
```

身份字段不能是空值、`unknown`、`TBD`、`TODO` 或 `?`。
身份使用 `N/A` 时，必须有对应 `identity_notes`。

## Component Coverage

manifest 必须逐项声明：

```text
atf smfw uboot optee oei m_payload firmware scfw ahab flashbin
```

不使用的组件：

```yaml
optee:
  status: not_applicable
  reason: 当前 recipe 不包含 tee.bin
```

固定输入：

```yaml
scfw:
  status: enabled
  inputs:
    - /absolute/path/to/scfw.bin
```

Git 构建组件：

```yaml
atf:
  status: enabled
  source:
    kind: managed_git
    canonical_path: /absolute/support_level/code_assets/projects/imx-atf/imx-atf
    case_path: /absolute/work/<case>/build/imx-atf
    ref_kind: tag
    ref: lf-6.18.2-1.0.0
    remote: origin
    remote_url: https://github.com/nxp-imx/imx-atf
    update: if_missing
  configuration:
    values:
      PLAT: imx8dxl
    files: []
  toolchains:
    - executable: /absolute/toolchain/bin/aarch64-none-linux-gnu-gcc
      version_args: [--version]
  outputs:
    - /absolute/work/<case>/artifacts/atf/bl31.bin
```

`update`：

- `if_missing`：本地 ref 存在时不联网
- `pull_ff_only`：只适用于当前 canonical checkout 的跟踪分支

非 Git 的本地源码输入：

```yaml
m_payload:
  status: enabled
  source:
    kind: local_files
    paths:
      - /absolute/work/<case>/sources/payload-source.c
  configuration:
    values:
      BOARD: evkmimx8dxl
    files:
      - /absolute/work/<case>/sources/config.h
  toolchains:
    - executable: /absolute/toolchain/bin/arm-none-eabi-gcc
      version_args: [--version]
  outputs:
    - /absolute/work/<case>/artifacts/m4/payload.bin
```

`flashbin` 使用 build/package 相同字段，`outputs` 指向最终 `flash.bin`；
toolchain 可以为空，source 应指向当前 case 的 mkimage checkout。

## Generated State

工具生成：

```text
work/<case>/state/software-state.yaml
```

它记录：

- case、identity、manifest/profile hash
- 每个成功组件的源码、配置和工具链指纹
- 输出文件 SHA-256 与缓存 stat
- 成功 unit 的原始命令 hash
- flashbin 成功消费的固定输入与启用依赖集合
- state 自身的 integrity hash

state 采用临时文件、`fsync` 和 `os.replace` 原子更新。
手改、截断或 schema 不合法会导致 `BLOCKED`。

新产物完整计算 SHA-256；后续 size、inode、mtime_ns、ctime_ns 不变时复用缓存，
元数据变化时重新计算并比较内容。
