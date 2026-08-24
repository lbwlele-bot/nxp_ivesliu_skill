# 项目级最小编译清单

## 当前状态

当前单清单 schema 已覆盖 OEI、ATF、通用/RTE U-Boot、OP-TEE、SMFW 和
imx-mkimage；M SDK 另有支持多 job 的公开单清单。每个项目/target 的模板可以
复制到 case；`*.example.yaml` 只展示填写形状，不是已验证的真实产品 case。

现有 profile、policy、manifest、assessment、request 和 state 能力作为内核；
对 AI 只暴露一张 case 编译清单：

```text
项目 COMPILE_CHECKLIST.yaml
        -> AI 复制并填写
work/<case>/records/compile/<project>/compile.yaml
        -> compile-tool prepare
        -> compile-tool run
        -> state/software-state.yaml
```

M SDK 固定使用：

```text
compile_targets/m_freertos_sdk/COMPILE_CHECKLIST.yaml
        -> records/compile/m_freertos_sdk/compile.yaml
        -> compile-tool prepare/run
```

其中每个 job 独立声明源码构建或预编译导入；backend、命令、输出路径与
内部 request 都由工具推导。

## 文件边界

- 项目 `COMPILE_CHECKLIST.yaml`：项目 owner 维护的空白表格和固定字段
- case `compile.yaml`：AI 从项目模板复制，只填当前值和本轮意图
- `software-state.yaml`：只由 compile-tool 生成，记录正规化清单、源码、工具、输入和输出身份
- 现有 `COMPILE_PROFILE.yaml` / `COMPILE_POLICY.yaml`：暂时保留为内核与兼容能力，不是 AI 每次填写的 case 清单

## 字段归属

| 字段 | 归属 | 规则 |
|---|---|---|
| `schema_version` / `kind` / `project` | 项目模板 | AI 不能改；工具按 project 找到权威模板 |
| `case_root` | AI | 必须是当前已存在 case 的绝对路径 |
| `source.ref` | AI | 必须是明确 tag、branch 或 commit，不能依赖当前 checkout |
| `parameters.*` 的键和默认值 | 项目模板 | AI 只填允许的 TBD；不允许增删键 |
| `silicon_revision` | 用户 -> AI 记录 | OEI/mkimage 都必须来自用户，不能猜测 |
| `inputs` | AI | producer 使用空列表；consumer 只选择当前 recipe 实际消费的 artifact/固定文件 |
| `toolchain` | 项目模板 | 工具验证实际路径和版本，AI 不得换成未授权工具 |
| `intent.action/reason` | AI | 记录本轮是 rebuild/repack/reuse 以及工程理由 |
| `build.mode` | 项目模板 | 当前项目清单统一使用 `isolated_git` |
| 实际 env/command | profile / compile-tool | AI 不填写；由受控 token 模板生成，prepare 完整展示 |
| `outputs` 的键、类型和路径规则 | 项目模板 | AI 不能自定义输出或把它发布到 case 外 |
| source/tool/input/output hash | compile-tool | 只由工具观察和写入 state，AI 不填 hash |
| 实际执行 `cwd` | compile-tool | 根据 case 和 `isolated_git` 生成，prepare 时完整展示 |

## OEI 最小闭环

OEI 清单只允许一个 component 和一个 `oei_ddr` 输出。工具必须验证：

- `source.ref`、revision 和 board 已填写
- profile 生成的 make 命令显式包含与清单一致的 `R=`、`REV=`、`board=` 和 `oei=`；`R` 用于 OEI Makefile 内部的 revision 派生，`REV` 同时保持对外门禁显式
- ARM compiler 与模板允许路径/版本一致
- 构建在 compile-tool 管理的隔离副本中发生
- `collect_from` 本轮确实生成，并由工具发布到 `publish_to`
- 清单和当前输出均未变化时可以 reuse

## imx-mkimage 最小闭环

mkimage 已把 OEI、ATF、U-Boot、OP-TEE 和 SMFW 当作独立 producer。工具必须验证：

- `SOC`、`REV`、`OEI`、`LPDDR_TYPE` 和 recipe 与清单一致
- 所有选中输入都存在，并由工具记录 SHA-256
- artifact 来自同 case producer 的成功状态，类型、hash 和身份匹配
- `SOC + recipe` 命中 recipe contract，必需角色、slot 和 `stage_to` 完全匹配
- `oei_enabled=YES` 时必须引用同 case 成功的 `oei_ddr`
- OEI 和 mkimage 的 silicon revision 必须一致
- `oei_enabled=NO` 时不能选择 OEI artifact
- `flash_all` 必须选择对应 SoC 的 M payload 角色；`flash_a55` 不允许混入这些角色
- 每个 M payload 必须是 M SDK producer 的 `nxp.mcore.bin`；i.MX95 固定 m7，
  i.MX94 固定 m33s/m70/m71，不能使用裸文件或 ELF
- mkimage 构建只能在 compile-tool 管理的 `isolated_git` 副本内执行
- OEI 成功状态或任一固定输入变化时，mkimage 需要 repack

## 对外 CLI

试点完成后，正常使用者只需：

```bash
compile-tool prepare work/<case>/records/compile/imx-oei/compile.yaml
compile-tool run work/<case>/records/compile/imx-oei/compile.yaml

compile-tool prepare work/<case>/records/compile/imx-mkimage/compile.yaml
compile-tool run work/<case>/records/compile/imx-mkimage/compile.yaml

compile-tool prepare work/<case>/records/compile/m_freertos_sdk/compile.yaml
compile-tool run work/<case>/records/compile/m_freertos_sdk/compile.yaml
```

`prepare` 内部执行清单校验、状态观察和计划生成，完整展示实际
cwd、env、原始命令和 rebuild/repack/reuse 结论。`run` 对同一张清单重新
校验并执行。

## 当前后续范围

- M SDK producer 已接通当前 i.MX94/i.MX95 `flash_all`；Linux remoteproc
  消费 `nxp.mcore.elf` 的上板流程尚未实现
- 已知 i.MX95 B0 和 i.MX943 A0 的 DDR/ELE/AHAB 已绑定 fixed-asset
  catalog 和 canonical hash；其他 SoC/revision/package 组合不会默认放行
- SCFW 需要按 release-package producer 单独建模
- 不做通用多项目自动编排
- 不删除旧 flashbin 深度模式和 schema v2 状态内核
- 不把清单存在或本地测试通过当成真实产品编译成功
