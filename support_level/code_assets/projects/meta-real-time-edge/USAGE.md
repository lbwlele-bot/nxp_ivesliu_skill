# meta-real-time-edge

- 真实源码目录：`./meta-real-time-edge/`
- 最近观察 ref：`master` / `Real-Time-Edge-v3.3-202512-57-g76f670a`，使用前重新核对
- 主要链路：`rte`、`yocto`

这是 Real-Time Edge 的 Yocto layer。它主要用来查 RTE 镜像、distro、
machine、packagegroup、bbappend 和 RTE patch 来源。

RTE 的跨项目规则不放在这里，先看 `../../../software_stacks/rte.md`。

## 什么时候看这里

- 当前任务明确进入 Real-Time Edge / Yocto layer
- 需要查 RTE image、distro、machine 或 packagegroup
- 需要按模块确认 RTE patch bucket，例如 `imx-atf`、`imx-system-manager`
  或 `u-boot`
- 需要确认 RTE layer 指向哪条 `real-time-edge-uboot` 分支

## 常用入口

- `meta-real-time-edge/README.md`：RTE Yocto release 的基础说明
- `meta-real-time-edge/conf/layer.conf`：layer 兼容性和动态 layer 入口
- `meta-real-time-edge/conf/distro/`：RTE distro 配置
- `meta-real-time-edge/conf/machine/`：RTE machine 配置
- `meta-real-time-edge/recipes-nxp/images/`：RTE image recipe
- `meta-real-time-edge/recipes-nxp/packagegroups/`：RTE packagegroup
- `meta-real-time-edge/dynamic-layers/imx-layer/recipes-bsp/`：
  i.MX 侧 `ATF`、`SMFW`、`U-Boot` bbappend 和 patch 线索

## 使用规则

1. 使用前先在 `./meta-real-time-edge/` 下核对当前 ref。
2. 只读查 recipe、bbappend、patch 可以直接在共享源码目录做。
3. 不要把整层 patch 全灌进单个项目；先按 recipe / bbappend 分桶。
4. 要改 layer、拉 Yocto 构建、产生产物或试 patch，在当前 case 的
   `../../../work/<case>/` 下做，不污染共享基线。

## 边界

- RTE 版本、LF/BSP 对应、跨项目输入集合：看 `../../../software_stacks/rte.md`
- `flash.bin` 打包：看 `../../../compile_targets/flashbin/README.md`
- 单项目源码构建：回到对应项目 `USAGE.md`
- 真正上板、烧写、串口验证：进入 `board-exec`

一句话：这里回答“RTE Yocto layer 里有哪些配置、recipe 和 patch 线索”，
不直接回答“某个模块最终怎么编、flash.bin 应该怎么组”。
