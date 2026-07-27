# Compile Request Schema

`compile-tool` 支持两种请求：

- schema v1：非 flashbin target 的身份与原始命令门禁
- schema v2：flashbin assessment 绑定、最小 component unit 和原始命令门禁

flashbin 不接受 schema v1。

## Schema v2

```yaml
schema_version: 2
case: 2026-xx-xx-imx8dxl-example

identity:
  soc: i.MX8DXL
  silicon_revision: B0
  chip_package: N/A
  board: imx8dxlevk
  ddr: LPDDR4
  software_release: lf-6.18.2-1.0.0

identity_notes:
  chip_package: 当前 recipe 不按封装选择输入

identity_effects:
  soc: SOC=iMX8DXL
  silicon_revision: REV=B0
  chip_package: 当前 recipe 无封装参数
  board: 使用 imx8dxlevk 配置
  ddr: 使用 LPDDR4 固件输入
  software_release: 使用对应 LF 软件线

assessment:
  manifest: /absolute/case/records/compile-manifest.yaml
  hash: sha256:<assess-output>

compile:
  target: flashbin
  units:
    - component: smfw
      action: rebuild
      steps:
        - name: build-smfw
          cwd: /absolute/case/build/imx-sm
          env:
            CROSS_COMPILE: /absolute/toolchain/bin/arm-none-eabi-
          command: make <original-arguments>
    - component: flashbin
      action: repack
      steps:
        - name: pack-flash-bin
          cwd: /absolute/case/build/imx-mkimage
          env: {}
          command: make SOC=iMX8DXL REV=B0 flash_linux_m4
```

每个 unit：

- `component` 必须来自当前 assessment
- `action` 只能是 `rebuild` 或 `repack`
- 同一个 component 只能出现一次
- unit 顺序和集合必须与 assessment 完全一致
- unit 可以包含多条 step；全部成功后才记录该 component

每条 step：

- `name`：非空人读名称
- `cwd`：当前 case 内存在的绝对目录
- `env`：可选标量环境变量
- `command`：由 `/bin/bash -lc` 原样执行的非空命令

## Schema v1

schema v1 保留原有 `compile.target + compile.steps` 结构。
身份字段、`N/A + identity_notes`、identity effects、绝对 cwd、环境变量和
plan hash 规则不变。

schema v1 的输出会明确提示当前 target 尚未启用最小重编约束。
