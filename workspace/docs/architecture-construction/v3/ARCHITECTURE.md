# NXP_v2 v3 架构手册

## 1. v3 的真实目标

v3 不直接建设 MCP server。

v3 先建设一层更小、更稳、更贴近目录的东西：

> 分布式 `RELATION.yaml` 关系层。

它的目标是让当前工作系统里一部分“软关系”先变成机器可读的显式关系。

当前系统已经有大量人读文档：

- `workspace/AGENTS.md`
- `workspace/.agents/skills/*/SKILL.md`
- `support_level/**/README.md`
- `support_level/code_assets/projects/*/USAGE.md`

这些文档适合解释：

- 为什么这样分层
- 当前目录做什么
- 什么时候该看这里
- 什么事情不能误判

但它们对机器来说仍然偏软。
agent 每次开工都要读一堆 Markdown，再靠上下文理解关系。

v3 要加的是：

```text
README / USAGE 给人读
RELATION.yaml 给机器读
未来 MCP 只是 RELATION.yaml 的读取器和聚合器
```

## 2. 为什么不先做中心 MCP catalog

前一版设想是：

```text
workspace/.agents/mcp/nxp-workspace/catalog/*.yaml
```

也就是在控制面建一组中心 catalog。

这个方案有明显风险：

- workspace 还在持续变化，中心 catalog 容易漂移
- README / USAGE 改了，catalog 可能没同步
- catalog 会变成第二套知识库
- agent 不知道该信 Markdown 还是信 catalog
- 一旦 catalog 过期，MCP 输出会显得很硬，但其实是错的

当前阶段更稳的做法是把关系放在它所属目录旁边。

也就是：

```text
support_level/compile_targets/flashbin/
  README.md
  RELATION.yaml

support_level/code_assets/projects/imx-sm/
  USAGE.md
  RELATION.yaml

support_level/software_stacks/
  rte.md
  rte.RELATION.yaml
```

这样做的好处：

- 关系文件跟人读文档同目录
- 改目录时更容易顺手改关系
- 不需要一次性建完全局 catalog
- 不需要马上实现 MCP
- 未来 MCP 可以递归收集这些关系文件
- 当前 agent 也可以直接读取这些 YAML

## 3. v3 的系统位置

`RELATION.yaml` 不是新的一层知识库。

它是现有文档旁边的机器可读索引。

目录关系变成：

```text
workspace/
  AGENTS.md
  .agents/skills/
  docs/

support_level/
  compile_targets/
    <target>/
      README.md
      RELATION.yaml
  code_assets/
    projects/
      <project>/
        USAGE.md
        RELATION.yaml
    workspaces/
      <workspace>/
        README.md
        RELATION.yaml
  software_stacks/
    <stack>.md
    <stack>.RELATION.yaml
  release_packages/
    <package>/
      README.md
      RELATION.yaml
  board_knowledge/
    <board>/
      README.md
      RELATION.yaml
      serial.yaml
```

不是所有目录第一天都必须有 `RELATION.yaml`。

v3 允许渐进增加。
先覆盖高频、容易误判、关系清楚的目录。

## 4. RELATION.yaml 的职责

每个 `RELATION.yaml` 回答机器需要知道的几个问题：

- 我是谁
- 我是什么类型
- 我的 human doc 是哪个
- 我的 owner 是谁
- 我跟哪些 compile target、project、software stack、release package、board 有关系
- 哪些动作必须进入 case
- 哪些误判必须提醒
- 我的关系来源是什么

它不负责：

- 写完整说明
- 写构建命令
- 替代 README / USAGE
- 替代 skill 判断
- 直接给最终技术答案
- 自动操作文件、源码、板子

也就是说：

```text
RELATION.yaml 是索引，不是专家。
```

## 5. 文件命名

### 5.1 单对象目录

目录本身只有一个对象时，用：

```text
RELATION.yaml
```

例如：

```text
support_level/compile_targets/flashbin/RELATION.yaml
support_level/code_assets/projects/imx-sm/RELATION.yaml
support_level/release_packages/scfw/RELATION.yaml
```

### 5.2 多对象目录

目录下有多个对象，但对象不各自独立成目录时，用：

```text
<id>.RELATION.yaml
```

例如：

