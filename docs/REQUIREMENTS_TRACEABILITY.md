# 产品需求追踪矩阵

**基准：** `docs/PRODUCT_PLAN.md` v1.0  
**更新日期：** 2026-08-30<br>
**当前阶段：** Software Phase 4 进行中（3/8）

状态含义遵循产品规划书：`ACCEPTED`、`IMPLEMENTED`、`VERIFIED_HOST`、`VERIFIED_BENCH`、`DEFERRED`。`IMPLEMENTED` 只表示存在部分代码，不表示达到完整验收标准。

## 软件功能需求

| ID | 状态 | 当前实现/证据 | 主要缺口或下一阶段 |
|---|---|---|---|
| SW-FR-001 | VERIFIED_HOST | `Measurement` 包含 UTC 时间、通道、值、单位、状态、来源、质量和 schema；DC/迟滞 runners 与结果包保留逐点 references/values/quality/reasons，标准结果已由黄金文件冻结 | Phase 4/5 消费时保持同一记录链 |
| SW-FR-002 | VERIFIED_HOST | `TestRunMetadata` 保存测试、配置、UTC、软件、设备/profile、来源和 raw IDs；DC/迟滞生命周期映射为证据一致的 `TestRunResult`，JSON/CSV 与黄金结果冻结其语义 | Phase 4/5 复用同一 schema |
| SW-FR-003 | VERIFIED_HOST | 9 类受控 `EvidenceSource` 已验证且每个正式 Measurement 必填；Step 7 验证 bundle、JSON 和 CSV 不改变来源 | Phase 5 在人类报告中同样显著显示来源 |
| SW-FR-004 | VERIFIED_HOST | Measurement 强制 `record_id`/`raw_record_id`；DC/迟滞分析和 Step 7 builders 保留逐点 record/raw 引用，bundle 强制其与 TestRun 完全一致 | 校准派生链的专用 TestRun/export mapping 后续补充 |
| SW-FR-005 | VERIFIED_HOST | 12 类受控单位；Step 1 只允许有限 V/mV 显式换算并拒绝安培、count、未知单位和 NaN/Inf | 后续分析继续使用同一规范化入口 |
| SW-FR-010 | VERIFIED_HOST | CRC 只有 `protocol/crc.py` 一个实现；固定参数、5 个黄金向量和 bytes-like 边界测试通过 | 后续 profile/adapter 复用，不再复制算法 |
| SW-FR-011 | VERIFIED_HOST | Step 1 的 profile-neutral bounded LF stream 已覆盖分段、粘包、exact limit、跨 chunk 超长、恢复和 reset；Step 2 的 `protocol.envelope` 覆盖严格 ASCII token、LF/CRLF、长度和 CRC；Step 3 `SerialSession` 已把 partial/coalesced/overlong chunks 转为有界 raw events | Step 4/5 profile 层继续解释 AFE/MSP 业务字段 |
| SW-FR-012 | VERIFIED_HOST | AFE v1 严格解析和错误分类由 20 条合法、9 类非法黄金消息冻结；旧 wrapper/API/bytes 不变；`afe-channel-map.v1` 显式映射 legacy `input_mv/output_mv` 与 canonical `input/output` | Step 4 的 AFE serial profile 使用 canonical adapter vocabulary，不静默改历史记录 |
| SW-FR-013 | VERIFIED_HOST | `transport.SequenceTracker` 由 profile 指定 2–64-bit 位宽，明确记录 FIRST/IN_ORDER/GAP/DUPLICATE/OUT_OF_ORDER、missing count 和 high-water mark；Step 3 raw event 可保留 typed observation，CRC 失败不会推进 sequence | Step 4/5 由 AFE/MSP profiles 提供字段位宽和 sequence value |
| SW-FR-014 | VERIFIED_HOST | AFE profile name=`afe`、wire version=`1`；黄金坏版本记录稳定抛出 `UnsupportedProtocolVersion` | Phase 4 在连接握手中应用 |
| SW-FR-015 | IMPLEMENTED | 多记录 CAP_REQ/CAP DEVICE/CHANNEL/END 已定义并可与 `DeviceCapabilities` 往返；未知 bit、序号和数量不一致被拒绝 | Phase 2/4 adapter 实际协商 |
| SW-FR-016 | VERIFIED_HOST | `SerialBackend`/`SerialSession` 已验证发现、打开、bounded read、正常 timeout、断线清半帧、每次断线 0–10 次有限重连和 deterministic close；失败使用稳定 transport error 且逻辑状态关闭 | 具体 OS/pyserial backend 与 SerialAdapter 留到 Step 6；真实端口留到可选 Step 7 |
| SW-FR-017 | VERIFIED_HOST | `BoundedRawEventLog` 保留 exact bytes、UTC、logical port、显式 profile、parse/error 和 typed sequence；状态先 `PENDING_PROFILE` 再显式 PARSED/REJECTED；默认 1,024 条/256 KiB，硬上限 10,000 条/2 MiB，仅内存且不自动持久化/上传 | Step 4/5 profiles 填写业务 outcome；Step 6 组合 adapter；未来 export 需显式隐私评审 |
| SW-FR-020 | VERIFIED_HOST | 正式 `DeviceAdapter` 已定义统一接口；reference、Simulator 和 CSV Replay 均通过同一套 8 项只读契约；`run_read_workflow` 已用同一请求实际驱动两个正式适配器 | Phase 4 让 Serial 适配器通过相同契约和工作流 |
| SW-FR-021 | VERIFIED_HOST | 版本化只读 SimulatorAdapter 已验证增益、偏置、噪声、饱和、迟滞和受控故障；Steps 4–5 确认它在 DC/迟滞输出 runners 中保持零采集 `UNSUPPORTED`，不会伪装成 DAC | 后续离线分析保持同一来源边界 |
| SW-FR-022 | VERIFIED_HOST | `csv-replay.v1` 提供不可变 dataset/record 与严格 parser；正式 `CsvReplayAdapter` 已验证顺序读取、独立通道游标、速度、暂停/恢复、明确 EOF、原引用保留和强制 `CSV_REPLAY` 来源；共享工作流已消费回放 | Phase 5 UI 增加用户控制 |
| SW-FR-023 | IMPLEMENTED | 正式核心已有 driver-neutral backend/session/event port 且架构测试保持标准库依赖；尚无 concrete OS backend 或 `SerialAdapter` | Phase 4 Step 6 实现可选 pyserial backend/SerialAdapter 并继续隔离分析层 |
| SW-FR-024 | ACCEPTED | 无 MSP430 profile | Phase 4 独立实现，保留原始字段 |
| SW-FR-025 | VERIFIED_HOST | 读工作流及 DC/迟滞 runners 均先做原子能力预检；runners 对缺输出/读取/数字输入/安全关闭能力返回零采集 `UNSUPPORTED`，Simulator/CSV 集成测试通过 | 新 runners 继续复用相同原则 |
| SW-FR-026 | VERIFIED_HOST | AFE v1/Capabilities 定义 SAFE_SHUTDOWN；DC/迟滞 runners 在成功、中止、读取/等待异常路径调用 cleanup，shutdown/disconnect 故障强制覆盖潜在 PASS 为 ERROR | 输出型硬件接入时仍需 fault/bench 验证物理安全状态 |
| SW-FR-030 | VERIFIED_HOST | `dc-sweep-runner.v1` 支持有序 setpoints、每点重复次数、注入 settle/abort、逐步记录和完整/部分结果；公开 plan/runner 签名已冻结，builder 导出完整逐点链 | 真实刺激仍待硬件 |
| SW-FR-031 | VERIFIED_HOST | `dc-sweep-analysis.v1` 计算 gain、offset、R²、RMSE、最大残差和逐点拟合；标准 synthetic 输入的 exact fit/criteria/export 已冻结 | 真实拟合仍待 BENCH |
| SW-FR-032 | VERIFIED_HOST | 上下饱和限值有限、可配置且边界包含；所有点保留并逐点区分 `LOW_SATURATION`/`HIGH_SATURATION` 和组件质量原因 | Step 3 可把有效点数纳入 criteria；真实饱和电压仍待 BENCH |
| SW-FR-033 | VERIFIED_HOST | `hysteresis-analysis.v1` 验证方向和 0/1 状态，保存转换前后引用并以区间中点估计阈值；标准 synthetic cycle 的 1750/1550/200 mV exact result 已冻结 | 这些是软件基准；真实阈值仍待 BENCH |
| SW-FR-034 | VERIFIED_HOST | `calibration-analysis.v1` 产生不可变版本化线性系数、双来源与参与拟合的 record/raw ID、校准前后误差；应用系数生成新 Measurement 而不修改原始批次 | 标准器/实物精度仍需未来 BENCH；专用 TestRun/export mapping 尚未定义 |
| SW-FR-035 | VERIFIED_HOST | `frequency-response-analysis.v1` 对显式 Hz/输入/输出幅值计算 ratio、`20 log10` dB 和 dB-vs-log10(Hz) 截止插值；无交点 incomplete，多交点拒绝 | 真实波形采集、FFT 和物理带宽仍 DEFERRED |
| SW-FR-036 | VERIFIED_HOST | 公共质量层逐项映射缺失、非有限、饱和、超范围、时间、通信和设备故障；DC/迟滞 builders 保留逐点质量与排除原因，缺失数据不形成完整结果 | 校准/频响专用导出仍以后续 TestRun mapping 为前提 |
| SW-FR-037 | VERIFIED_HOST | DC 与迟滞 criteria/evaluator 只对完整证据给 PASS/FAIL；bundle 强制 criteria/outcome 一致，两个 exact golden PASS 同时冻结来源、逐点证据与结论 | 新 criteria 需新版本和黄金评审 |
| SW-FR-038 | VERIFIED_HOST | 固定 telemetry 回归保持冻结；Step 8 新增标准 synthetic DC 输入以及 exact DC/迟滞输出与 SHA-256，公开 runner 在仓库外 wheel 完成 safe `UNSUPPORTED` smoke | Phase 4 接入新来源时增加对应 golden |
| SW-FR-040 | IMPLEMENTED | 两个工具有 argparse | Phase 5 建立统一产品 CLI |
| SW-FR-041 | ACCEPTED | `app.py` 仅占位 | Phase 5 实现 Dashboard |
| SW-FR-042 | ACCEPTED | 无测试向导 | Phase 5 实现 |
| SW-FR-043 | VERIFIED_HOST | `result-export.v1` 四列行式 CSV 已实现固定 row type/order/index、严格 JSON payload、100,000 行/2 MB 限制、精确往返和原子默认不覆盖写入；公开列/限制已冻结 | Phase 5 CLI/报告消费 |
| SW-FR-044 | VERIFIED_HOST | `result-export.v1` 严格 JSON 已实现稳定字段顺序、UTC、finite-only、重复键/坏 Unicode/坏版本拒绝和精确往返；两个 exact JSON golden 已冻结 | Phase 5 CLI/报告消费 |
| SW-FR-045 | ACCEPTED | `summary.py` 占位 | Phase 5 实现证据和限制说明 |
| SW-FR-046 | IMPLEMENTED | 正式包公开稳定领域/协议/配置/adapter/replay 错误；黄金坏消息冻结 CRC、长度、framing、协议版本、业务协议和 replay 格式/版本错误家族；回放 EOF 使用独立 `ReplayEndOfData` | Phase 5 增加面向用户的操作指导 |

