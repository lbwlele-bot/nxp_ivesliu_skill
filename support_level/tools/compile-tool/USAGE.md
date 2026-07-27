# compile-tool

- 程序入口：`./compile-tool`
- 工具角色：编译身份声明、原始命令展示、plan hash 绑定和顺序执行
- 请求 schema：`REQUEST_SCHEMA.md`

## 使用边界

本工具不生成编译命令，不维护项目 recipe，也不替代：

- `compile`
- `compile_targets/<target>/README.md`
- 源码项目或工作区的 `USAGE.md`

源码阅读、依赖分析和编译规划不需要调用本工具。
准备执行第一条真实编译命令时才进入本工具。

首版只提供工作区级统一入口，不修改系统权限，
也不能从主机层阻止故意直接调用裸 `make`、`cmake`、`ninja` 或 `bitbake`。

## 标准流程

在当前 case 中准备请求，推荐位置：

```text
records/compile-request.yaml
```

先校验并显示：

```bash
../support_level/tools/compile-tool/compile-tool prepare \
  ../support_level/work/<case>/records/compile-request.yaml
```

`prepare` 成功后必须先向用户完整展示输出中的：

- 编译身份
- 身份对编译的影响
- 工作目录和环境变量
- 原始编译命令
- plan hash

然后使用同一个 hash 执行：

```bash
../support_level/tools/compile-tool/compile-tool run \
  ../support_level/work/<case>/records/compile-request.yaml \
  --plan-hash sha256:<digest>
```

展示后不要求用户逐次确认。
如果请求在 `prepare` 后发生任何变化，旧 hash 会被拒绝，
必须重新 `prepare`、重新展示，再执行。

## 退出状态

- `0`：校验通过，或所有编译步骤完成
- `2`：请求格式、身份字段或 plan hash 不合法
- 其它非零值：实际编译步骤的退出码

某一步失败后，后续步骤不会继续执行。
