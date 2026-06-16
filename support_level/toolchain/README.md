# toolchain

这里放长期复用的交叉编译工具链和相关主机侧编译输入。

它回答的是：

- 这台 Ubuntu 本机当前有哪些可复用 toolchain
- 哪类源码该用哪一类 toolchain
- 哪些场景必须把 A-core / M-core toolchain 明确分开

## 使用规则

1. 先确认当前任务属于哪条编译链
2. 不要只看“目录里有 gcc”，要先确认它属于：
   - A-core / Linux side
   - M-core / firmware side
3. 需要向脚本或 make 传 toolchain 前，优先显式传目录或 prefix
4. 不要依赖模糊的 wildcard 自动选 toolchain

## 当前可复用工具链形态

当前目录里已经有这些长期资产：

- `arm-gnu-toolchain-14.3.rel1-x86_64-aarch64-none-linux-gnu/`
  A-core / Linux-targeted `aarch64-none-linux-gnu`
- `arm-gnu-toolchain-14.3.rel1-x86_64-arm-none-eabi/`
  M-core / firmware-targeted `arm-none-eabi`
- `arm-gnu-toolchain-14.2.rel1-x86_64-aarch64-none-elf/`
  某些 A-core baremetal / 特殊场景候选
- `arm-gnu-toolchain-14.2.rel1-x86_64-arm-none-eabi/`
  M-core / firmware 候选
- `gcc-arm-none-eabi-9-2019-q4-major/`
  旧版 `arm-none-eabi`
- `zephyr-sdk-1.0.1/`
  Zephyr 相关链路

## 当前长期边界

- `U-Boot`
- `ATF`
- `OP-TEE`

更偏向 A-core side。

- `OEI`
- `SMFW`
- 某些 M-core payload

更偏向 M-core / firmware side。

所以对 `flash.bin` 打包链，尤其是 `i.MX95 RTE 3.3` 这种链路，
必须先把 A-core / M-core 工具链的归属分清。

## 已吸收：`imx95-rte33-build-flashbin` 的 toolchain 边界

对 `i.MX95 RTE 3.3 flash.bin`：

- `U-Boot` / `ATF` / `OP-TEE`
  属于 A-core side
- `OEI` / `SMFW`
  属于 M-core / firmware side
- 不要把 `OEI` / `SMFW` 偷偷吃成 A-core toolchain
- 也不要靠“PATH 里刚好先撞到哪个 gcc”去赌

旧 skill 的稳定结论是：

- 优先显式给出 `AARCH64_TC_DIR`
- 优先显式给出 `ARM_NONE_TC_DIR`

也就是说，先把“哪条链用哪个 toolchain”说清，
再跑 build。

## 当前推荐读取方式

如果任务是 启动固件 / `flash.bin`：

1. 先读当前任务相关模块的 `USAGE.md`
2. 再回到这里确认工具链归属
3. 最后才去实际跑构建命令

如果任务是 `i.MX95 RTE 3.3 flash.bin`，
这里要先确认的不是“目录里有没有工具链”，
而是：

- A-core side 用的是不是 Linux-targeted `aarch64-none-linux-gnu`
- M-core side 用的是不是明确的 `arm-none-eabi`
- 当前脚本 / make 变量有没有把这两条链分清

## 当前不该怎么用

- 不要把 `toolchain/` 当成源码目录
- 不要把“存在多个版本”误当成“可以随便混用”
- 不要默认旧版 `gcc-arm-none-eabi-9-2019-q4-major` 就是所有 M-core 链路的优先选择
- 对会影响输出结果的链路，不要把工具链选择写成模糊默认值
