# i.MX93 14x14 LPDDR4x EVK Serial Profile

## Onboard FT4232H 映射

| 顺序 | Interface | 默认 role | 已验证输出 |
|---|---|---|---|
| 第 1 个 COM | `if00` | `first-com` | 未分配默认运行日志 |
| 第 2 个 COM | `if01` | `second-com` | BCU 板控，无默认运行日志 |
| 第 3 个 COM | `if02` | `a-core` | SPL、U-Boot、Linux |
| 第 4 个 COM | `if03` | `m33` | M33 |

默认同时捕获 `a-core` 和 `m33`，参数为 `115200 8N1`。

## BCU 影响

BCU 实际板控访问固定使用 FT4232H channel 1，即 `if01`。当前实测
`get_boot_mode` 和 reset 都可能在退出后留下未绑定的 `if01`，而
不访问板卡的 `bcu version` 不影响绑定。

这不会直接移除 `if02` 的 A-core 或 `if03` 的 M33 日志，因此可在允许的
BCU reset 流程中先捕获这两路。BCU 退出后仍应恢复 `if01`，并要求 fresh
probe 重新看到四个 interface：

```bash
sudo -n ./serial-console recover --board imx93evk14
./serial-console probe --board imx93evk14
```

reset 是否允许由板级执行规则决定，不由本工具或 profile 自动决定。

## 证据

- profile 验证日期：2026-07-24
- 来源 case：`2026-07-24-imx93evk14-serial-console-validation`
- A-core 已抓到 Linux login；当前镜像的 M33 端口映射已确认
