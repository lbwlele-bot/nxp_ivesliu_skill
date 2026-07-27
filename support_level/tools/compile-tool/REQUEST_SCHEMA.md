# Compile Request Schema

`compile-tool` 使用一份显式 YAML 请求描述本次编译身份和原始命令。
首版 schema 固定为 `1`。

```yaml
schema_version: 1
case: 2026-xx-xx-imx95-example

identity:
  soc: i.MX95
  silicon_revision: B0
  chip_package: 19x19
  board: imx95evk19
  ddr: LPDDR5
  software_release: RTE-3.3

identity_notes: {}

identity_effects:
  soc: SOC=iMX95
  silicon_revision: REV=B0
  chip_package: 使用 mx95lp5 输入目录
  board: 使用 i.MX95 19x19 EVK 对应配置
  ddr: LPDDR_TYPE=lpddr5
  software_release: 使用 RTE 3.3 对齐的源码和固件输入

compile:
  target: flashbin
  steps:
    - name: pack-flash-bin
      cwd: /absolute/path/to/imx-mkimage
      env:
        CROSS_COMPILE: /absolute/path/to/aarch64-none-linux-gnu-
      command: make SOC=iMX95 REV=B0 OEI=YES LPDDR_TYPE=lpddr5 flash_all
```

## 身份字段

以下字段始终必须显式出现：

- `soc`
- `silicon_revision`
- `chip_package`
- `board`
- `ddr`
- `software_release`

字段禁止为空，也不能使用 `unknown`、`TBD`、`TODO` 或 `?`。

某字段确实与本次编译无关时可以填写 `N/A`，
但必须在 `identity_notes` 中写明原因：

```yaml
identity:
  ddr: N/A

identity_notes:
  ddr: 本次只编译与 DDR 无关的主机侧辅助程序
```

`identity_effects` 必须覆盖全部身份字段。
它是给工程师审阅的显式影响说明，不是由工具解释或生成的 recipe。

## 编译步骤

`compile.steps` 至少包含一步。每一步包含：

- `name`：人读步骤名；省略时使用 `step-N`
- `cwd`：存在的绝对目录
- `env`：可选环境变量
- `command`：原始 shell 命令字符串

命令由 `/bin/bash -lc` 原样执行。
复杂流程应拆成多步，让每条原始命令都能单独显示和检查。

首版不解析命令语义，也不自动补参数。
命令、工作目录、环境变量或身份的任何变化都会改变 plan hash。
