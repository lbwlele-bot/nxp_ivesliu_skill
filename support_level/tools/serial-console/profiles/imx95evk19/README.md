# i.MX95 19x19 EVK Serial Profile

## 当前映射

该 profile 仍是 `partial`：

| 顺序 | Interface | 默认 role | 状态 |
|---|---|---|---|
| 第 1 个 COM | `if00` | `first-runtime` | 已验证 |
| 第 2 个 COM | `if01` | 未确认 | 不猜测 |
| 第 3 个 COM | `if02` | `a55-rtos` | 已验证 |
| 第 4 个 COM | `if03` | `cm33-smfw` | 已验证 |

参数为 `115200 8N1`。未确认 `if01` 前，不得自动给它分配 Linux、M 核或
系统管理固件 role。

## BCU UART Mux 风险

`bcu reset ... -keep` 可能把 `ft_fta_sel` 留在 HIGH，从而抑制
`first-runtime` 输出。出现第一路假静音时，先按板级规则恢复
`ft_fta_sel`，不要直接判断对应固件或系统没有启动。
