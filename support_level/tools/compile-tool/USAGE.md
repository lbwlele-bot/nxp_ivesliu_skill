# compile-tool

- 程序入口：`./compile-tool`
- 工具角色：component 参数守门、软件状态观察、执行范围限制和状态记录
- 参数规则：compile target / project / workspace 旁边的 `COMPILE_POLICY.yaml`
- manifest / state schema：`SOFTWARE_STATE_SCHEMA.md`
- request schema：`REQUEST_SCHEMA.md`
- 项目单清单入口：`MINIMAL_CHECKLIST_DESIGN.md`
- 内部 profile / artifact schema：`PROJECT_PROFILE_SCHEMA.md`

## 使用边界

本工具通常不解析 Makefile、Kbuild 或 west manifest，也不生成 recipe。唯一
例外是 imx-mkimage：工具只读取选定 ref 的 `soc.mak` target 依赖来识别 M
payload 文件名，不执行 Make recipe。具体编译方法仍由 compile target、项目
`USAGE.md` 和工程判断负责。

它不要求所有编译都填写 SoC、silicon revision、封装、板型、DDR 和软件版本。
普通参数可以省略，也可以明确标成 assumption/default。只有
`COMPILE_POLICY.yaml` 命中的已知风险参数会成为阻断规则。

当前已知规则：

- 编译 OEI 时，silicon revision 必须询问用户，不能猜或使用默认值
- 使用 imx-mkimage 打包 flashbin 时同样如此
- 两类 make 命令都必须显式包含相同的 `REV=<value>`
- SMFW 重编必须删除 `make cfg` 的生成目录，再执行
  `really-clean -> cfg -> all`

是否重编由 LLM 根据任务目标、代码改动和工程判断决定。`assess` 只提供
状态证据；工具不会把观察到的差异自动变成必须执行的命令。

工具不会从主机层阻止故意调用裸 `make`、`cmake`、`ninja`、`bitbake`
或 `west`。

## 标准流程

已经带 `COMPILE_CHECKLIST.yaml` 的项目统一使用单清单入口。当前包括：

- `imx-oei`
- `imx-atf`
- `uboot-imx`
- `real-time-edge-uboot`
- `imx-optee-os`
- `imx-sm`
- `imx-mkimage`
- `m_freertos_sdk`（compile target，多 job producer）

先把项目旁 `COMPILE_CHECKLIST.yaml` 复制到：

```text
work/<case>/records/compile/<project>/compile.yaml
```

填写清单后只提交这一份：

```bash
compile-tool prepare work/<case>/records/compile/<project>/compile.yaml
compile-tool run work/<case>/records/compile/<project>/compile.yaml
```

AI 只填写模板允许的参数、输入选择和 intent；原始命令由项目
`COMPILE_PROFILE.yaml` 的受控 token 模板生成。`prepare` 内部完成
requirements、source plan、assess、命令门禁和完整 cwd/env/原始命令展示；
`run` 必须消费未变的同一清单和 prepare 记录。内部 manifest/request
由工具生成，AI 不维护。任何已经提供项目清单的 target，直接提交其
manifest/request 执行都会被阻断。

M SDK 使用专用公开清单
`records/compile/m_freertos_sdk/compile.yaml`。清单可以声明多个独立 job，
工具按本轮实际 SDK 版本自动选择 legacy 或 West backend，源码构建固定发布同源
ELF+BIN，预编译只允许执行校验、复制和发布。AI 同样不能填写 backend、命令、
输出路径或内部 manifest/request。

SDK 发布包需要登录 NXP 获取，compile-tool 不自动下载。本地缺少清单选择的包
时，`prepare` 返回 `USER_INPUT_REQUIRED`，AI 必须找用户要对应包；用户下载后
可把包放入当前 case 并在清单填写 `archive/sdk_release/trust_reason`。工具只对
本轮选中的包计算和比较 SHA-256，状态摘要仍由一次 `prepare` 自动完成。

