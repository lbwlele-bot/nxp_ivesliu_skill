# NXP_v2 v3 施工手册

## 1. 施工目标

v3 不直接实现 MCP。

v3 先施工一层分布式关系元数据：

```text
RELATION.yaml
```

它和 `README.md` / `USAGE.md` 并列，放在对象所在目录下。

目标是：

- 让目录之间的稳定关系机器可读
- 减少 agent 每次重新理解目录的成本
- 避免中心 catalog 漂移
- 为未来 MCP resolver 提供可靠数据源

第一阶段只写 YAML 和必要说明。
不写 MCP server。
不接 hooks。
不做 workflow。

## 2. 施工总原则

### 2.1 贴近对象

关系文件必须跟对象放在一起。

例如 `flashbin` 的关系文件就在：

```text
support_level/compile_targets/flashbin/RELATION.yaml
```

不要把它挪到中心 catalog。

### 2.2 小而确定

只写稳定关系。

可以写：

```yaml
relations:
  software_stacks:
    - rte
```

不要写：

```yaml
maybe_related:
  - 某次 case 好像用过
```

不稳定的信息继续留在 README / USAGE 或 case 记录里。

### 2.3 不复制长文档

`RELATION.yaml` 不复制 README / USAGE 内容。

它只写：

- id
- type
- owner
- human_doc
- relations
- case_required_for
- warnings
- evidence

### 2.4 可渐进

不要求一次性覆盖全系统。

优先覆盖：

- 高频入口
- 容易误判的对象
- 关系已经清楚的对象

## 3. 目录和命名

### 3.1 单对象目录

单对象目录新增：

```text
RELATION.yaml
```

例子：

```text
support_level/compile_targets/flashbin/
  README.md
  RELATION.yaml

support_level/code_assets/projects/imx-sm/
  USAGE.md
  RELATION.yaml

support_level/release_packages/scfw/
  README.md
  RELATION.yaml
```

### 3.2 多对象目录

多对象目录新增：

```text
<id>.RELATION.yaml
```

例子：

```text
support_level/software_stacks/
  README.md
  rte.md
  rte.RELATION.yaml
```

### 3.3 暂不建目录

第一阶段不新增：

```text
workspace/.agents/mcp/
workspace/tools/validators/
```

等关系层稳定后再讨论。

## 4. schema 第一版

每个关系文件使用同一套最小结构。

```yaml
schema_version: 1
id: <stable-id>
type: <object-type>
human_doc: <README.md-or-USAGE.md>
owner: <owner>

summary: <one-line-summary>

relations:
  projects: []
  compile_targets: []
  software_stacks: []
  release_packages: []
  boards: []
  tools: []

case_required_for: []

warnings: []

evidence:
  - <human_doc>
```

### 4.1 字段要求

- `schema_version`
  必须是 `1`
- `id`
  必须稳定且全局唯一，优先等于目录名或对象名；
  如果同一个名字在不同类型里重复，给 `id` 加角色后缀
- `type`
  必须来自枚举
- `human_doc`
  必须指向同目录或同级人读文档
- `owner`
  必须是当前四个主 owner 之一
- `summary`
  一句话，不写段落
- `relations`
  只写稳定关系
- `case_required_for`
  只写必须进入 case 的动作类型
- `warnings`
  只写稳定误判提醒
- `evidence`
  至少包含 `human_doc`

### 4.2 type 枚举

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

### 4.3 owner 枚举

```yaml
owner:
  - understanding
  - support
  - compile
  - board-exec
```

## 5. 第一批施工范围

第一批建议覆盖 18 个对象。

### 5.1 compile_targets

```text
support_level/compile_targets/flashbin/RELATION.yaml
support_level/compile_targets/linux/RELATION.yaml
support_level/compile_targets/m_freertos_sdk/RELATION.yaml
```

### 5.2 software_stacks

```text
support_level/software_stacks/rte.RELATION.yaml
```

### 5.3 code_assets/projects

```text
support_level/code_assets/projects/imx-mkimage/RELATION.yaml
support_level/code_assets/projects/imx-atf/RELATION.yaml
support_level/code_assets/projects/imx-sm/RELATION.yaml
support_level/code_assets/projects/imx-optee-os/RELATION.yaml
support_level/code_assets/projects/imx-oei/RELATION.yaml
support_level/code_assets/projects/uboot-imx/RELATION.yaml
support_level/code_assets/projects/real-time-edge-uboot/RELATION.yaml
support_level/code_assets/projects/linux-imx/RELATION.yaml
support_level/code_assets/projects/real-time-edge-linux/RELATION.yaml
support_level/code_assets/projects/meta-real-time-edge/RELATION.yaml
support_level/code_assets/projects/mcuxsdk-core/RELATION.yaml
support_level/code_assets/projects/mcuxsdk-manifests/RELATION.yaml
```

### 5.4 release_packages

```text
support_level/release_packages/m_freertos_sdk/RELATION.yaml
support_level/release_packages/scfw/RELATION.yaml
```

这些对象覆盖后，最常见工作路径已经能被机器读到：

- `flash.bin`
- RTE
- Linux
- M 核 SDK
- SCFW
- U-Boot 来源候选
- shared baseline vs case 边界

## 6. 编写顺序

不要按目录树从上到下机械写。

建议按工作流价值写：

