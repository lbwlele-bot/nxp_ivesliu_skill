# Compile Request Schema

`compile-tool` 支持两种请求：

- schema v2：绑定 manifest、assessment、component unit 和原始命令
- schema v1：只校验并执行显式参数和原始命令，不维护软件状态

flashbin 不接受 schema v1。

## Schema v2

```yaml
schema_version: 2
case: 2026-xx-xx-imx93-example

assessment:
  manifest: /absolute/case/records/compile/linux/manifest.yaml
  hash: sha256:<assess-output>

decision:
  scope: [dtb]
  reason: 本轮只修改了目标板设备树
  destructive: {}

compile:
  target: linux
  units:
    - component: dtb
      action: rebuild
      steps:
        - name: build-dtb
          cwd: /absolute/case/build/linux
          env:
            ARCH: arm64
            CROSS_COMPILE: /absolute/toolchain/bin/aarch64-linux-gnu-
          command: make -C /absolute/case/sources/linux O=/absolute/case/build/linux imx93-11x11-evk.dtb
```

参数在 manifest 中声明，request 不重复维护。

`decision.scope` 是 LLM 判断的直接变更组件，不是 `assess` 推导的结果。
`reason` 必须说明本轮为什么执行这些组件。`destructive` 默认是空 mapping。

每个 unit：

- `component` 必须来自 manifest 中的启用组件
- 通用状态单元的 `action` 只能是 `rebuild`
- flashbin build component 使用 `rebuild`，package 使用 `repack`
- 同一个 component 只能出现一次
- unit 必须位于 scope 或其显式下游，且按 manifest 拓扑顺序排列
- scope 中可执行的 component 不能遗漏
- flashbin 上游 scope 必须包含最终 `flashbin repack`
- fixed input 可进入 scope，但不能成为可执行 unit
- unit 可以包含多条 step；全部成功且产物有效后才记录 component

每条 step：

- `name`：非空人读名称
- `cwd`：当前 case 内的绝对目录。普通 component 在读取 request 时必须已
  存在；`isolated_git` component 可以指向尚未物化的固定隔离目录
- `env`：可选标量环境变量
- `command`：由 `/bin/bash -lc` 原样执行的非空命令

managed Git component 的 cwd 还受执行边界约束：

- 未命中隔离 policy 时，cwd 不得位于任何 managed Git case source 内；
- 命中 `isolated_git` 时，该 component 的每个 step cwd 都必须位于
  `build/.compile-tool/<target>/<component>/source/` 内；
- `run` 在执行 component 前物化隔离源码，并再次确认各 cwd 已存在。

`assess` 的 `observed_units` 只提供状态证据，不限制 LLM：

- 可以只执行其中一部分
- 状态 `MATCHED` 时也可以基于明确理由重编
- 不能借此把 scope 之外的平级组件加入请求

普通组件包含 `make clean/distclean/mrproper/really-clean` 或递归强制
`rm` 时，必须声明：

```yaml
decision:
  destructive:
    uboot: 切换 defconfig，当前输出目录不能复用
```

命中 `COMPILE_POLICY.yaml` 的 unit 还必须满足对应命令绑定。
当前 OEI 和 mkimage 的 `make` 命令必须显式包含与 manifest 相同的
`REV=<silicon_revision>`；不能依赖 Makefile 默认值。

SMFW rebuild 还必须使用 manifest 的 `smfw_config`，按顺序执行：

```bash
rm -rf configs/<smfw_config>
make really-clean
make config=<smfw_config> cfg
make config=<smfw_config> all
```

删除 `.cfg` 源文件、整个 `configs/`、使用不同 config 或打乱顺序都会阻断。

`prepare` 和 `run` 都重新读取 request、manifest 并快速 assessment。
源码、配置、工具、watched inputs、受约束参数、依赖或产物变化后，
旧 assessment hash 失效。

`run` 不使用 prepare/run plan hash：

```bash
compile-tool prepare <request>
compile-tool run <request>
```

## Schema v1

```yaml
schema_version: 1
case: <case>
parameters: {}
compile:
  target: <target>
  steps:
    - name: <step>
      cwd: <absolute-existing-directory>
      env: {}
      command: <raw-command>
```

schema v1 不读取 manifest，不应用 component 参数规则，也不更新
`software-state.yaml`。它不要求全局 SoC、revision、封装、板型、DDR
或软件版本。
