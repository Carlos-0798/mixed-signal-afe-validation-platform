# TD-051：核心运行与用户工作流整体审查

日期：2026-09-09。所有者明确授权重新审视运行层和界面层、突破原有小阶段规划。
本轮交付为未提交的源码改进和独立安装预览；没有发布或硬件验证。

## 产品判断与结果

AVS 的定位继续是控制器中立的本地测试与分析工作台。它应当减少重复配置、手工
处理与拼接报告的操作，同时让结果、条件和证据来源可追溯。本轮采用已有可靠
算法和服务，打通四处实际断点：

| 改进 | 用户得到什么 | 保护措施 |
| --- | --- | --- |
| 预设载回 Setup | 保存过的参数可重新使用、修改、审核和运行 | 原预设不变；有编辑/未保存结果时确认替换；重新 Review；载入不执行 I/O |
| GUI 完整报告包 | 一次保存 HTML、SVG、Markdown、文本、规范 JSON 和 manifest | 同一结果来源、原子发布、新目录、不覆盖；打开 HTML 前检查记录的大小与 SHA-256 |
| 每次读取前检查取消 | 请求取消后不再发起下一次采集 | 保留 worker cleanup；不把取消后的部分采集发布成已完成分析 |
| 批次后项准备失败保留先前成果 | 第一项已完成、第二项输入缺失时，第一项仍可查看、校验、交付 | v4 显式记录准备失败和未开始项；不虚构 worker、测量或证据等级 |

三套主题 Workbench、Daylight、Midnight 沿用上一阶段的可读性改进。未复制工程算法、
更换 UI 框架或加入无关功能。定向修复了新发现的隐藏字段问题：CSV 范围无效后切换
Simulator，不再被不可见的 Replay 字段阻塞；合法非默认范围仍能精确往返。

## 数据契约与兼容性

- 新批次写 `validation-run-manifest.v4`，增加 nullable `preparation_failure`：
  `preset_id`、`issue_code`、`technical_type`、`message`。
- v1、v2、v3 仍严格按原形读取/序列化，不修改旧文件。严格外部读取器要显式增加
  v4 支持，不能假定旧读取器自动理解新格式。
- 首项准备失败依然不发布空运行目录；已有实际记录后的预期准备失败才保留 ERROR
  历史。无法确认 cleanup 的 worker timeout、最终发布失败不伪造成功保存的历史。
- CLI 进度仍只写 stderr，stdout JSON 保持纯机器文档；取消退出码仍为 130。
- `publish_human_report(..., result_bundle=None)` 为兼容的可选参数；省略它仍产生
  原来五个报告文件，原报告 golden 字节不变。GUI 使用它增加 `result.json`，
  不改变 `result-export.v1` 或 `human-report.v1` 的含义。
- `run_read_workflow(..., checkpoint=None)` 为可选 keyword-only 扩展；既有两参数
  调用保持有效。Dashboard 增加预设载入、报告保存和 report publication 访问接口。
- Phase 2/5 公共 API golden 经评审更新。API golden 的物理换行按 `.gitattributes`
  统一为 LF；Phase 3 内容与 HEAD blob 完全一致，仅修正本地 CRLF 物理形式。
  没有重新生成历史运行产物、测量、CSV 或报告文件。

## 首次失败与修复

1. 定向检查暴露了普通采集取消滞后、后续准备失败撤销先前产物，以及合法非默认
   Replay 范围无法精确还原预设的问题，分别以逐次 checkpoint、v4 失败记录和精确
   草稿转换修复。
2. 独立交互复查发现本轮公共范围解析导致隐藏字段阻塞 Simulator。新增 7 项用例，
   非 Replay 的无效隐藏范围采用配置默认值；实际 Replay 仍严格拒绝错误。
3. 第一次全套结果为 **8 failed / 2,835 passed，99.93% statement coverage**。
   8 项均是旧测试 wrapper/fake 未接收 `on_load_setup` 新回调，涉及五档真实 Tk
   测试与三个项目生命周期测试。补齐转发和报告挂载点后原生命周期检查恢复。
4. 新测试的 mypy 曾拒绝以 `list.append(...) or True` 表达 bool 回调，改为显式返回
   bool 的测试函数。若干早期测试使用错误字段/枚举名称，修正测试后通过。
   没有以降低 coverage、跳过测试或移除原断言解决失败。

## 最终验证

