# ADR-0004：为可访问 Dashboard 评估 PySide6 Qt Widgets

**Status:** Proposed<br>
**Date:** 2026-09-07

## Context

Analog Validation Studio 当前 Dashboard 使用 Python 自带的 Tk 8.6.15。
虽然应用已有文字状态、键盘焦点、字段错误定位和 Windows 高对比度，但 Windows
UI Automation 将 37 个应用后代全部识别为无名称 Pane。屏幕阅读器无法可靠得知
输入框、按钮、当前步骤或运行状态。

Tk 9.1 增加了 `tk accessible`，但它目前是预览版本。Python 3.14/3.15 的 Windows
构建转向 Tk 9.0.4，而 Tk 9.0 没有这项接口。Tk 9.1 的官方 TIP 还说明 Windows
实现主要通过 MSAA 桥接；NVDA 是主要开发测试对象，基于 UIA 的 Narrator 体验较弱。
因此，升级普通 Python 版本或直接捆绑 Tk 9.1 beta 都不能形成稳健的候选方案。

现有架构把 Tk 限制在 `dashboard/app.py` 和 widget 构建层。Dashboard state、
presenter、application、wizard、project workspace、worker、services、CLI 和领域层
均不依赖 tkinter，这允许替换显示驱动而不复制业务规则。

## Decision

在获得依赖与许可证批准后，以 **PySide6 Essentials + Qt Widgets** 作为首选的
可访问 Dashboard 迁移候选，先开发一个小型纵向切片，再决定是否完整迁移。

当前不改变生产依赖、包许可证、Dashboard 入口或 Tk fallback。后续候选必须：

- 只消费现有不可变 Dashboard state、presenter 和 application action；
- 不复制校准、分析、批次、取消、cleanup、manifest、项目历史或证据判断；
- 先实现 Simulator 的 Source → Review → Run status → Result 最短链；
- 不包含串口发现、真实设备、硬件访问或新业务功能；
- 使用标准 Qt Widgets 以及明确的 accessible name/description；
- 为动态状态发送 Qt accessibility 事件，并保留可读文字；
- 保持 Tk Dashboard 可用，直到 Qt 路径达到功能与安全等价；
- 把 Qt 作为可选 GUI extra，CLI 和基础 wheel 不依赖 GUI 框架；
- 在正式依赖变更前完成 LGPL/第三方 notices、wheel 体积、离线安装、构建可复现性
  和目标 Python/Windows 版本审查。

只有 UI Automation 中名称、角色、值、焦点和事件正确，Narrator/NVDA 链通过，
并完成真实辅助技术用户验收后，才能声明 Dashboard 支持屏幕阅读器。

## Prototype evidence

仓库外临时环境安装了 PySide6 Essentials 6.10.1 和 shiboken6 6.10.1。最小 Qt
Widgets 窗口只包含 Source、Replay path、Run status 和 Validate action。

同一台 Windows 主机上的 UI Automation 识别到：

| 控件 | UIA 类型 | 可聚焦 |
|---|---|---|
| Source label | Text | 否 |
| Source selector | ComboBox | 是 |
| Replay CSV path label | Text | 否 |
| Replay CSV path input | Edit | 是 |
| Run status | Text | 否 |
| Validate setup | Button | 是 |

状态 accessible name 从 `Run status` 更新到
`Run status: READY; setup validated` 后，UI Automation 的轮询结果同步改变。该检查
证明 Windows 可以发现语义与动态属性；尚未证明事件播报顺序或真实屏幕阅读器体验。

下载的 Essentials wheel 为 74.5 MB；临时环境的相关 site-packages 约 206.3 MiB。
PySide6 提供 LGPLv3/GPLv3/商业许可证选择。体积、许可证和第三方 notice 都是正式
采用前必须解决的产品成本。

## Consequences

- 可访问性路线不再依赖 Tk 9.1 beta 或把键盘焦点当作屏幕阅读器证明。
- 业务、证据、CLI、项目和批次契约可以保持不变。
- GUI 安装体积和分发复杂度会明显增加。
- 在 Qt 原型达到等价前需要维护两套显示层。
- 当前 Tk Dashboard 仍明确不支持屏幕阅读器。
- 本 ADR 保持 Proposed；依赖和许可证变更需要项目所有者明确批准。

## Alternatives considered

1. **继续 Tk 8.6：** 保留为当前 fallback，但无法满足程序化辅助技术要求。
2. **直接迁移 Tk 9.1 beta：** 暂不采用；Python 稳定 Windows 分发尚未提供该组合，
   且 Windows 屏幕阅读器后端对 Narrator 的官方说明仍有限。
3. **只升级 Python 3.14/3.15：** 拒绝作为修复；其 Tk 9.0.4 不含
   `tk accessible`。
4. **WinUI/.NET：** 原生 Windows UIA 强，但会引入 Windows 专用运行时和跨语言
   host，偏离当前 Python 跨平台产品壳。
5. **本地 Web UI：** 浏览器辅助功能成熟，但会新增本地服务器、浏览器生命周期、
   CSP/端口和打包边界，超过当前显示层替换范围。

## References

- [Tcl/Tk TIP 733](https://core.tcl-lang.org/tips/doc/trunk/tip/733.md)
- [Tcl/Tk 9.1 accessible manual](https://www.tcl-lang.org/man/tcl9.1/TkCmd/accessible.html)
- [CPython Windows Tcl/Tk 9.0.4 backport](https://github.com/python/cpython/pull/150197)
- [Qt for Python QAccessible](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QAccessible.html)
- [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html)
