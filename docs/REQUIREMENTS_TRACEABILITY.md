# 产品需求追踪矩阵

**基准：** `docs/PRODUCT_PLAN.md` v1.0  
**更新日期：** 2026-08-29  
**当前阶段：** Software Phase 0 审计完成  

状态含义遵循产品规划书：`ACCEPTED`、`IMPLEMENTED`、`VERIFIED_HOST`、`VERIFIED_BENCH`、`DEFERRED`。`IMPLEMENTED` 只表示存在部分代码，不表示达到完整验收标准。

## 软件功能需求

| ID | 状态 | 当前实现/证据 | 主要缺口或下一阶段 |
|---|---|---|---|
| SW-FR-001 | ACCEPTED | `dashboard/models.py` 有有限的 Telemetry | Phase 1 建立通用 Measurement、来源和质量字段 |
| SW-FR-002 | ACCEPTED | 无 TestRun 模型 | Phase 1 建立版本化运行元数据 |
| SW-FR-003 | IMPLEMENTED | 两个生成工具标记 `SYNTHETIC` | 标签进入每条领域记录和报告 |
| SW-FR-004 | ACCEPTED | 无原始/派生数据关系 | Phase 1 设计 immutable 原始记录和派生引用 |
| SW-FR-005 | IMPLEMENTED | 字段名含 `_mv` | Phase 1 增加明确单位模型/字段约束 |
| SW-FR-010 | VERIFIED_HOST | `crc16_ccitt_false`；`tests/test_crc.py` | Phase 1 拆为独立稳定模块并增加向量 |
| SW-FR-011 | VERIFIED_HOST | 128-byte 限制、换行和 CRLF 测试 | Phase 4 增加流式分帧 |
| SW-FR-012 | VERIFIED_HOST | 严格 telemetry/command parser 和错误测试 | Phase 1 扩展版本化消息和黄金文件 |
| SW-FR-013 | ACCEPTED | 无序列追踪 | Phase 1 定义语义，Phase 4 实现 transport tracker |
| SW-FR-014 | ACCEPTED | 无协议版本 | Phase 1 定义 AFE v1 envelope/profile |
| SW-FR-015 | ACCEPTED | 无能力协商 | Phase 1 定义 Capability，Phase 2/4 实现 |
| SW-FR-016 | ACCEPTED | `serial_worker.py` 占位 | Phase 4 实现有限重试和错误恢复 |
| SW-FR-017 | ACCEPTED | 无原始帧日志模型 | Phase 1 定义，Phase 4 实现 |
| SW-FR-020 | ACCEPTED | 无 DeviceAdapter | Phase 2 实现契约和契约测试 |
| SW-FR-021 | IMPLEMENTED | `tools/telemetry_simulator.py` | Phase 2 迁移为可注入故障的 SimulatorAdapter |
| SW-FR-022 | ACCEPTED | 无 CSV replay | Phase 2 实现 |
| SW-FR-023 | ACCEPTED | 串口占位文件 | Phase 4 实现且隔离分析层 |
| SW-FR-024 | ACCEPTED | 无 MSP430 profile | Phase 4 独立实现，保留原始字段 |
| SW-FR-025 | ACCEPTED | 无 capability 降级逻辑 | Phase 2 实现 `UNSUPPORTED` |
| SW-FR-026 | ACCEPTED | 无安全关闭 | Phase 2 定义，输出型硬件接入时验证 |
| SW-FR-030 | IMPLEMENTED | 合成 sweep generator | Phase 3 建立 runner、等待、重复和运行记录 |
| SW-FR-031 | VERIFIED_HOST | `linear_fit` 与 2 项核心拟合测试 | Phase 3 增加残差、有限值和质量信息 |
| SW-FR-032 | IMPLEMENTED | `exclude_saturated` 和测试 | Phase 3 保存逐点排除原因并配置化 |
| SW-FR-033 | VERIFIED_HOST | `calculate_hysteresis` 和 3 项测试 | Phase 3 增加方向、状态和重复统计 |
| SW-FR-034 | ACCEPTED | `calibration.py` 占位 | Phase 3 实现版本化系数和前后结果 |
| SW-FR-035 | ACCEPTED | `frequency_response.py` 占位 | Phase 3 先实现离线分析 |
| SW-FR-036 | ACCEPTED | 仅有部分 parser range check | Phase 1 建立 QualityFlag，Phase 3 应用 |
| SW-FR-037 | ACCEPTED | 无判定引擎 | Phase 3 实现，缺数据不得 PASS |
| SW-FR-038 | IMPLEMENTED | 当前纯函数和固定 seed 可重复 | Phase 2/3 加端到端确定性测试 |
| SW-FR-040 | IMPLEMENTED | 两个工具有 argparse | Phase 5 建立统一产品 CLI |
| SW-FR-041 | ACCEPTED | `app.py` 仅占位 | Phase 5 实现 Dashboard |
| SW-FR-042 | ACCEPTED | 无测试向导 | Phase 5 实现 |
| SW-FR-043 | ACCEPTED | `csv_export.py` 占位 | Phase 3 实现结构化导出 |
| SW-FR-044 | ACCEPTED | 无 JSON 摘要 | Phase 3 实现 |
| SW-FR-045 | ACCEPTED | `summary.py` 占位 | Phase 5 实现证据和限制说明 |
| SW-FR-046 | IMPLEMENTED | ProtocolError 有可读消息 | Phase 1 错误分类，Phase 5 用户指导 |

## 软件非功能需求

| ID | 状态 | 当前实现/证据 | 主要缺口或下一阶段 |
|---|---|---|---|
| SW-NFR-001 | VERIFIED_HOST | `src` 布局、editable install、隔离构建、仓库外 wheel 安装和 import 均通过 | Phase 5 增加最终用户运行入口，Phase 6 再做发布候选安装测试 |
| SW-NFR-002 | IMPLEMENTED | 当前核心使用标准 Python | Phase 4/6 验证 Windows，避免核心平台绑定 |
| SW-NFR-003 | ACCEPTED | parser 可拒绝部分坏输入 | 设备、文件、中止和安全状态仍未实现 |
| SW-NFR-004 | VERIFIED_HOST | 协议和分析可无硬件单测 | Phase 1 保持依赖反转并扩展契约测试 |
| SW-NFR-005 | ACCEPTED | 仅有架构文档 | Phase 1/2 建立可执行边界 |
| SW-NFR-006 | IMPLEMENTED | dataclass、类型提示和小模块 | 缺公共 API 版本、完整文档和 src 分层 |
| SW-NFR-007 | ACCEPTED | 无性能基准 | Phase 5/6 建立实际数据规模基准 |
| SW-NFR-008 | IMPLEMENTED | 帧长度、ASCII 和数值有验证 | 配置、路径、文件和命令尚未覆盖 |
| SW-NFR-009 | IMPLEMENTED | 当前无网络代码，文件均本地 | Phase 5 文档化并保持默认离线 |
| SW-NFR-010 | ACCEPTED | 报告未实现 | Phase 1 定义版本字段，Phase 3/5 写入结果 |
| SW-NFR-011 | ACCEPTED | 无 UI | Phase 5 验证文本与颜色双重表达 |
| SW-NFR-012 | ACCEPTED | 无 schema/protocol version | Phase 1 版本化并建立黄金测试 |

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
