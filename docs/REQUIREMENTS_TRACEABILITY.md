# 产品需求追踪矩阵

**基准：** `docs/PRODUCT_PLAN.md` v1.0  
**更新日期：** 2026-08-30<br>
**当前阶段：** Software Phase 2 完成（8/8）

状态含义遵循产品规划书：`ACCEPTED`、`IMPLEMENTED`、`VERIFIED_HOST`、`VERIFIED_BENCH`、`DEFERRED`。`IMPLEMENTED` 只表示存在部分代码，不表示达到完整验收标准。

## 软件功能需求

| ID | 状态 | 当前实现/证据 | 主要缺口或下一阶段 |
|---|---|---|---|
| SW-FR-001 | VERIFIED_HOST | `Measurement` 包含 UTC 时间、通道、值、单位、状态、来源、质量和 schema；100 帧流水线生成 400 条显式来源测量 | Phase 3 runner 使用正式模型 |
| SW-FR-002 | VERIFIED_HOST | `TestRunMetadata` 保存测试、配置、UTC 时间、软件、设备/profile 和来源；`TestRunResult` 保存结论与证据 | Phase 3 runner 生成实际运行记录 |
| SW-FR-003 | VERIFIED_HOST | 9 类受控 `EvidenceSource` 已验证且每个正式 Measurement 必填；100 帧集成测试确认 400 条记录均为 `SYNTHETIC` 且非 BENCH | Phase 3/5 写入导出和报告 |
| SW-FR-004 | IMPLEMENTED | Measurement 冻结且强制 `record_id`/`raw_record_id`，可区分原始与派生 | Phase 3 分析结果保存实际引用链 |
| SW-FR-005 | VERIFIED_HOST | 12 类受控单位；Measurement、profile 和配置通道均拒绝未知或含义不明单位 | 后续 adapter 和分析保持显式单位 |
| SW-FR-010 | VERIFIED_HOST | CRC 只有 `protocol/crc.py` 一个实现；固定参数、5 个黄金向量和 bytes-like 边界测试通过 | 后续 profile/adapter 复用，不再复制算法 |
| SW-FR-011 | VERIFIED_HOST | 正式 framing 实现 128-byte 上限、严格可打印 ASCII token、LF/CRLF、CRC envelope 和精确错误；边界测试通过 | Phase 4 增加流式分帧和超长恢复状态机 |
| SW-FR-012 | VERIFIED_HOST | AFE v1 严格解析和错误分类通过单元测试，并由 20 条合法、9 类非法黄金消息冻结 | Phase 4 流式 parser 复用相同业务 parser |
| SW-FR-013 | ACCEPTED | 无序列追踪 | Phase 1 定义语义，Phase 4 实现 transport tracker |
| SW-FR-014 | VERIFIED_HOST | AFE profile name=`afe`、wire version=`1`；黄金坏版本记录稳定抛出 `UnsupportedProtocolVersion` | Phase 4 在连接握手中应用 |
| SW-FR-015 | IMPLEMENTED | 多记录 CAP_REQ/CAP DEVICE/CHANNEL/END 已定义并可与 `DeviceCapabilities` 往返；未知 bit、序号和数量不一致被拒绝 | Phase 2/4 adapter 实际协商 |
| SW-FR-016 | ACCEPTED | `serial_worker.py` 占位 | Phase 4 实现有限重试和错误恢复 |
| SW-FR-017 | ACCEPTED | 无原始帧日志模型 | Phase 1 定义，Phase 4 实现 |
| SW-FR-020 | VERIFIED_HOST | 正式 `DeviceAdapter` 已定义统一接口；reference、Simulator 和 CSV Replay 均通过同一套 8 项只读契约；`run_read_workflow` 已用同一请求实际驱动两个正式适配器 | Phase 4 让 Serial 适配器通过相同契约和工作流 |
| SW-FR-021 | VERIFIED_HOST | 版本化只读 SimulatorAdapter 已验证增益、偏置、确定性噪声、上下限饱和、Schmitt 迟滞、缺失样本、通信错误和 CRC 错误；所有记录保持 `SYNTHETIC` | Phase 3 runner 使用该适配器执行完整工作流 |
| SW-FR-022 | VERIFIED_HOST | `csv-replay.v1` 提供不可变 dataset/record 与严格 parser；正式 `CsvReplayAdapter` 已验证顺序读取、独立通道游标、速度、暂停/恢复、明确 EOF、原引用保留和强制 `CSV_REPLAY` 来源；共享工作流已消费回放 | Phase 5 UI 增加用户控制 |
| SW-FR-023 | ACCEPTED | 串口占位文件 | Phase 4 实现且隔离分析层 |
| SW-FR-024 | ACCEPTED | 无 MSP430 profile | Phase 4 独立实现，保留原始字段 |
| SW-FR-025 | VERIFIED_HOST | 共享工作流在任何读取前原子检查命令、通道和单位；缺失能力返回无部分数据且列明缺口的 `UNSUPPORTED`；Replay 提前 EOF 单独返回 `INCOMPLETE` | Phase 3 runner 将采集状态映射到正式 TestRunResult |
| SW-FR-026 | IMPLEMENTED | AFE v1 定义 SAFE_SHUTDOWN command；自动输出验证强制声明该能力 | Phase 2 adapter 实现；输出型硬件接入时做 fault/bench 验证 |
| SW-FR-030 | IMPLEMENTED | 合成 sweep generator | Phase 3 建立 runner、等待、重复和运行记录 |
| SW-FR-031 | VERIFIED_HOST | `linear_fit` 与 2 项核心拟合测试 | Phase 3 增加残差、有限值和质量信息 |
| SW-FR-032 | IMPLEMENTED | `exclude_saturated` 和测试 | Phase 3 保存逐点排除原因并配置化 |
| SW-FR-033 | VERIFIED_HOST | `calculate_hysteresis` 和 3 项测试 | Phase 3 增加方向、状态和重复统计 |
| SW-FR-034 | ACCEPTED | `calibration.py` 占位 | Phase 3 实现版本化系数和前后结果 |
| SW-FR-035 | ACCEPTED | `frequency_response.py` 占位 | Phase 3 先实现离线分析 |
| SW-FR-036 | IMPLEMENTED | 缺失、非有限、饱和、超范围、时间和通信质量标志已建立；Simulator 实际生成 `SATURATED` 及缺失/通信组合并通过一致性测试 | Phase 3 将规则用于分析和判定 |
| SW-FR-037 | IMPLEMENTED | 领域模型强制 PASS/FAIL 具备证据且无缺失项；INCOMPLETE/UNSUPPORTED 不能成为 PASS | Phase 3 实现版本化判定引擎 |
| SW-FR-038 | VERIFIED_HOST | 固定 seed 的 100 帧 AFE 流水线保持冻结 SHA-256；同配置/clock 的输入、带噪输出、迟滞和故障序列可重复，且各通道读取顺序互不干扰 | Phase 3 扩展到 runner 端到端测试 |
| SW-FR-040 | IMPLEMENTED | 两个工具有 argparse | Phase 5 建立统一产品 CLI |
| SW-FR-041 | ACCEPTED | `app.py` 仅占位 | Phase 5 实现 Dashboard |
| SW-FR-042 | ACCEPTED | 无测试向导 | Phase 5 实现 |
| SW-FR-043 | ACCEPTED | `csv_export.py` 占位 | Phase 3 实现结构化导出 |
| SW-FR-044 | ACCEPTED | 无 JSON 摘要 | Phase 3 实现 |
| SW-FR-045 | ACCEPTED | `summary.py` 占位 | Phase 5 实现证据和限制说明 |
| SW-FR-046 | IMPLEMENTED | 正式包公开稳定领域/协议/配置/adapter/replay 错误；黄金坏消息冻结 CRC、长度、framing、协议版本、业务协议和 replay 格式/版本错误家族；回放 EOF 使用独立 `ReplayEndOfData` | Phase 5 增加面向用户的操作指导 |