1. `flashbin`
2. `rte`
3. `imx-mkimage`
4. `imx-sm`
5. `imx-atf`
6. `uboot-imx`
7. `real-time-edge-uboot`
8. `imx-optee-os`
9. `imx-oei`
10. `linux`
11. `linux-imx`
12. `real-time-edge-linux`
13. `meta-real-time-edge`
14. `m_freertos_sdk` compile target
15. `m_freertos_sdk` release package
16. `scfw`
17. `mcuxsdk-core`
18. `mcuxsdk-manifests`

理由：

- 先打通 `flashbin + RTE`
- 再补启动固件链
- 再补 Linux 和 M 核 SDK

## 7. 模板

新建关系文件时使用这个模板：

```yaml
schema_version: 1
id:
type:
human_doc:
owner:

summary:

relations:
  projects: []
  compile_targets: []
  software_stacks: []
  release_packages: []
  boards: []
  tools: []

case_required_for: []

warnings: []

evidence:
  - <human_doc>
```

写完后必须把空值清掉。
不允许提交空 `id`、空 `type` 或空 `human_doc`。

## 8. 示例写法

### 8.1 flashbin

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
  boards: []
  tools: []

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

### 8.2 imx-sm

```yaml
schema_version: 1
id: imx-sm
type: git_project
human_doc: USAGE.md
owner: compile

summary: System Manager firmware 源码项目，常作为 flash.bin 输入之一。

relations:
  projects: []
  compile_targets:
    - flashbin
  software_stacks:
    - rte
  release_packages: []
  boards: []
  tools: []

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

### 8.3 rte

```yaml
schema_version: 1
id: rte
type: software_stack
human_doc: rte.md
owner: compile

summary: Real-Time Edge 软件线，影响 LF/BSP 家族、源码 ref、release 包和 flash.bin 输入集合。

relations:
  projects:
    - imx-atf
    - imx-optee-os
    - imx-sm
    - uboot-imx
    - real-time-edge-uboot
    - linux-imx
    - real-time-edge-linux
    - meta-real-time-edge
  compile_targets:
    - flashbin
    - linux
  software_stacks: []
  release_packages:
    - m_freertos_sdk_package
    - scfw
  boards: []
  tools: []

case_required_for: []

warnings:
  - RTE version must be confirmed before selecting refs.
  - RTE name alone does not determine flash_a55 or flash_all.
  - U-Boot source must be checked against the target RTE version.

evidence:
  - rte.md
```

## 9. 校验规则

第一阶段可以先人工检查。
但写关系文件时要按未来机器校验标准执行。

每个 `RELATION.yaml` 必须满足：

- YAML 可解析
- `schema_version: 1`
- `id` 非空
- `type` 在枚举内
- `human_doc` 存在
- `owner` 在枚举内
- `evidence` 至少包含 `human_doc`
- `warnings` 不写临时 case 结论
- `relations` 不引用明显不存在的对象

如果不确定关系是否稳定，先不写。

## 10. 与未来 MCP 的关系

未来 MCP resolver 如果要做，只应该读取这些分布式关系文件。

未来 MCP 的工作方式应该是：

```text
递归扫描 RELATION.yaml
校验 schema
校验 human_doc
建立关系图
根据 query 返回候选入口、证据路径、warning 和 unknown
```

它不应该维护另一套中心 catalog。

也就是说：

```text
RELATION.yaml 是数据源
MCP 是读取器
```

## 11. 与 agent 的当前关系

在 MCP 出现之前，agent 也可以直接用这些文件。

例如用户说：

```text
我要重编 i.MX95 RTE 3.3 flash.bin
```

agent 可以读：

```text
support_level/compile_targets/flashbin/RELATION.yaml
support_level/software_stacks/rte.RELATION.yaml
```

然后知道：

- 先走 `compile`
- 必读 `flashbin/README.md`
- 必读 `software_stacks/rte.md`
- 相关项目包括 `imx-mkimage`、`imx-sm`、`imx-atf` 等
- 不能从 RTE 名称直接推出 `flash_a55` / `flash_all`

但最终技术判断仍然要回到 README / USAGE / skill。

## 12. 推荐 commit 切分

真正开工时建议分批提交：

1. `docs: define distributed relation metadata architecture`
   更新 v3 文档。
2. `relations: add flashbin and rte metadata`
   先添加 `flashbin` 和 `rte` 两个核心关系。
3. `relations: add boot firmware project metadata`
   添加 `imx-mkimage`、`imx-sm`、`imx-atf`、`OP-TEE`、`OEI`、U-Boot。
4. `relations: add linux and m-core metadata`
   添加 Linux、RTE Linux、M 核 SDK、SCFW、MCUX 相关关系。
5. `docs: describe relation metadata usage`
   按需要轻改 `AGENTS` / `support` / `compile` 的使用说明。

每个 commit 都要能单独 review。

## 13. 验收标准

v3 第一阶段完成时，应满足：

- 第一批关系文件存在
- 每个关系文件都能被人工快速读懂
- 每个 `human_doc` 路径存在
- 每个关系文件都不复制长文档
- `flashbin` / `rte` / `imx-sm` 这类高频对象能通过关系文件看出连接
- README / USAGE 仍然是人读权威文档
- 没有 MCP server、hooks、workflow 额外复杂度

## 14. v3 结论

v3 先不追求“工具化”。

v3 先追求：

```text
把稳定关系写到对象旁边。
```

这个关系层建好以后，后续无论是 agent 直接读，还是 MCP 统一读取，
都会比中心 catalog 更稳。