| 验证 | 真实结果 |
| --- | --- |
| 全套 pytest | **2,850 passed，97.13 s** |
| 完整三个 package statement coverage | **16,714 / 16,714，100.00%** |
| Ruff | 通过 |
| mypy | 239 个源文件通过 |
| 开发与独立安装环境 pip check | 通过 |
| git diff --check | 通过；部分上一阶段文件仍有 Git 换行提示，不是 whitespace error |
| 真 Tk 完整产品链 | 预设→修改/取消替换→重新 Review→Simulator→六文件报告→哈希→拒绝覆盖→三主题→安全关闭，通过 |
| 原项目页面五档缩放 | 1.0 / 1.25 / 1.5 / 1.75 / 2.0，通过 |
| 最小窗口 | 1040×760 下报告 Save/Open 按钮实际处于可视区域，通过 |
| 新 snapshot 构建/安装 | sdist、wheel 构建通过；新 venv 离线安装本地 wheel；真实 console launcher 启动通过 |
| 安装版 CLI/API | 6 项复合检查、6 次实际 CLI 调用，通过；模块来自新环境 site-packages |
| 安装版 GUI | 独立无 pytest 依赖的实际窗口闭环通过，保存同源报告并拍摄三主题截图 |
| 安装版产品质量工具 | 15/15，通过；10k Replay、事件队列、LIVE 缓冲及 deterministic demo |

本轮生成结果为 SYNTHETIC 或测试中的临时 CSV_REPLAY，验证为 HOST_TEST。
GUI 自动验收用可控路径和确认回答替代原生文件对话框，以 mock 记录浏览器打开请求；
真实窗口、按钮绑定、状态、文件发布与哈希仍实际执行。系统默认浏览器没有在本轮打开。
没有新增 SPICE_IDEAL、BENCH_CONTROLLER 或 BENCH 证据。100% statement coverage
不等于无 bug，也不是完整分支覆盖或硬件性能证明；没有测量人工对照效率提升百分比。

## 实际修改文件

下列为本轮改动；上一阶段主题文件继续保留，不重复记成本轮新实现。

- 核心运行：`src/analog_validation/workflows/read.py`；
  `src/analog_validation_app/{services,projects,cli,__init__}.py`。
- 用户主链：`src/analog_validation_app/dashboard/{app,application,wizard,project_widgets,project_workspace}.py`；
  新增 `{presets,report_actions}.py`。
- 报告：`src/analog_validation_app/reporting.py`。
- 契约：`test-data/golden/{phase2_public_api,phase5_public_api}.json`；
  `tests/golden/test_phase5_public_api_golden.py`；Phase 3 golden 仅物理换行处理。
- 原测试调整：`tests/unit/{test_dashboard_app,test_dashboard_projects,test_product_projects,test_product_projects_cli}.py`；
  `tests/integration/test_dashboard_project_workflow.py`。
- 新增测试：`tests/unit/{test_read_workflow_cancellation,test_batch_preparation_failure,test_dashboard_presets,test_dashboard_product_actions,test_dashboard_product_application,test_report_package}.py`；
  `tests/integration/test_dashboard_product_loop.py`。
- 文档：`docs/{FEATURE_FREEZE,KNOWN_LIMITATIONS,TECHNICAL_DEBT,dashboard,human-reports,phase5-public-api,product-cli,product-worker,test-projects-and-history}.md`；
  新增 `docs/PRODUCT_REVIEW_2026-09-09.md` 和本报告。

## 交付与 Git 状态

工作树为 `outputs/.worktrees/calibration-workflow`，分支 `codex/calibration-workflow`。
HEAD 保持 `aa1dd5b84dc5494d02b5ec20924527f83fad146e`，没有提交或推送。
本轮开始时已有的 12 个未提交文件已经在修改前逐字节备份，原成果继续保留。
最终 Git 显示 33 个修改、15 个未跟踪，共 48 项；其中 Phase 3 golden 没有净内容差异。
逐文件 SHA-256 见外部 `verification.json`；不把初始旧交接快照的
53 文件数量当成今天仍然成立的事实。

外部交付目录标识：`avs-product-review-20260909-071528`。
本机绝对路径保存在工作树外的同步接续档案中；同步前原始报告副本保持不变。

其中 `OPEN_DASHBOARD.cmd` 启动独立安装预览，`README_ZH.md` 提供操作步骤；
`final-pytest.log`、`installed-product-quality.json`、`installed-acceptance/verification.json`
及 `installed-gui*/acceptance.json` 保存验收证据。`source-inventory.json` 记录构建输入；
最后的验证报告和少量文档澄清完成于构建之后，运行源代码与安装 wheel 另行核对。
旧 candidate/showcase/theme preview、演练和本轮失败诊断均保留，没有重写旧展示包。

## 剩余事项与停止点

TD-051 关闭。当前主链已形成可靠可用的增量，适合先进行真实使用和展示反馈。
READ/LIVE 全量观察持久化、原地编辑预设、跨运行曲线叠加、主题跨重启记忆、屏幕
阅读器支持继续作为独立事项；没有为追求页面数量而增加菜单或静态演示数据。
当前 adapter 调用阻塞时取消仍需等待返回，这是协作式取消的明确边界。

本轮没有 reset、checkout、clean、覆盖既有产物、合并仓库、修改 PR、标签、Release、
可见性、许可证或历史；没有枚举/打开串口、操作 MSP430/AFE/实验室仪器或采购。
建议下一步由所有者使用新预览体验实际任务，再按确切问题选择改进；当前停在未提交状态。
