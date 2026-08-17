# Compile Software State Schema

## Parameters And Guards

manifest 不要求全局芯片身份。只声明本次需要记录或被规则约束的参数：

```yaml
parameters:
  silicon_revision:
    value: B0
    source: user
  software_release:
    value: lf-6.18.2-1.0.0
    source: project
```

参数 `source` 支持：

- `user`：用户明确给出；`must_ask_user` 规则只接受此值
- `assumption`：AI/工程判断的待验证假设
- `project`：来自项目、发布包或源码规则
- `default`：显式采用上游默认值

没有规则的参数可以省略，也允许 assumption/default。

机器规则统一维护在 compile target、源码项目或 workspace 旁边的
`COMPILE_POLICY.yaml`。规则按 `target + component` 命中，规定：

- 哪个参数必须向用户询问
- 哪类原始命令必须显式绑定它
- 接受哪些命令变量名
- 哪个 managed Git component 必须在工具自有副本中隔离执行

当前规则：

- `flashbin/oei`：`silicon_revision` 必须来自用户，OEI make 命令必须显式传 `REV/R/r`
- `flashbin/flashbin`：`silicon_revision` 必须来自用户，mkimage make 命令必须显式传 `REV`
- `flashbin/smfw`：`smfw_config` 指定生成目录，重编必须执行受控刷新序列
- `flashbin/flashbin`：managed Git imx-mkimage 使用 `isolated_git`，不能直接
  在源码 worktree 中暂存输入或生成 container
- `flashbin/atf`：managed Git ATF 使用 `isolated_git`，其 `build/` 只生成在
  工具自有执行副本中

规则参数会进入对应 component 的配置指纹。revision 变化只使 OEI/mkimage
失效，不使没有该规则的 ATF、U-Boot、Linux 等 component 失效。

准备 manifest 后，可以先执行：

```bash
compile-tool requirements <manifest>
```

该命令只列出命中的 component 参数模板，不要求参数实例已经完整填写。
工具只加载当前 target 旁边的 policy，以及与当前 component 同名的
project/workspace policy；无关 policy 不参与本次校验。

## Generic Manifest V2

通用 target 的 manifest 固定放在：

```text
work/<case>/records/compile/<target>/manifest.yaml
```

最小结构：

```yaml
schema_version: 2
case: <case-directory-name>
case_root: /absolute/path/to/work/<case>
target: <arbitrary-target>
parameters: {}

sources:
  source-tree:
    kind: managed_git
    canonical_path: /absolute/support_level/code_assets/projects/<project>/<repo>
    case_path: /absolute/work/<case>/sources/<repo>
    ref_kind: tag
    ref: <exact-ref>
    remote: origin
    remote_url: <expected-url>
    update: if_missing

components:
  dtb:
    sources: [source-tree]
    configuration:
      values:
        ARCH: arm64
        DTB: <requested-dtb>
      files:
        - /absolute/work/<case>/build/linux/.config
    tools:
      - name: compiler
        executable: /absolute/toolchain/bin/aarch64-linux-gnu-gcc
        version_args: [--version]
    watched_inputs: []
    outputs:
      - /absolute/work/<case>/build/linux/arch/arm64/boot/dts/<requested>.dtb
    depends_on: []
```

`components` 是状态与执行边界，不表示工具理解内部构建系统：

- 只声明本 case 真正需要的 component
- `depends_on` 只传播明确写出的依赖
- 配置、watched inputs 和 outputs 必须位于 case
- outputs 使用非空普通文件
- 每个 component 至少声明一个具名工具及只读版本命令

来源支持：

- `managed_git`：单仓 detached worktree
- `managed_git_set`：manifest 明确列出的多个仓
- `release_archive`：本地 tar/zip 安全解包
- `local_files`：case 内已有普通文件

非 Git 目录只递归采集 component 显式声明的 `watched_inputs`。

## Flashbin Manifest V1

flashbin 深度模式继续使用：

```text
work/<case>/records/compile-manifest.yaml
```

根结构：

```yaml
schema_version: 1
case: <case>
case_root: /absolute/work/<case>
target: flashbin
parameters:
  silicon_revision:
    value: B0
    source: user
  smfw_config:
    value: other/mx95rte
    source: project
components: {}
```

manifest 必须逐项声明：

```text
atf smfw uboot optee oei m_payload firmware scfw ahab flashbin
```

未使用项必须填写 `not_applicable + reason`。固定依赖图以
`compile_targets/flashbin/DEPENDENCIES.yaml` 为权威。

## Generated State

所有 target 共用：

```text
work/<case>/state/software-state.yaml
```

```yaml
schema_version: 2
generated_by: compile-tool 3.4
case: <case>
targets:
  flashbin: {}
  linux: {}
integrity_hash: sha256:<digest>
```

每个 target 记录 manifest/profile、component 源码、配置、工具、输入快照、
输出 SHA-256 和缓存 stat。命令 hash 不记录，也不参与依赖身份。
有效旧 state v1 会迁移到 `targets.flashbin`。

命中 `isolated_git` 的 component 还记录执行模式、契约版本、policy 来源和
隔离工作区身份。旧成功记录缺少该契约时会触发一次重建；执行副本中的临时
文件和生成物不进入源码指纹，也不写入软件状态。

flashbin package 额外记录 `input_artifacts`，逐个保存启用上游组件输入文件
的 SHA-256，并记录最终 `flash.bin` 输出 SHA-256。这些 hash 用于后续核对，
不声称证明 shell recipe 实际消费了哪个路径。

每个成功 component 立即通过临时文件、`fsync` 和 `os.replace` 原子记录；
手改、截断或 integrity 不合法会导致 `BLOCKED`。
