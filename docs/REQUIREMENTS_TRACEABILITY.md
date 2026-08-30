# 产品需求追踪矩阵

**基准：** `docs/PRODUCT_PLAN.md` v1.0  
**更新日期：** 2026-08-29  
**当前阶段：** Software Phase 1 Step 4 完成

状态含义遵循产品规划书：`ACCEPTED`、`IMPLEMENTED`、`VERIFIED_HOST`、`VERIFIED_BENCH`、`DEFERRED`。`IMPLEMENTED` 只表示存在部分代码，不表示达到完整验收标准。

## 软件功能需求

| ID | 状态 | 当前实现/证据 | 主要缺口或下一阶段 |
|---|---|---|---|
| SW-FR-001 | VERIFIED_HOST | `Measurement` 包含 UTC 时间、通道、值、单位、状态、来源、质量和 schema；边界测试通过 | Step 8 接入黄金数据 |
| SW-FR-002 | VERIFIED_HOST | `TestRunMetadata` 保存测试、配置、UTC 时间、软件、设备/profile 和来源；`TestRunResult` 保存结论与证据 | Phase 3 runner 生成实际运行记录 |
| SW-FR-003 | IMPLEMENTED | 9 类受控 `EvidenceSource` 已验证且每个正式 Measurement 必填 | Step 8 迁移生成器；Phase 3/5 写入导出和报告 |
| SW-FR-004 | IMPLEMENTED | Measurement 冻结且强制 `record_id`/`raw_record_id`，可区分原始与派生 | Phase 3 分析结果保存实际引用链 |
| SW-FR-005 | VERIFIED_HOST | 12 类受控单位；未知单位和含义不明值被拒绝 | 后续 profile 映射保持显式单位 |
| SW-FR-010 | VERIFIED_HOST | `crc16_ccitt_false`；`tests/test_crc.py` | Phase 1 拆为独立稳定模块并增加向量 |
| SW-FR-011 | VERIFIED_HOST | 128-byte 限制、换行和 CRLF 测试 | Phase 4 增加流式分帧 |
| SW-FR-012 | VERIFIED_HOST | 严格 telemetry/command parser 和错误测试 | Phase 1 扩展版本化消息和黄金文件 |
| SW-FR-013 | ACCEPTED | 无序列追踪 | Phase 1 定义语义，Phase 4 实现 transport tracker |
| SW-FR-014 | ACCEPTED | 无协议版本 | Phase 1 定义 AFE v1 envelope/profile |
| SW-FR-015 | IMPLEMENTED | `DeviceCapabilities` 已定义 ADC/DAC/PWM/数字输入、安全范围、命令和 schema，并通过主机边界测试 | Step 6 定义线上形状；Phase 2/4 实现协商 |
| SW-FR-016 | ACCEPTED | `serial_worker.py` 占位 | Phase 4 实现有限重试和错误恢复 |
| SW-FR-017 | ACCEPTED | 无原始帧日志模型 | Phase 1 定义，Phase 4 实现 |
| SW-FR-020 | ACCEPTED | 无 DeviceAdapter | Phase 2 实现契约和契约测试 |
| SW-FR-021 | IMPLEMENTED | `tools/telemetry_simulator.py` | Phase 2 迁移为可注入故障的 SimulatorAdapter |
| SW-FR-022 | ACCEPTED | 无 CSV replay | Phase 2 实现 |
| SW-FR-023 | ACCEPTED | 串口占位文件 | Phase 4 实现且隔离分析层 |
| SW-FR-024 | ACCEPTED | 无 MSP430 profile | Phase 4 独立实现，保留原始字段 |
| SW-FR-025 | IMPLEMENTED | `UNSUPPORTED` 结果语义已建立且必须列出缺失能力 | Phase 2 adapter/runner 实际生成降级结果 |
| SW-FR-026 | ACCEPTED | 无安全关闭 | Phase 2 定义，输出型硬件接入时验证 |
| SW-FR-030 | IMPLEMENTED | 合成 sweep generator | Phase 3 建立 runner、等待、重复和运行记录 |
| SW-FR-031 | VERIFIED_HOST | `linear_fit` 与 2 项核心拟合测试 | Phase 3 增加残差、有限值和质量信息 |
| SW-FR-032 | IMPLEMENTED | `exclude_saturated` 和测试 | Phase 3 保存逐点排除原因并配置化 |
| SW-FR-033 | VERIFIED_HOST | `calculate_hysteresis` 和 3 项测试 | Phase 3 增加方向、状态和重复统计 |
| SW-FR-034 | ACCEPTED | `calibration.py` 占位 | Phase 3 实现版本化系数和前后结果 |
| SW-FR-035 | ACCEPTED | `frequency_response.py` 占位 | Phase 3 先实现离线分析 |
| SW-FR-036 | IMPLEMENTED | 缺失、非有限、饱和、超范围、时间和通信质量标志已建立；一致性测试通过 | Phase 3 将规则用于分析和判定 |
| SW-FR-037 | IMPLEMENTED | 领域模型强制 PASS/FAIL 具备证据且无缺失项；INCOMPLETE/UNSUPPORTED 不能成为 PASS | Phase 3 实现版本化判定引擎 |
| SW-FR-038 | IMPLEMENTED | 当前纯函数和固定 seed 可重复 | Phase 2/3 加端到端确定性测试 |
| SW-FR-040 | IMPLEMENTED | 两个工具有 argparse | Phase 5 建立统一产品 CLI |
| SW-FR-041 | ACCEPTED | `app.py` 仅占位 | Phase 5 实现 Dashboard |
| SW-FR-042 | ACCEPTED | 无测试向导 | Phase 5 实现 |
| SW-FR-043 | ACCEPTED | `csv_export.py` 占位 | Phase 3 实现结构化导出 |
| SW-FR-044 | ACCEPTED | 无 JSON 摘要 | Phase 3 实现 |
| SW-FR-045 | ACCEPTED | `summary.py` 占位 | Phase 5 实现证据和限制说明 |
| SW-FR-046 | IMPLEMENTED | 正式包公开 9 类稳定错误；继承、消息和异常链测试通过 | Step 5 迁移协议错误；Phase 5 增加用户操作指导 |

