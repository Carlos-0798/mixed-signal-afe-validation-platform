# TD-050：Dashboard 三主题与文字可读性

日期：2026-09-09。证据：HOST_TEST；运行验收使用 SYNTHETIC Simulator。

## 触发与边界

所有者反馈原界面字体不突出、配色不协调，希望可选择工作台、白天、深夜等风格。
这是功能冻结后的显示可读性例外，不启动新的业务功能或 UI 运行时迁移。

修改前只读确认：分支 `codex/calibration-workflow`，HEAD
`aa1dd5b84dc5494d02b5ec20924527f83fad146e`，工作树干净。
开发环境实际导入位于 `outputs/.worktrees/calibration-workflow/src/`。
此前成果已在先前单独授权的本地提交中；本轮没有重置、覆盖旧成果或创建新提交。

## 实际变化

- 新增不可变配色定义 `dashboard/themes.py`：Workbench 为中性石板灰，Daylight
  为白底深字，Midnight 为低亮度炭灰。减少高饱和青色和亮边框的装饰感。
- 顶部 **Appearance (this window)** 即时切换三主题；窗口关闭后恢复默认
  Workbench。Windows 高对比度优先，选择器显示 System contrast 并禁用。
- 正文、辅助提示和表格至少 10 pt；正文、辅助文字、禁用状态、选中行、按钮状态
  和曲线图例的指定色对达到 4.5:1 对比度下限。此指标不是完整无障碍认证。
- ttk 样式、原生下拉列表、滚动背景、实时曲线同步重绘；不重建业务控件或任务。
- 修正禁用状态被 active/readonly 样式抢先匹配，以及项目页滚动背景漏用系统
  高对比度的问题。实际截图检查后，统一 light/dark border 颜色，减少深色主题的亮边。

操作顺序、数据模型、公开 API、manifest v1/v2/v3、工程结论、证据标签、产物哈希、
create-new 和取消/cleanup 契约均未改变，既有 API golden 无需改写。
没有引入第三方运行依赖、主题配置文件或网络资源。

## 验收与首次失败

真实 Tk 检查覆盖三主题及系统高对比度 × 五档缩放（1.0、1.25、1.5、1.75、2.0），
共 20 组。检查主题选择器和关键控件可见、键盘焦点、CSV Replay 缺失路径的错误样式，
以及切换后输入、错误、焦点、滚动位置、禁用样式和已创建下拉列表的保持。

独立真实窗口组合链使用新临时项目目录：选择两个预设、填写未保存输出目录、切换
三主题，确认选中行、页签和输入保持；启动真实 Simulator LIVE_MONITOR worker，
在运行中切换主题，确认已审核任务、已采集点与状态保持，最后正常 SUCCEEDED，
结果仍标注 SYNTHETIC。主题回调未调用任何业务动作。

新组合链前两次失败来自测试脚本本身：第一次在 Source 步骤提前选择任务，被既有
向导正确拒绝；第二次错误地把 ReviewedServiceRouter.prepared 当作
DashboardApplication 的属性。修正测试顺序和对象引用后组合链通过，没有为通过
测试而放宽业务状态机。首轮 mypy 指出 10 个测试属性引用问题；修正这些引用和
动态 Tk 测试门面的类型标注后通过。

| 最终检查 | 实际结果 |
| --- | --- |
| 完整 pytest | 2,727 passed，69.19 秒 |
| 三个正式包 statement coverage | 16,424 / 16,424，100% |
| Ruff（src/tools/tests/examples/public_adapter） | 通过 |
| mypy（同范围） | 230 个文件，无错误 |
| pip check | 无损坏依赖 |
| git diff --check | 通过；仅 Git 的 CRLF→LF 提示，无空白错误 |

在最终边框收敛前的完整回归同样为 2,727 passed、100%；边框修改后执行了上述最终
完整门禁。没有用局部 coverage 代替正式三个包的 coverage。
实际窗口截图已逐张查看；截图程序使用无业务回调的显示夹具，功能链证据来自测试。

## 修改文件

- `src/analog_validation_app/dashboard/themes.py`
- `src/analog_validation_app/dashboard/widgets.py`
- `src/analog_validation_app/dashboard/project_widgets.py`
- `tests/unit/test_dashboard_themes.py`
- `tests/unit/test_dashboard_widgets.py`
- `tests/unit/test_dashboard_workflow_widgets.py`
- `tests/integration/test_dashboard_theme_switching.py`
- `tests/integration/test_phase5_dashboard_accessibility_smoke.py`
- `docs/dashboard.md`
- `docs/FEATURE_FREEZE.md`
- `docs/TECHNICAL_DEBT.md`
- 本报告。

本轮末 Git 为 8 个已修改、4 个未跟踪文件，共 12 个未提交文件；分支和 HEAD 未变。

## 使用入口与剩余事项

工作树外 `avs-theme-preview-20260909/` 保存三套真实截图、最终测试日志、中文使用说明
和 `OPEN_UPDATED_DASHBOARD.cmd`。新入口启动当前工作树 .venv 中的 Dashboard，
便于与未改动的旧展示包区分；它不是可分发安装包。本轮没有重新构建候选包或发布。

TD-050 关闭。跨重启保存主题尚未实现，界面明确说明选择只作用于当前窗口。
既有 TD-043B2A 屏幕阅读器限制保留；主题切换不等于完成该技术债，也不触发 Qt 迁移。
下一步仅收集所有者对三种主题实际使用的反馈；没有证据时不扩展皮肤编辑器、动画或新功能。

没有提交、推送、PR/Release/可见性/许可证/历史修改，没有真实串口枚举、设备访问
或硬件采购。旧候选包和演练目录未改动。本轮不产生 BENCH_CONTROLLER 或 BENCH 证据，
软件 PASS 不能解释为硬件验证。
