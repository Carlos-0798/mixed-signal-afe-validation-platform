# 项目接续点：求职准备期间暂停功能扩展

**留档日期：** 2026-09-09<br>
**当前版本：** `0.1.0b1`，已完成当前软件范围的本地交付验收，尚未正式发布<br>
**当前任务：** 保存接续点 → 同步私有 GitHub 开发分支和现有 Draft PR → 求职材料准备<br>
**恢复原则：** 从本文、当前 Git 状态和最新验收证据继续，不依赖聊天窗口显示的位置。

## 1. 项目方向和实际暂停点

Analog Validation Studio 是独立、控制器中立的 Python 验证软件。当前主要场景是
重复处理已有模拟信号链的电压数据，将输入准备、DC 增益/偏置/线性度分析、批次、
结果追溯和报告串成可以重复运行的流程。CLI 和桌面界面共用正式核心与工作流。
MSP430 Equipment Health Controller 与 OSU Lab Bench Monitor 均是独立项目。

最后完成的是 **TD-052 通用电压文件导入**。现在暂停新增业务功能，转入私有仓库
同步和求职展示。此前讨论的“更多来源可接入”并未取消，但没有承诺自动兼容任意板卡，
也没有开始 TD-053 的实现。完成求职准备后再根据真实输入样本决定下一小阶段。

## 2. 已完成，不重复实施

- 控制器中立的数据、能力、adapter、协议 profile 和证据契约；Simulator、严格 CSV
  Replay、显式配置的接收型串口路径。串口新功能以 HOST_TEST 为主，不新增实物结论。
- READ、有界 LIVE、DC、迟滞、线性校准和幅频响应；正式分析、规范结果与人类报告。
- 可复用项目/预设、逐预设真实进度、协作取消、cleanup、部分成果保留和项目历史。
  新运行 manifest v4 可表达后续准备失败，v1–v3 保持严格读取，历史产物不迁移。
- **TD-050：** Workbench、Daylight、Midnight 三主题，窗口内切换和文字可读性改进。
- **TD-051：** 预设复制载入 Setup 并重新 Review、GUI 完整报告包、逐次读取取消检查、
  后续预设失败时保留先前结果。
- **TD-052：** 显式列/单位/时间映射、可复用 JSON 模板、转换后 mV 预览，CLI
  `import-csv inspect/convert/verify` 和 Dashboard Import data 接入同一分析链。
- 导入包保留 `source.csv`、`mapping.json`、`replay.csv`、`project.json` 和
  `import-manifest.json`；create-new、原子发布、不覆盖、SHA-256 和重新生成校验。

TD-052 的范围是 UTF-8 电压表格：逗号/分号/制表符，V/mV，一个输入通道及可选输出
通道；带时区时间戳，或相对秒数加实际采集起点。上限为 2 MiB、10,000 行、64 列。
不猜单位、列含义或采集时间，不把格式通过等同于判据合理。

## 3. 暂停时的验证证据

| 证据 | 已记录结果 |
|---|---|
| 完整 pytest | 3,047 passed，0 failed，0 skipped，88.81 秒 |
| 三个正式 package 的语句覆盖 | 17,567/17,567，100%；不是分支覆盖 |
| 静态与依赖检查 | Ruff、mypy（252 文件）、pip check、git diff --check 通过 |
| 产品质量门禁 | 15/15 通过 |
| 独立安装验收 | 23 条 CLI 命令、7 组场景，安装后的真实 Tk 主链通过 |
| 数据转换 | 三种 SYNTHETIC 表格布局生成相同 Replay 字节 |
| 构建一致性 | 100 个运行层 Python 文件在工作树、wheel、site-packages 字节一致 |

