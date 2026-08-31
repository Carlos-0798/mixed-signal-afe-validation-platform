# 产品需求追踪矩阵

**基准：** `docs/PRODUCT_PLAN.md` v1.0  
**更新日期：** 2026-08-30<br>
**当前阶段：** Software Phase 4 进行中（6/8）

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
| SW-FR-011 | VERIFIED_HOST | Step 1–5 的 bounded stream/envelope/session/raw-log/profiles 已由 Step 6 `SerialAdapter` 组合；AFE/MSP 内存 bytes 可经 typed raw outcome 和 Measurement 进入同一 `ReadWorkflow` | 真实 OS stream 仍待可选 HIL |
| SW-FR-012 | VERIFIED_HOST | AFE v1 的 20 valid/9 invalid 契约不变；telemetry 显式转换为 canonical names；Step 6 另将 native `adcN/dacN/pwmN/dinN` capabilities 显式投影为 `afe.chN.input/dac/pwm/threshold` 并拒绝 identity/count/range/command 漂移 | 实物字段/行为仍待 AFE BENCH |
| SW-FR-013 | VERIFIED_HOST | 通用 tracker 已覆盖 2–64 bits；AFE 使用 16-bit TEL continuity，MSP430 使用 32-bit TEL continuity；Step 6 adapter 保持 profile-owned semantics，并在重连清 profile/buffer/capability trust | OS 端口 sequence/uptime 证据待 Step 7 |
| SW-FR-014 | VERIFIED_HOST | `SerialProfileIdentity` 明确 name/version/sequence/limit；`SerialAdapterConfig`、session 和 profile 必须精确匹配，构造时拒绝不一致，不按 COM/VID/PID 猜测 | 无 wire-version token 的 MSP430 仍需用户确认固件接口 |
| SW-FR-015 | VERIFIED_HOST | AFE profile 只在完整合法 CAP transaction 后发布 native capabilities；Step 6 adapter 被动接收并显式投影，同时保留 native snapshot，禁止 command escalation；MSP430 使用静态只读 snapshot | Step 6 不发送 `CAP_REQ`；实物 capability 仍待 HIL/BENCH |
| SW-FR-016 | VERIFIED_HOST | `SerialSession` 的 bounded lifecycle/reconnect 已通过；Step 6 将 open/read/close/reconnect 映射到 adapter errors，成功重连后强制 capability reconfirmation，所有操作有 finite poll budget | concrete OS/pyserial backend 和真实端口留到可选 Step 7 |
| SW-FR-017 | VERIFIED_HOST | bounded raw log 保留 exact bytes/UTC/logical port/profile/outcome/sequence；Step 6 adapter 暴露 immutable snapshot，坏 CRC/overlong 不产生 Measurement，raw 不自动持久化/上传 | 未来 export 需显式隐私评审 |
| SW-FR-020 | VERIFIED_HOST | 正式 `DeviceAdapter` 统一接口和八项只读契约已由 reference、Simulator、CSV Replay、AFE SerialAdapter、MSP430 SerialAdapter 配置通过；同一 `run_read_workflow` 实际驱动四类正式来源 | 未来 instrument adapter 继续复用契约 |
| SW-FR-021 | VERIFIED_HOST | 版本化只读 SimulatorAdapter 已验证增益、偏置、噪声、饱和、迟滞和受控故障；Steps 4–5 确认它在 DC/迟滞输出 runners 中保持零采集 `UNSUPPORTED`，不会伪装成 DAC | 后续离线分析保持同一来源边界 |
| SW-FR-022 | VERIFIED_HOST | `csv-replay.v1` 提供不可变 dataset/record 与严格 parser；正式 `CsvReplayAdapter` 已验证顺序读取、独立通道游标、速度、暂停/恢复、明确 EOF、原引用保留和强制 `CSV_REPLAY` 来源；共享工作流已消费回放 | Phase 5 UI 增加用户控制 |
| SW-FR-023 | VERIFIED_HOST | driver-neutral backend/session/event 与 receive-only `SerialAdapter` 已实现；adapter 不导入 analysis/exports/runners/workflows/dashboard/pyserial，且 AFE/MSP 复合链通过 | concrete OS backend/worker 尚未实现；真实端口待 Step 7 |
| SW-FR-024 | VERIFIED_HOST | 独立 MSP430 parser/profile 保留 raw sentinel/power/state/fault 并安全映射 unavailable；Step 6 已包装为 `SerialAdapter`、通过共用 contract/workflow，并对 DC/迟滞 runner 零写入 `UNSUPPORTED` | Step 7 才可产生本项目自己的可选只读 HIL |
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
| SW-FR-038 | VERIFIED_HOST | 固定 telemetry、标准 synthetic DC、exact DC/迟滞结果与 SHA-256 保持冻结；全部 20 valid/9 invalid AFE records 通过 serial profile；Step 5 又冻结 10 valid/11 invalid 独立 MSP interoperability records、32-bit wrap 和 memory backend 复合链 | Step 8 冻结完整 Phase 4 public contract |
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
| SW-NFR-004 | VERIFIED_HOST | 单元、黄金、架构、adapter/workflow、runners、分析、导出和 Steps 1–6 serial stack 全部无需硬件；1,472 项完整回归、7,198/7,198 正式 package 覆盖及仓库外无 pyserial installed SerialAdapter smoke 均离线通过 | Phase 4 保持硬件可选测试路径 |
| SW-NFR-005 | VERIFIED_HOST | one-way gates 要求 transport 不导入 profiles/高层，profiles 不导入 adapters/analysis/runners/workflows，`serial_adapters` 不导入 analysis/exports/runners/workflows/dashboard/pyserial；MSP profile 无 peer runtime namespace | concrete OS driver 继续作为可选边界 |
| SW-NFR-006 | VERIFIED_HOST | domain/protocol/transport/profiles/serial adapter/config/analysis 责任分离；profile 不打开 COM，adapter 不复制 CRC/分析；公开接口有类型、文档和完整 host tests | Step 8 冻结 Phase 4 public contract |
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
| HW-FR-009 | DEFERRED | receive-only 软件 SerialAdapter 已完成 HOST_TEST；尚无输出型参考控制器或实物链路 | 软件 v1、参考控制器和硬件安全评审 |
| HW-FR-010 | DEFERRED | 独立 MSP430 profile/adapter 已完成 HOST_TEST；尚无本仓库 OS-serial HIL 或实物接线证据 | Step 7 可选只读 HIL；未来硬件阶段另做接线 |
| HW-FR-011 | DEFERRED | 只有安全规则 | 断电、上电和拔除控制器检查 |
| HW-FR-012 | DEFERRED | 只有接口原则 | 原理图、测试点和丝印评审 |

## 汇总

| 状态 | 数量 |
|---|---:|
| VERIFIED_HOST | 37 |
| IMPLEMENTED | 5 |
| ACCEPTED | 6 |
| DEFERRED | 12 |
| VERIFIED_BENCH | 0 |
| 总计 | 60 |

Software Phase 1、2、3 均已完成各自 8/8。Software Phase 4 已完成 Steps 1–6/8：profile-neutral stream/sequence/envelope、driver-neutral lifecycle/raw events、独立 AFE/MSP profiles，以及 receive-only `SerialAdapter` 对共用 adapter/workflow 的组合均通过 HOST_TEST；当前完整回归 1,472 项，正式 package 7,198/7,198 语句覆盖。下一里程碑是可选、单独授权的 MSP430 只读 OS-serial HIL；硬件仍为 DEFERRED，VERIFIED_BENCH 仍为 0。