```text
support_level/software_stacks/rte.md
support_level/software_stacks/rte.RELATION.yaml
```

### 5.3 暂不建议

不建议第一版使用：

```text
.relation.yaml
relation.yml
metadata.yaml
catalog.yaml
```

原因：

- `RELATION.yaml` 更醒目
- 与 `README.md` / `USAGE.md` 并列时含义清楚
- 未来递归扫描规则简单

## 6. 基础 schema

第一版 schema 应该小而稳定。

```yaml
schema_version: 1
id: flashbin
type: compile_target
human_doc: README.md
owner: compile

summary: 启动固件 / flash.bin 打包对象

relations:
  projects: []
  compile_targets: []
  software_stacks: []
  release_packages: []
  boards: []

case_required_for: []

warnings: []

evidence:
  - README.md
```

字段说明：

- `schema_version`
  关系文件格式版本
- `id`
  稳定且全局唯一的机器标识，优先使用目录名或对象名；
  如果同一个名字在不同类型里重复，给 `id` 加角色后缀
- `type`
  对象类型
- `human_doc`
  人读文档，相对当前 YAML 所在目录
- `owner`
  主 owner，通常是 `understanding`、`support`、`compile`、`board-exec`
- `summary`
  一句话说明，不复制长文档
- `relations`
  指向其他对象的关系
- `case_required_for`
  哪些动作不能在共享基线做，必须进入 case
- `warnings`
  高风险误判提醒
- `evidence`
  关系来源，通常是同目录 README / USAGE 或明确上层文档

## 7. type 枚举

第一版只需要这些：

```yaml
type:
  - skill
  - support_area
  - compile_target
  - git_project
  - workspace
  - software_stack
  - release_package
  - board_profile
  - host_tool
  - case_area
```

不要过早细分。

如果一个对象暂时无法归类，先不要建关系文件。

## 8. owner 枚举

第一版 owner 只使用当前四个主 skill：

```yaml
owner:
  - understanding
  - support
  - compile
  - board-exec
```

如果某个目录只是资源容器，owner 通常是 `support`。

如果某个目录是编译对象或源码项目，owner 通常是 `compile`。

如果某个目录涉及真实板子状态，owner 通常是 `board-exec`。

如果某个目录表达概念模型或路由语义，owner 通常是 `understanding`。

## 9. relations 模型

`relations` 只表达稳定关系。

不要写“也许”“可能”“某次 case 中曾经”。

可以写：

```yaml
relations:
  compile_targets:
    - flashbin
  software_stacks:
    - rte
```

不应该写：

```yaml
relations:
  make_targets:
    - flash_all
```

除非这个目录本身就是 make target 的 owner。

`flash_all` / `flash_a55` 是 `soc.mak` recipe，不是顶层 compile target。
这种误判应放进 `warnings`。

## 10. 示例：flashbin

文件：

```text
support_level/compile_targets/flashbin/RELATION.yaml
```

内容：

```yaml
schema_version: 1
id: flashbin
type: compile_target
human_doc: README.md
owner: compile

summary: 启动固件 / flash.bin 打包对象，负责确认 boot image 输入集合和最终打包链路。

relations:
  projects:
    - imx-mkimage
    - imx-atf
    - imx-sm
    - imx-optee-os
    - imx-oei
    - uboot-imx
    - real-time-edge-uboot
  compile_targets:
    - m_freertos_sdk_target
  software_stacks:
    - rte
  release_packages:
    - scfw

case_required_for:
  - generated_flashbin
  - patched_inputs
  - rebuilt_inputs

warnings:
  - flashbin is a compile target, not a single imx-mkimage make target.
  - flash_a55 and flash_all are soc.mak recipes, not top-level compile targets.
  - RTE name alone must not decide flash_a55 or flash_all.

evidence:
  - README.md
  - ../../software_stacks/rte.md
```

## 11. 示例：imx-sm

文件：

```text
support_level/code_assets/projects/imx-sm/RELATION.yaml
```

内容：

```yaml
schema_version: 1
id: imx-sm
type: git_project
human_doc: USAGE.md
owner: compile

summary: System Manager firmware 源码项目，常作为 flash.bin 输入之一。

relations:
  compile_targets:
    - flashbin
  software_stacks:
    - rte

case_required_for:
  - patch
  - build
  - generated_output

warnings:
  - Shared project directory is a baseline; case patch/build must happen under support_level/work/<case>/.
  - RTE-specific SMFW config and patches are software-stack constraints, not generic imx-sm rules.

evidence:
  - USAGE.md
  - ../../../software_stacks/rte.md
```

