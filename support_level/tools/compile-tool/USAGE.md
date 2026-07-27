# compile-tool

- 程序入口：`./compile-tool`
- 工具角色：编译身份门禁、flashbin 软件状态评估、原始命令展示和绑定执行
- manifest / state schema：`SOFTWARE_STATE_SCHEMA.md`
- compile request schema：`REQUEST_SCHEMA.md`

## 使用边界

本工具不解析 Makefile，不生成 recipe，也不替代：

- `compile`
- `compile_targets/<target>/README.md`
- 源码项目或工作区的 `USAGE.md`

首版只有 `flashbin` 启用软件状态与最小重编强制约束。
其他 compile target 仍使用 schema v1 的身份和原始命令门禁，
输出会明确标记“尚未启用最小重编约束”。

工具不会从主机层阻止故意调用裸 `make`、`cmake`、`ninja` 或 `bitbake`。

## flashbin 标准流程

当前 case 固定使用：

```text
records/compile-manifest.yaml
records/compile-request.yaml
state/software-state.yaml
```

`compile-manifest.yaml` 是声明文件，由当前任务准备；
`software-state.yaml` 只能由工具生成和更新，不应手改。

先评估：

```bash
../support_level/tools/compile-tool/compile-tool assess \
  ../support_level/work/<case>/records/compile-manifest.yaml
```

如果结果是 `ACQUIRE_REQUIRED`，输出会完整显示本地源码准备命令和
acquisition plan hash。使用同一 hash 执行：

```bash
../support_level/tools/compile-tool/compile-tool acquire \
  ../support_level/work/<case>/records/compile-manifest.yaml \
  --plan-hash sha256:<digest>
```

重新 `assess` 后：

- `REUSE_ONLY`：已有产物可信，不生成编译请求
- `READY`：按输出的 `REBUILD / REPACK` 精确生成 schema v2 请求
- `BLOCKED`：先解决身份、路径、来源、状态或固定输入问题

对 `READY` 请求继续执行：

```bash
../support_level/tools/compile-tool/compile-tool prepare \
  ../support_level/work/<case>/records/compile-request.yaml

../support_level/tools/compile-tool/compile-tool run \
  ../support_level/work/<case>/records/compile-request.yaml \
  --plan-hash sha256:<digest>
```

`prepare` 必须在 commentary 中完整展示身份、assessment hash、最小动作集合、
工作目录、环境变量和原始 shell 命令。

## 强制行为

- flashbin manifest 必须覆盖 dependency profile 中的全部候选组件
- 未使用组件必须是 `not_applicable + reason`
- 所有编译 cwd 必须在当前 case 下，canonical `code_assets` 只作只读基线
- 请求中的 component unit 必须与 assessment 的最小动作集合完全一致
- `prepare` 和 `run` 都重新评估；状态变化后旧 hash 失效
- 每个 unit 成功后立即验证产物并原子记录状态
- 后续 unit 失败，不撤销之前已经验证成功的组件状态
- case 级文件锁阻止两个 compile-tool 流程并发修改同一状态

源码解析顺序：

1. 可信的当前 case checkout
2. canonical repo 中已有的本地 ref
3. hash 绑定的 `git pull --ff-only` 或定向 `git fetch`
4. 缺失的外部源码或 release 包返回 `BLOCKED`，不自动下载

源码树只读取 Git commit、tracked diff 和非 ignored 新文件；
不会递归哈希未修改的 tracked 文件。

## 退出状态

- `0`：评估可继续、无需编译，或命令执行成功
- `2`：schema、身份、路径、状态、hash 或最小动作集合不合法
- `3`：`assess` 发现必须先执行 `acquire`
- 其它非零值：源码准备或实际编译命令的退出码
