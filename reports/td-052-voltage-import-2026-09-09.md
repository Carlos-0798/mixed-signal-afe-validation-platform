# TD-052：通用电压文件导入验收

**状态：** 本地实现及验收完成，未提交、未发布。日期为本地 2026-09-09。

## 目的与实际效果

本轮回应“只有一块开发板，也希望扩大软件适用范围”的需求：让不同来源可导出的电压表格，经显式映射进入同一套分析、批次、历史和报告。用户不必为每种列名、列顺序或 V/mV 表达手工制作 AVS 专用的 13 列 Replay 文件；保存映射后可用于下一份同结构文件。

这证明了转换和处理链可以自动执行。尚未做新的陌生用户计时实验，不声称节省某个百分比、降低某个比例的操作错误，也不把三个合成文件布局称为三个厂商兼容认证。

## 用户操作与数据契约

Dashboard 新增 **Import data**：选择文件 → 指定时间及电压列 → Check mapping → Publish package → Load imported setup → 原有 Review/Run/报告。检查结果显示每个通道的原单位和前 3 个转换后 mV 数值，帮助发现千倍单位误选。按钮随实际检查、保存、运行状态启用；运行中暂停导入操作，关闭时提示尚未发布的已检查数据。

- UTF-8，可带 BOM；支持逗号、分号、制表符。上限 2 MiB、10,000 行、64 列，每个单元格 1,024 字符。
- 本阶段支持一个电压通道及可选输出通道，V/mV 显式转换成 mV；不猜测列名、物理单位或采集时间。
- 时间来自带时区的 ISO 时间列，或相对秒数加用户提供的真实采集起点。每次复用相对时间模板时必须确认新的采集起点。
- 缺失、非有限、超范围、乱序时间、重复表头和畸形 CSV 明确拒绝，不补零、不丢行、不夹紧数值。错误尽可能定位原始行/列。
- 单通道或不足 3 行生成 READ；至少 3 行输入/输出对生成 DC 配置。两行配对数据仍完整保存，只是初始操作为读取。格式合格不保证数据足以拟合或默认判据适合真实电路。
- 新建五文件导入包：原始 `source.csv`、`mapping.json`、`replay.csv`、`project.json`、`import-manifest.json`。保留原始字节、字段映射和哈希；项目采用包内相对路径。
- 新增 `voltage-import-mapping.v1`、`voltage-import-manifest.v1`；不改变或迁移已有 Replay、项目、结果、系数或运行 manifest。现有 v1–v4 运行历史的读取测试保持通过。
- CLI 新增 `import-csv inspect/convert/verify`；沿用 `product-cli-output.v2`。成功 JSON 在 stdout，错误在 stderr；下游批次进度仍在 stderr。
- 文件和目录发布为 create-new。新导入目录使用 Windows 不替换重命名，或 Linux `renameat2(RENAME_NOREPLACE)`；不支持的系统/文件系统拒绝发布。哈希与重新生成校验只证明内部一致性，不认证采集者、设备或物理准确度。

`afe` 通道/profile 在这里是沿用的逻辑 Replay 契约，不表示必须来自 MSP430 或真实 AFE。本轮没有新依赖，没有引入第二套拟合、判定或报告算法。

## 首次失败与修正

1. 核心与存储测试先因新模块尚未实现失败，再补充最小实现。随后旧 CLI 命令列表的冻结测试发现新增命令；仅向列表和旧 golden 的 `cli_contract` 增加 import-csv 路径，原命令及选项保持一致。
2. 大边界样本自动生成的 pytest 参数 ID 过长，触发 Windows 路径限制；改为简短测试 ID，保留原始边界样本和断言。
3. 最初设计将两行输入/输出生成为 DC。联动检查发现既有 DC 工作流至少需要三个有效点；失败测试复现后改成不足三行先 READ，并保留所有通道数据。原失败日志另行保留。
4. 初次分隔符错误导致未能捕获可解析快照，改分隔符不能直接恢复。界面现明确提示“选择正确分隔符后重新选文件”，在文件区域和状态区域均可见；已有快照仍可直接重解释。
5. 映射名称和项目名称边界不一致，可能导致检查后发布失败；统一为不超过 256 个可打印字符。相对起点固定为字符串契约，模板复用时提示更新真实采集时间。
6. 真实 UI 的短任务可能在断言忙碌状态前完成；测试加入有限时的读取同步门，不以运行速度推断生命周期。产品没有加入人为延迟。
7. 独立安装验收脚本错误使用 `record.outcome`，实际公开字段为 `engineering_outcome`；修正脚本，在新目录完整重跑 23 条命令。首次失败产物保留，软件代码无需修改。
8. 首轮屏幕抓取混用 Windows 逻辑坐标与物理像素，截图被裁切；改为窗口句柄抓取并处理绘制事件。正确截图另存，未据此修改产品布局。

## 真实验收结果

