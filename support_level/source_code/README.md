# source_code

这里放长期保留的源码基线。

当前开始采用的新模型是：

- `modules/`
  单模块长期源码基线
- `_to_absorb/`
  从旧系统复制过来的混合资产，后续按旧 skill 再拆

## 长期结构

每个可长期保留的源码模块，都按下面的形式管理：

```text
source_code/
  modules/
    <module>/
      USAGE.md
      <real-source-tree>/
```

例如：

```text
source_code/
  modules/
    imx-atf/
      USAGE.md
      imx-atf/
```

## 为什么这样做

这样后面每吸收一个旧 skill，都能直接落到对应源码模块旁边：

- 源码本体在同一个目录里
- 编译/查看/版本差异说明写在 `USAGE.md`
- 不再靠一个巨大 skill 把很多源码、很多版本、很多芯片混在一起讲

## 使用规则

- 先定位模块目录
- 先读该模块的 `USAGE.md`
- 再进入旁边真实源码目录看实现细节
- 只读检查可以直接在这里做
- 要改动、构建、生成输出，复制到 `../work/<case>/` 再做

## `_to_absorb/` 的含义

`_to_absorb/` 不是长期形态。
它只是一个暂存区，用来放从旧系统复制过来、但还没拆清的东西，例如：

- 整套版本快照
- 集成 workspace
- alias 目录
- 源码压缩包

这些东西后续只有两种去向：

- 被拆成一个个清晰模块，进入 `modules/`
- 确认没有长期价值后删除

## 当前模块

- `imx-atf`
- `imx-mkimage`
- `imx-oei`
- `imx-optee-os`
- `imx-sm`
- `linux-imx`
- `mcuxsdk-core`
- `mcuxsdk-manifests`
- `meta-real-time-edge`
- `real-time-edge-linux`
- `real-time-edge-uboot`
- `uboot-imx`
