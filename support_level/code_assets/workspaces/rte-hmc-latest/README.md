# rte-hmc-latest

这是从旧 `NXP` 工作区补过来的 `RTE HMC` 集成工作区。

当前保留它，是因为你关心的 `A` 核 `RTOS` / `heterogeneous-multicore`
代码不只是某一个单独仓库，而是和下面这些部分一起协同：

- `heterogeneous-multicore/`
- `zsdk/`
- `mcuxsdk/`
- `.west/`

当前本地这份 `heterogeneous-multicore` 的参考版本是：

- `Real-Time-Edge-v3.4-202604`

使用规则：

- 如果任务明确落到 `RTE A` 核 `RTOS`、`heterogeneous-multicore`、`west` 工作区联动，先来这里
- 如果只是查源码资产，优先回到 `../../projects/`
- 如果其实是在编纯 Zephyr，对应对象优先看 `../../../compile_targets/zephyr/`