`imx-mkimage` 从选定源码 ref 的 `<SOC>/soc.mak` 提取 recipe 的 M payload
文件名，再按 producer identity 检查类型、SoC、core role 和隔离源码内落位；
`compile_targets/flashbin/RECIPE_CONTRACTS.yaml` 不再复制 M 镜像列表。当前完整
非 M producer/fixed-input 合同先覆盖
`iMX94/iMX95` 的 `flash_a55` 与 `flash_all`；其它 recipe 不会被静默放行。
固定 AHAB/DDR firmware 同时绑定
`compile_targets/flashbin/FIXED_ASSETS.yaml`；工具校验 role、目标文件名和
SHA-256，不允许只靠文件名把相近版本混入当前 case。
含 M payload 的 recipe 只接受 M producer 导出的 `nxp.mcore.bin`；工具同时
验证 producer 成功状态、当前文件哈希、SoC 与 core role。裸 M 文件输入和
`nxp.mcore.elf` 都不能进入 flash.bin。

通用 target：

```text
records/compile/<target>/manifest.yaml
records/compile/<target>/request.yaml
state/software-state.yaml
```

flashbin 深度模式：

```text
records/compile-manifest.yaml
records/compile-request.yaml
state/software-state.yaml
```

先评估：

```bash
compile-tool requirements <manifest>
compile-tool assess <manifest>
```

如果是 `ACQUIRE_REQUIRED`，使用 assess 显示的 acquisition hash：

```bash
compile-tool acquire <manifest> --plan-hash sha256:<digest>
```

重新 assess 后，`READY` 会同时显示：

- `MATCHED`：当前记录和现场状态一致
- `CHANGES_OBSERVED`：观察到源码、配置、工具、输入或产物差异

LLM 再决定复用还是生成 schema v2 request，并在 `decision.scope/reason`
中声明本轮直接变更范围和理由。观察结果不是强制动作集合。

执行：

```bash
compile-tool prepare <request>
compile-tool run <request>
```

`prepare` 完整显示显式参数、状态摘要、LLM 决策范围、cwd、环境变量和
原始 shell 命令；`run` 重新读取并校验当前 request 后直接执行。

## Linux 长构建日志

仅当 schema v2 manifest 的 `target: linux` 时，`run` 使用长构建输出策略。
这个判断不依赖命令文本里是否出现 `make` 或 `kernel`：

- 编译进程的 stdout/stderr 完整写入
  `work/<case>/logs/compile/linux/build-<time>-<pid>.log`
- 正常编译行不流式回传给 AI
- 工具以 shell 进程退出和退出码判定结束，不把“日志暂停增长”
  误判为编译完成
- 成功时只回传耗时和完整日志路径
- 失败时回传退出码、第一个可识别错误、最后 30 行和完整日志路径

`zephyr`、`a55_rtos`、flashbin 和项目公共清单不使用该策略，
保持原有输出行为。日志静默只能作为可能卡住的辅助信号，
不是成功或失败证据。

assessment hash、source acquisition hash 和 state integrity hash 继续保留，
因为它们分别用于状态过期、源码准备计划和状态损坏检测，不用于绑定
prepare/run 命令文本。

跨项目 artifact 引用也进入 assessment hash。producer manifest、成功状态、
artifact 内容或匹配身份变化后，consumer 的旧 assessment 会失效。

## 源码与构建执行边界

managed Git 的 `sources/<repo>` 只承载源码身份：HEAD、tracked diff 和
非 ignored 的 untracked 文件。构建生成物不能靠 `.gitignore`、manifest
排除列表或其它白名单从源码指纹中隐藏。

执行分为两种硬边界：

- out-of-tree：step cwd 必须位于 managed Git 源码树之外；构建前后仍严格
  比较原始源码指纹。
- `isolated_git`：由 `COMPILE_POLICY.yaml` 对已知 in-tree component 强制；
  `run` 将当前 commit、tracked patch、untracked 文件和符号链接精确物化到
  `build/.compile-tool/<target>/<component>/source/`，全部 step cwd 必须位于
  该副本内。

隔离副本是 compile-tool 自有的可重建执行现场。构建失败时保留现场但不写
成功状态；下一次执行前重新物化。即使使用隔离副本，命令若越界修改原始
`sources/<repo>`，构建后源码一致性检查仍会阻断。

