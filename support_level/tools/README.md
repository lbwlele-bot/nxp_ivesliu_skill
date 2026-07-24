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
  serial-console/
    USAGE.md
    serial-console
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
- `bcu` 和 `uuu` 是固定 root 工具：任何调用都必须带 `sudo -n`
- `sudo -n` 失败就报告权限问题，不先尝试或回退到普通用户执行

## 当前工具

- `bcu/`
- `uuu/`
- `imx-rm/`
- `serial-console/`
