# tools

这里放长期保留的主机侧工具。

当前开始采用的新模型是：

```text
tools/
  <tool>/
    USAGE.md
    <program-or-version-dir>
```

例如：

```text
tools/
  bcu/
    USAGE.md
    bcu
  uuu/
    USAGE.md
    uuu
    1.5.243/
      uuu
```

## 使用规则

- 先定位工具目录
- 先读对应 `USAGE.md`
- 再决定是否直接执行程序
- 工具层只写稳定工具边界，不在这里写具体板型操作步骤

## 当前工具

- `bcu/`
- `uuu/`
- `imx-rm/`