## 软件非功能需求

| ID | 状态 | 当前实现/证据 | 主要缺口或下一阶段 |
|---|---|---|---|
| SW-NFR-001 | VERIFIED_HOST | `src` 布局、editable install、隔离构建、仓库外 wheel 安装和 import 均通过 | Phase 5 增加最终用户运行入口，Phase 6 再做发布候选安装测试 |
| SW-NFR-002 | IMPLEMENTED | 当前核心使用标准 Python | Phase 4/6 验证 Windows，避免核心平台绑定 |
| SW-NFR-003 | IMPLEMENTED | framing/profile/config/replay parser 拒绝坏输入；adapter 状态机拒绝越级 I/O；CSV 回放暂停不消耗记录、EOF 类型明确；共享工作流在 success/unsupported/incomplete/error 后均断开自己拥有的 adapter | 真实断线、用户中止和串口恢复仍未实现 |
| SW-NFR-004 | VERIFIED_HOST | 单元、黄金、架构、100 帧、adapter 契约和共用 workflow 测试均无需硬件；同一 workflow 已分别运行 Simulator 与 CSV Replay | Phase 3 runner 继续使用依赖注入 |
| SW-NFR-005 | VERIFIED_HOST | `tests/architecture/test_core_dependencies.py` 可执行地禁止正式核心导入第三方、串口、GUI、板级 SDK、dashboard 或 tools；Phase 2 workflow 保持 adapter 依赖方向 | Phase 3 runner 继续受同一边界保护 |
| SW-NFR-006 | VERIFIED_HOST | 正式领域、协议与配置模块责任分离，公开 API 有类型、文档与完整 host tests | Phase 2 继续保持 adapter 依赖方向 |
| SW-NFR-007 | ACCEPTED | 无性能基准 | Phase 5/6 建立实际数据规模基准 |
| SW-NFR-008 | VERIFIED_HOST | 严格 JSON 与 CSV 只作为数据解析；CSV 拒绝坏 UTF-8/BOM/NUL/控制字符/非规范值/超限/不完整 END，loader 测试确认不修改源文件；无 `eval`/`exec` | Phase 5 扩展到 CLI 路径和命令入口 |
| SW-NFR-009 | IMPLEMENTED | 当前无网络代码，文件均本地 | Phase 5 文档化并保持默认离线 |
| SW-NFR-010 | ACCEPTED | 报告未实现 | Phase 1 定义版本字段，Phase 3/5 写入结果 |
| SW-NFR-011 | ACCEPTED | 无 UI | Phase 5 验证文本与颜色双重表达 |
| SW-NFR-012 | VERIFIED_HOST | Measurement、capability、TestRun、AFE profile 和配置均显式版本化；AFE v1 wire/model 意义由黄金文件冻结 | 未来格式变化必须增加版本和迁移说明 |