## 软件非功能需求

| ID | 状态 | 当前实现/证据 | 主要缺口或下一阶段 |
|---|---|---|---|
| SW-NFR-001 | VERIFIED_HOST | `src` 布局、editable install、隔离构建、仓库外 wheel 安装和 import 均通过 | Phase 5 增加最终用户运行入口，Phase 6 再做发布候选安装测试 |
| SW-NFR-002 | IMPLEMENTED | 当前核心使用标准 Python | Phase 4/6 验证 Windows，避免核心平台绑定 |
| SW-NFR-003 | IMPLEMENTED | adapter/read workflow/runners 保持既有 cleanup；Step 3 另外验证 serial 打开/读取/关闭失败、断线、半帧 reset、有限重连和失败后逻辑关闭，不会把 timeout 误作有效数据 | concrete OS backend、真实断线和进程级 worker 退出仍待 Step 6/7 |
| SW-NFR-004 | VERIFIED_HOST | 单元、黄金、架构、adapter/workflow、runners、分析、导出和 Steps 1–3 transport/envelope 全部无需硬件；1,218 项完整回归、6,274/6,274 正式 package 覆盖及仓库外 wheel smoke 均离线通过 | Phase 4 保持硬件可选测试路径 |
| SW-NFR-005 | VERIFIED_HOST | 架构测试禁止正式核心导入第三方/串口/GUI/SDK；新增 runner 只依赖标准库和正式 adapter/config/domain/analysis 层 | 后续 runner 保持同一依赖方向 |
| SW-NFR-006 | VERIFIED_HOST | 正式领域、协议与配置模块责任分离，公开 API 有类型、文档与完整 host tests | Phase 2 继续保持 adapter 依赖方向 |
| SW-NFR-007 | ACCEPTED | 无性能基准 | Phase 5/6 建立实际数据规模基准 |
| SW-NFR-008 | VERIFIED_HOST | Replay 与 result-export 的严格 JSON/CSV 均有版本/大小/类型/Unicode/非有限值边界；结果写入默认不覆盖并使用原子发布；无 `eval`/`exec` | Phase 5 扩展到 CLI 路径和命令入口 |
| SW-NFR-009 | IMPLEMENTED | 当前无网络代码，文件均本地 | Phase 5 文档化并保持默认离线 |
| SW-NFR-010 | ACCEPTED | 报告未实现 | Phase 1 定义版本字段，Phase 3/5 写入结果 |
| SW-NFR-011 | ACCEPTED | 无 UI | Phase 5 验证文本与颜色双重表达 |
| SW-NFR-012 | VERIFIED_HOST | Measurement、capability、TestRun、AFE、配置、analysis、criteria、evaluation、runners 和 `result-export.v1` 均显式版本化；Phase 2/3 公开 API 与 exact 结果均由黄金文件冻结 | 破坏性变化必须升级版本并记录迁移 |

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
| VERIFIED_HOST | 34 |
| IMPLEMENTED | 7 |
| ACCEPTED | 7 |
| DEFERRED | 12 |
| VERIFIED_BENCH | 0 |
| 总计 | 60 |

Software Phase 1、2、3 均已完成各自 8/8。Software Phase 4 已完成 Steps 1–3/8：profile-neutral stream/sequence、token/CRC envelope、AFE compatibility wrapper、显式 channel mapping、driver-neutral serial lifecycle 和 bounded memory-only raw event 均通过 HOST_TEST；当前完整回归 1,218 项，正式 package 6,274/6,274 语句覆盖。下一里程碑是独立 AFE v1 serial profile；硬件仍为 DEFERRED，VERIFIED_BENCH 仍为 0。