以上是 [TD-052 本地验收](../reports/td-052-voltage-import-2026-09-09.md) 的历史记录，
不是自动更新的 CI 状态。GitHub 同步后的结果须查看 [现有 PR #10](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/pull/10)
对应的提交和 Actions；旧提交的成功不能代替新提交验证。不得为追求相同数字删除新测试。

证据分类：测试/安装为 **HOST_TEST**，示例为 **SYNTHETIC**，导入后的运行是
**CSV_REPLAY**。本次新增 **BENCH_CONTROLLER/BENCH = 0**，没有新的 SPICE 结论。
既有 MSP430 UART 兼容性证据不证明 AFE 性能；软件 PASS 不构成硬件验证。
真人效率基准尚未执行，不写节省时间或降低错误率的百分比。

同步准备补充 1 项跨平台测试后，完整本地门禁为 **3,048 passed、17,567/17,567
statements**，运行代码不变。详见 [私有同步报告](../reports/private-github-sync-2026-09-09.md)。

## 4. Git 与恢复入口

- 实际工作树位置：AVS 主目录下 `outputs/.worktrees/calibration-workflow`。
- 分支：`codex/calibration-workflow`；远程仓库：
  `Carlos-0798/mixed-signal-afe-validation-platform`。
- 同步前本地 HEAD：`aa1dd5b84dc5494d02b5ec20924527f83fad146e`。
- 同步前远程 PR head：`bf8c4c6f59ba9063524aea7db01df87d35170483`；main：
  `158e752e9365ed10b90bcdb5cc419fd692dada2b`。
- 同步前 37 个已修改文件 + 38 个未跟踪文件 = 75 项未提交文件。
  它们是已验收成果，不是临时垃圾；本次同步将这些成果纳入后续提交。
- 同步前已另存全部 506 个项目文件、逐文件 SHA-256、Git 状态及 HEAD 历史 bundle。
  本机完整路径、后续提交和验证回执保存在工作树外的 `avs-github-sync-20260909-01`。
  既有演练、构建、首次失败日志、安装环境与验收目录全部保留。

恢复工作时先只读检查：

```powershell
git branch --show-current
git status --short
git log -5 --oneline
git remote -v
.venv\Scripts\python.exe -c "import analog_validation_app; print(analog_validation_app.__file__)"
```

确认导入来自当前工作树，阅读最新同步回执与 PR。本文的同步前 SHA 和 75 项计数是
历史定位信息，不能用它们强行回退后来的合法提交。发现其他未提交改动时先保留和辨认。
不要 reset、checkout、clean、重写历史或从旧仓库覆盖开始。

## 5. 求职准备结束后的路线

1. **先看真实任务是否被阻断。** 用一份实际可解释的电压文件重复“导入→检查映射→
   Review→分析/批次→报告→历史验证”。只有新问题或新需求才安排修改，不重做已通过的
   主题、引导、报告或导入功能。
2. **TD-053 按样本选一种输入。** 收集列名、单位、时间格式、通道含义和来源限制，
   优先选择现有用户确实会重复处理的格式。若普通 CSV 已能满足，不增加新适配器。
   通用串口文本/JSON、更多物理量、多通道、设备二进制协议是候选方向，不是同时开工清单。
3. **冻结最小契约后再实现。** 显式 parser/profile → 标准测量或 Replay → 原工作流，
   复用分析和报告。先写合法/畸形/截断/乱序/单位/边界测试，再完成最小实现。
4. **验收并收敛。** 旧格式读取、原子不覆盖、取消和 cleanup、CLI JSON/stderr、
   Dashboard 主链、完整 pytest/statement coverage、静态检查和安装验证。兼容性声明
   只列实际验证的格式/协议/设备及对应证据等级。

继续后置：READ/LIVE 全量原始数据持久化、归档输入一键重跑、曲线叠加、签名和身份认证、
云服务/多人协作、UI 框架迁移。屏幕阅读器限制仍记录在 TD-043B2A，按原决定暂缓迁移。
真实串口断连/长时间运行及 AFE/仪器验证必须作为单独授权和验收的阶段。
完整清单见 [技术债](TECHNICAL_DEBT.md) 与 [已知限制](KNOWN_LIMITATIONS.md)。

## 6. 本次同步授权与停止条件

2026-09-09 所有者明确授权：先留档，再开始此前讨论的 GitHub 同步，进度对齐后再评估公开。
本次可整理当前成果、提交并推送既有开发分支、更新现有 Draft PR 的标题/说明并核对 CI。
仓库保持私有；不把这些动作解释为 Ready、合并、删除分支、tag、Release、包发布、
可见性/许可证/历史修改、LinkedIn 发帖或访问硬件的授权。

同步阶段结束时应有：本地与远程开发分支 SHA 对齐、包含当前功能的 Draft PR、真实 CI
结果或明确的阻塞说明、完整接续文档。main 在单独批准合并前仍是旧版本；预览请使用
开发分支 README。之后集中完成求职准备，等待下一次项目优化或公开决定。

## 7. 后续决定：本地优先，云端仅手动

所有者随后明确选择“本地测试为主，云端测试仅手动触发”。该决定优先于此前
“账户问题解决后继续重跑 CI”的计划：不得自行重跑或新增自动云端触发。
保留本地验证记录和历史被阻塞的 Actions 结果；云端复验不再是日常同步或求职展示前提。
需要额外跨平台证据时，再由所有者选择具体分支/提交并明确启动。

当前开发分支与 main 的 CI 配置仅保留 `workflow_dispatch`；main 的配置更新不表示
产品功能已合并。操作方法和历史分支恢复边界见 [本地测试与手动 CI](LOCAL_TESTING_AND_CI.md)。