## 12. 示例：rte

文件：

```text
support_level/software_stacks/rte.RELATION.yaml
```

内容：

```yaml
schema_version: 1
id: rte
type: software_stack
human_doc: rte.md
owner: compile

summary: Real-Time Edge 软件线，影响 LF/BSP 家族、源码 ref、release 包和 flash.bin 输入集合。

relations:
  compile_targets:
    - flashbin
    - linux
  projects:
    - imx-atf
    - imx-optee-os
    - imx-sm
    - uboot-imx
    - real-time-edge-uboot
    - linux-imx
    - real-time-edge-linux
    - meta-real-time-edge
  release_packages:
    - m_freertos_sdk_package
    - scfw

case_required_for: []

warnings:
  - RTE version must be confirmed before selecting refs.
  - RTE name alone does not determine flash_a55 or flash_all.
  - U-Boot source must be checked against the target RTE version.

evidence:
  - rte.md
```

## 13. 机器如何使用这些关系

第一阶段不需要 MCP。

agent 可以直接读相关 `RELATION.yaml`。

未来 MCP 也可以按下面逻辑收集：

```text
scan support_level/**/RELATION.yaml
scan support_level/**/*.RELATION.yaml
validate schema
validate human_doc exists
validate relation target ids exist
build graph
answer relation lookup
```

但 MCP 只是读取器。
关系本身仍然分散在对象旁边。

## 14. RELATION.yaml 和 README / USAGE 的关系

### 14.1 README / USAGE 是权威解释

人要理解细节时，读 README / USAGE。

例如：

- 编译命令
- 版本注意事项
- 具体路径
- 技术边界
- 例外情况

### 14.2 RELATION.yaml 是机器索引

机器需要快速路由时，读 `RELATION.yaml`。

例如：

- 这个对象属于哪个 owner
- 这个对象和哪些 compile target 有关
- 这个对象是不是 release package
- 这个动作是否必须进入 case
- 有哪些必须提示的 warning

### 14.3 冲突时怎么办

如果 `RELATION.yaml` 和 README / USAGE 冲突：

1. 暂停使用该关系
2. 以 README / USAGE 为人工审查入口
3. 修正 `RELATION.yaml`
4. 记录这次修正来源

不允许因为 YAML 看起来更“硬”，就覆盖人读文档。

## 15. 质量原则

每个关系文件必须满足：

- `human_doc` 存在
- `id` 稳定
- `type` 在枚举内
- `owner` 在枚举内
- `relations` 只引用已知对象或明确允许的外部对象
- `warnings` 是稳定误判提醒，不写临时 case 结论
- `evidence` 至少包含同目录人读文档
- 不复制长 Markdown 内容

如果做不到，就先不要写。

## 16. 第一批覆盖范围

v3 第一批不追求全覆盖。

建议先覆盖：

### compile_targets

- `flashbin`
- `linux`
- `m_freertos_sdk`

### software_stacks

- `rte`

### code_assets/projects

- `imx-mkimage`
- `imx-atf`
- `imx-sm`
- `imx-optee-os`
- `imx-oei`
- `uboot-imx`
- `real-time-edge-uboot`
- `linux-imx`
- `real-time-edge-linux`
- `meta-real-time-edge`
- `mcuxsdk-core`
- `mcuxsdk-manifests`

### release_packages

- `m_freertos_sdk`
- `scfw`

这些覆盖后，日常 flash.bin、RTE、Linux、M 核 SDK 的入口关系会稳定很多。

## 17. 非目标

v3 第一阶段不做：

- MCP server
- hooks
- workflow
- 自动解析自然语言
- 自动创建 case
- 自动修改 README / USAGE
- 自动选择 `flash_a55` / `flash_all`
- 自动决定 RTE 版本 / ref
- 自动执行编译
- 自动操作板子

v3 只做一件事：

```text
把散在目录里的稳定关系写成贴近目录的 RELATION.yaml。
```

这个层做好以后，未来再谈 MCP 才有可靠基础。
