---
name: build-customer-release
description: 从当前 NXP i.MX case 生成精简、可审计、经过语义验证的客户 release package。用于用户要求“做客户包”、“生成 release 包”、“准备客户交付包”、“整理补丁和移植文档”或对已有客户包做结构、补丁、脚本、校验和声明一致性检查。默认面向客户工程师理解方案并移植到自有板卡，不生成内部调试过程的文档堆或未经语义验证的复现脚本。
---

# 构建客户 Release 包

## 默认交付形态

将“给客户做 release 包”默认理解为 `customer_integration`：

- 客户要理解思路、修改点、修改原因、移植顺序和风险；
- 客户不需要复制内部调试全过程；
- 只有用户明确要求“可完整复现构建”时，才转为 `reproduction` 包。

不重复询问这些默认值。只有受众、交付组件或未验证声明会实质改变包内容时才请用户决定。

## 读取证据

1. 先读当前 case 的 `README.md`、`state/` 和产物索引，再读支撑最终结论的记录。
2. 将声明分成：已验证、用户接受的 waiver、未验证。
3. 不把编译成功写成上板成功，不把 channel 出现写成业务 payload 已验证，不把单板观察外推为芯片保证。
4. 产物缺失时转 `compile`；必需的板级证据缺失时转 `board-exec`。本 skill 不默认重编或动板。

## 组织内容

默认根目录只允许：

```text
README_CN.md
RELEASE.yaml
SHA256SUMS
patches/
binaries/       # 只有确实交付预编译产物时
reference/      # 只有移植必需的 map、身份或代码框架
licenses/
```

以本 skill 目录为相对路径根，从
`assets/README_CN.template.md` 生成唯一的客户主文档。它必须说清：

- 解决什么问题以及整体数据/控制流；
- 为什么选择当前方案；
- 每个组件改了什么、为什么改；
- 客户在自有板卡上的移植顺序；
- 已验证范围、未验证项和产品化风险。

不把 case 的 `logs/`、`records/`、`state/`、`build/`、排障时间线或内部主机路径放入客户包。不为了“看起来完整”拆出多份重复文档。

## 生成补丁和脚本

- 每个补丁从声明的干净 baseline 到最终源码生成，不从中间失败版本生成。
- 在干净 baseline 上执行 `git apply --check` 或 `patch --dry-run`；只有语法正确不算通过。
- `customer_integration` 默认不附构建/烧写脚本。如用户确实需要脚本，必须在内部 release request 中为每个脚本声明无副作用的语义检查命令。
- shell 脚本同时通过 `bash -n` 和真实 `--help`/`--dry-run`。检查输出中的参数和命令，不只看退出码。

## 建立发布请求

将 `assets/customer-release-request.template.yaml` 复制到当前 case 的
`records/release/customer-release.yaml`，填写：

- 必须文件和允许的根目录对象；
- README 必须覆盖的关键语义；
- 每个 patch 的客户包相对路径、baseline 和校验方式；
- 如果存在脚本，声明它的语法和语义检查。

这份 request 只留在 case，不进客户包。客户包内的
`RELEASE.yaml` 从 `assets/RELEASE.template.yaml` 生成，不写本机绝对路径。

## 验证与打包

1. 先验证未压缩目录：

   ```bash
   python3 <skill-dir>/scripts/validate_release.py <release-dir> \
     --spec <case>/records/release/customer-release.yaml
   ```

2. 在 release 根目录生成 `SHA256SUMS`，它覆盖除自身外的所有文件。
3. 生成 `.tar.gz`，不在原包上就地覆盖。
4. 对压缩包再运行同一校验器，确认只有一个顶层目录、无路径逃逸、checksum 与解包后内容一致。
5. 最终交付时只报告包路径、大小、SHA-256、已通过的验证和未验证限制。

检查历史包的结构时可使用 `--layout-only`；它不等于新包的最终验收。

## 停止条件

出现任一情况就停止发布，保留验证日志：

- patch 不能干净应用；
- 产物身份或 SHA-256 与 case 证据不一致；
- README 把 waiver/未验证项写成已通过；
- 脚本只通过语法检查，没有通过语义检查；
- 压缩包与已验证目录的内容不一致；
- 需要用户做会改变技术声明或产品策略的决定。