| 检查 | 结果 |
|---|---|
| 完整 pytest | **3,047 passed，88.81 秒，无失败或跳过** |
| 三个正式 package 的 statement coverage | **17,567/17,567，100%**；不是分支覆盖或硬件证明 |
| Ruff | 通过：src、tools、tests、examples/public_adapter |
| mypy | 通过：252 个文件 |
| pip check | 无损坏依赖 |
| API golden | 旧契约回归通过；新 golden 冻结新公开模块、映射、manifest 和三种布局的产物哈希 |
| 产品质量检查 | 15/15：受限 Replay、事件队列、LIVE 缓冲、确定性 demo 等原有门禁通过 |
| 三种文件布局 | 逗号+UTC+V；分号+相对秒数+mV；制表符+重排+混合单位，转换成相同 Replay 字节 |
| 真实 Tk | 1040×760、缩放 1.0/1.5、三种主题、64 列横向滚动、转换数值预览、忙碌禁用和完整导入到报告链通过 |
| 独立安装 CLI | 23 条命令、7 组验收通过；包含中文路径、重复目标拒绝、源文件变化后校验、缺失单元格、包被改动拒绝、批次/历史/报告、stdout/stderr 隔离 |
| 独立安装 GUI | 使用安装后的包重复完整链，通过；保留三主题的窗口截图 |
| 构建及代码一致性 | 505 文件只读源码快照构建 sdist/wheel；全新环境安装；100 个运行层 Python 文件在工作树、wheel 和 site-packages 字节一致 |

这次没有实际运行新的 Linux/Python 版本矩阵或新硬件。Windows 主机结果不替代其他系统、真实串口、长期运行或真人可用性研究。构建后的报告和技术债状态作为验收补充；运行代码与构建包保持一致。

## 文件与 Git

实际工作树仍为 `outputs/.worktrees/calibration-workflow`，分支 `codex/calibration-workflow`，HEAD 保持 `aa1dd5b84dc5494d02b5ec20924527f83fad146e`。

本轮开始的 48 项未提交文件均有逐文件 SHA-256 和字节副本，原成果保留。完成后为 37 个已修改文件、38 个未跟踪文件，共 75 项；最终机器核对记录在外部 `verification.json`。本轮实际新增/增量修改 38 个文件，清单见下方。没有执行 reset、checkout、clean、提交、推送、PR 修改、发布、硬件访问或采购。

## 剩余范围

TD-052 关闭。TD-053 保留通用串口文本、JSON、更多物理量、多通道和设备特定协议；需要真实可解释样本及独立验收后再选下一种输入。当前不支持无时间信息的表格或 Excel 工作簿。屏幕阅读器、UI 运行时迁移、真实硬件验证等原有缺口不因本阶段通过而关闭。

证据分别为：测试与安装检查 **HOST_TEST**；示例原始数据 **SYNTHETIC**；导入运行 **CSV_REPLAY**。本轮新增 **BENCH_CONTROLLER/BENCH = 0**，没有新的 SPICE 结论。软件 PASS 不构成硬件验证。

## 本轮实际文件清单

- CHANGELOG.md
- README.md
- docs/FEATURE_FREEZE.md
- docs/KNOWN_LIMITATIONS.md
- docs/PROJECT_STATUS.md
- docs/TECHNICAL_DEBT.md
- docs/dashboard.md
- docs/phase5-public-api.md
- docs/product-cli.md
- docs/voltage-data-import.md
- examples/voltage-import/README.md
- examples/voltage-import/synthetic-comma-utc-v.csv
- examples/voltage-import/synthetic-comma-utc-v.mapping.json
- examples/voltage-import/synthetic-semicolon-elapsed-mv.csv
- examples/voltage-import/synthetic-semicolon-elapsed-mv.mapping.json
- examples/voltage-import/synthetic-tab-reordered-mixed.csv
- examples/voltage-import/synthetic-tab-reordered-mixed.mapping.json
- reports/td-052-voltage-import-2026-09-09.md
- src/analog_validation_app/atomic_directory.py
- src/analog_validation_app/cli.py
- src/analog_validation_app/dashboard/app.py
- src/analog_validation_app/dashboard/import_page.py
- src/analog_validation_app/import_cli.py
- src/analog_validation_app/import_packages.py
- src/analog_validation_app/tabular_import.py
- test-data/golden/phase5_public_api.json
- test-data/golden/voltage_import_v1.json
- tests/golden/test_voltage_import_golden.py
- tests/integration/test_dashboard_import_workflow.py
- tests/unit/test_atomic_directory.py
- tests/unit/test_dashboard_import_app.py
- tests/unit/test_dashboard_import_page.py
- tests/unit/test_dashboard_product_actions.py
- tests/unit/test_dashboard_projects.py
- tests/unit/test_import_cli.py
- tests/unit/test_import_packages.py
- tests/unit/test_product_cli.py
- tests/unit/test_tabular_import.py