## 软件非功能需求

| ID | 状态 | 当前实现/证据 | 主要缺口或下一阶段 |
|---|---|---|---|
| SW-NFR-001 | VERIFIED_HOST | `src` 布局、editable install、隔离构建、仓库外 wheel 安装和 import 均通过 | Phase 5 增加最终用户运行入口，Phase 6 再做发布候选安装测试 |
| SW-NFR-002 | IMPLEMENTED | 当前核心使用标准 Python | Phase 4/6 验证 Windows，避免核心平台绑定 |
| SW-NFR-003 | ACCEPTED | parser 可拒绝部分坏输入 | 设备、文件、中止和安全状态仍未实现 |
| SW-NFR-004 | VERIFIED_HOST | 协议和分析可无硬件单测 | Phase 1 保持依赖反转并扩展契约测试 |
| SW-NFR-005 | ACCEPTED | 仅有架构文档 | Phase 1/2 建立可执行边界 |
| SW-NFR-006 | IMPLEMENTED | `src` 正式包、版本和公开错误 API 均有类型、文档与测试 | 领域、协议和配置模块仍待迁移 |
| SW-NFR-007 | ACCEPTED | 无性能基准 | Phase 5/6 建立实际数据规模基准 |
| SW-NFR-008 | IMPLEMENTED | 帧长度、ASCII 和数值有验证 | 配置、路径、文件和命令尚未覆盖 |
| SW-NFR-009 | IMPLEMENTED | 当前无网络代码，文件均本地 | Phase 5 文档化并保持默认离线 |
| SW-NFR-010 | ACCEPTED | 报告未实现 | Phase 1 定义版本字段，Phase 3/5 写入结果 |
| SW-NFR-011 | ACCEPTED | 无 UI | Phase 5 验证文本与颜色双重表达 |
| SW-NFR-012 | IMPLEMENTED | Measurement schema 固定为 `measurement.v1`，未知版本拒绝 | Step 5/6 增加协议/profile 版本与黄金测试 |

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
| VERIFIED_HOST | 6 |
| IMPLEMENTED | 13 |
| ACCEPTED | 29 |
| DEFERRED | 12 |
| VERIFIED_BENCH | 0 |
| 总计 | 60 |

Software Phase 1 的重点不是增加很多功能，而是把已有原型迁移到可版本化、可测试、可扩展的正式核心，使 SW-FR-001/002/005/014/015/036 和 SW-NFR-001/006/010/012 获得可执行基础。