## 未来硬件需求

| ID | 状态 | 当前实现/证据 | 入口条件 |
|---|---|---|---|
| HW-FR-001 | DEFERRED | 只有理论与规格 | 软件 Phase 2/3 完成并冻结采购 |
| HW-FR-002 | DEFERRED | 只有保护设计目标 | 器件型号、原理图和安全评审 |
| HW-FR-003 | DEFERRED | 只有理想 SPICE/理论 | 面包板和 BENCH_DMM |
| HW-FR-004 | DEFERRED | 只有拟合软件与理想结果 | 多档真实 DC sweep |
| HW-FR-005 | DEFERRED | 只有 RC 理论/理想 SPICE | 合适信号源与示波器权限 |
| HW-FR-006 | DEFERRED | 只有迟滞算法/理想 SPICE | 比较器实物和重复测量 |
| HW-FR-007 | DEFERRED | 未采购 ADC | 参考源和对照测量计划 |
| HW-FR-008 | DEFERRED | 架构目标 | 无 MCU 手动模式原型 |
| HW-FR-009 | DEFERRED | 软件适配器尚未完成 | 软件 v1 和参考控制器 |
| HW-FR-010 | DEFERRED | 只有兼容性设计 | 独立 MSP430 profile 与实物接线 |
| HW-FR-011 | DEFERRED | 只有安全规则 | 断电、上电和拔除控制器检查 |
| HW-FR-012 | DEFERRED | 只有接口原则 | 原理图、测试点和丝印评审 |

## 汇总

| 状态 | 数量 |
|---|---:|
| VERIFIED_HOST | 21 |
| IMPLEMENTED | 12 |
| ACCEPTED | 15 |
| DEFERRED | 12 |
| VERIFIED_BENCH | 0 |
| 总计 | 60 |

Software Phase 1 已完成版本化、可测试、无硬件依赖的正式核心。Software Phase 2 已完成 8/8：公共 adapter 契约、可配置模拟器、严格 CSV Replay、正式 CsvReplayAdapter、共用读取工作流、明确能力降级，以及 API/端到端黄金兼容冻结均通过主机验证。下一步是 Software Phase 3 分析与 runner 规划；硬件仍为 DEFERRED，VERIFIED_BENCH 仍为 0。