没有 `isolated_git` policy 的 managed Git component 若直接把源码目录作为
cwd，`prepare` 和 `run` 都会阻断；项目应改为真正的 out-of-tree 构建，或在
对应长期 policy 中声明隔离执行，不能添加生成路径排除规则。

通用 schema v2 component 还支持受控 `operation: import`。该操作只允许由
公开清单生成，step 必须与 manifest 的 `import_contract` 一一对应，且只能是
`/usr/bin/install -D -m 0644 <case-source> <declared-output>`；不能夹带 shell
命令、环境变量或 case 外路径。

## 决策范围和 destructive 操作

schema v2 请求必须包含：

```yaml
decision:
  scope: [smfw]
  reason: 修改了 SMFW 配置
  destructive: {}
```

工具只允许执行 scope 中的组件及 manifest 明确声明的下游组件。
flashbin 的上游组件进入 scope 后必须包含最终 `flashbin repack`，无关的
ATF、U-Boot 等平级组件不能顺带加入。

普通组件使用 `make clean/distclean/mrproper/really-clean` 或递归强制
`rm` 时，必须在 `decision.destructive.<component>` 写明理由。工具只要求
显式化，不判断工程理由是否正确。SMFW policy 自带的精确刷新序列不需要
重复填写 destructive 理由。

## 参数规则

`COMPILE_POLICY.yaml` 是长期模板，说明某个 target/component 有哪些
危险参数必须被显式处理。manifest 是当前 case 的实例，只填写本次实际值
和信息来源。

LLM 不需要记忆每个 component 的参数列表。准备真实编译前先执行：

```bash
compile-tool requirements <manifest>
```

该命令会按 manifest 中的 target 和 component 集合加载所有命中的
`COMPILE_POLICY.yaml`，并列出必须用户确认或必须显式传入命令的参数。
加载范围是当前 `compile_targets/<target>/COMPILE_POLICY.yaml`，以及与
component 同名的 `code_assets/projects/<component>/COMPILE_POLICY.yaml`
或 `code_assets/workspaces/<component>/COMPILE_POLICY.yaml`。

manifest 示例：

```yaml
parameters:
  silicon_revision:
    value: B0
    source: user
```

如果 flashbin manifest 缺失该参数、值为 unknown/N/A、source 不是 user，
`assess` 会返回 `BLOCKED` 并要求先询问用户。

即使参数已经声明，下面的命令仍会阻断：

```bash
make SOC=iMX95 OEI=YES flash_all
```

必须显式绑定：

```bash
make SOC=iMX95 REV=B0 OEI=YES flash_all
```

未来增加已确认的危险点时，优先在对应 compile target、源码项目或
workspace 旁边增加一条 `COMPILE_POLICY.yaml` 规则，不增加全局必填字段，
也不增加新的 Python profile。

SMFW 还需要：

```yaml
parameters:
  smfw_config:
    value: other/mx95rte
    source: project
```

它决定允许删除的唯一生成目录 `configs/<smfw_config>/`。源配置
`configs/<smfw_config>.cfg` 和整个 `configs/` 目录都禁止删除。

## 软件状态

- flashbin 使用固定依赖图的深度模式
- 其他 target 使用通用状态单元，只传播 manifest 明确声明的依赖
- canonical 源码只作来源，编译 cwd 必须位于 case
- 每个成功 component 立即原子记录
- Git 只采集 HEAD、tracked diff 和非 ignored 新文件
- 非 Git 内容只采集显式 watched inputs
- flashbin 记录各启用输入产物和最终 `flash.bin` 的 SHA-256
- 不记录命令 hash；命令文本不参与软件状态或依赖身份
- 项目级 consumer 记录跨 manifest artifact 的 producer state identity、type、
  identity、origin 和 SHA-256

## 退出状态

- `0`：状态观察完成或执行成功
- `2`：schema、参数规则、路径、状态、hash 或执行范围不合法
- `3`：必须先执行 acquire
- 其他非零值：源码准备或实际编译命令退出码
