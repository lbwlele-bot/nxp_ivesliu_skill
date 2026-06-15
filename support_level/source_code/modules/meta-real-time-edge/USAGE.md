# meta-real-time-edge

- 真实源码目录：`./meta-real-time-edge/`
- 当前参考分支：`master`
- 当前参考版本：`Real-Time-Edge-v3.3-202512-57-g76f670a`
- 主要链路：`linux-bsp`

## 使用规则

1. 先确认任务是不是落到 `Real-Time Edge` 的 meta layer
2. 先核对当前 ref
3. 只读检查可直接在这里做
4. 要改 layer、拉构建链、产生产物，复制到 `../../work/<case>/` 再做

## 已吸收：`RTE` patch-truth 角色

对 `RTE` lane，
`meta-real-time-edge` 第一轮吸收后的稳定角色是：

- patch truth bucket
- source / branch / version mapping 的补充 truth
- `ATF`
  `SMFW`
  `U-Boot`
  等 `RTE` delta 的来源之一

它不直接等于：

- 最终 runtime owner
- board deploy owner
- 某一个 case 的完整 recipe owner

## 已吸收：`imx95-rte33-build-flashbin` / `imx943-linux`

- `i.MX95 RTE 3.3`：
  `ATF` / `SMFW` patch sync 要从这里分 bucket 看
- `i.MX943 RTE Linux`：
  版本判断时也要把这里当成 patch-truth / branch-truth 候选

高风险误区：

- 不要把整层 patch 全灌给单个模块
- 要先按 module owner 分 patch bucket

## 待补全

- 版本与 Yocto/BSP 的对应关系
- 相关旧 skill 的吸收结果
- 典型构建入口
