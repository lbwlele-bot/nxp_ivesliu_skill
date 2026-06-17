# compile_targets

这里放编译对象入口。

这层不是源码资产层，也不是 case 输出层。
它只负责说明：

- 我现在到底要编什么
- 这个编译对象依赖哪些源码资产、SDK、toolchain、firmware、workspace
- 正常应该从哪里开始编
- 哪些目录只是输入来源，不能直接拿来编

这层由 `compile` owner。
正常顺序是：

1. 先进入 `compile`
2. 由 `compile` 判断当前属于哪个编译对象
3. 再进入这里对应对象的 `README.md`

当前已收编译对象：

- `flashbin`
- `linux`
- `m_freertos_sdk`
- `zephyr`
- `a55_rtos`
