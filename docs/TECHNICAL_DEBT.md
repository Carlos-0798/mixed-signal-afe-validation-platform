# 技术债与已知缺口

**更新日期：** 2026-08-30<br>
**来源：** Software Phase 0–4 持续审计

优先级：`P0` 阻塞安全或正确性；`P1` 阻塞下一主要里程碑；`P2` 应在 v1 前解决；`P3` 可后置。

| ID | 优先级 | 技术债/缺口 | 影响 | 计划处理 |
|---|---|---|---|---|
| TD-001 | CLOSED | Git 身份和首个 Phase 0 基线于 2026-08-29 建立 | 已具有可恢复基线和历史差异 | 后续阶段保持小步提交 |
| TD-002 | CLOSED | 正式核心已迁入 `src/analog_validation/`，旧 protocol/shared-model files 已删除；`dashboard/measurements` 仅保留待 Phase 3 迁移的旧分析 | UI、领域和协议依赖方向已分离 | 证据见 `reports/software-phase1-step8.md`；旧分析由 TD-007/008/009 跟踪 |
| TD-003 | CLOSED | 正式 Measurement 强制来源、状态、质量、单位、UTC 时间和原始引用 | 合成、仿真、回放与 BENCH 标签不再依赖文件名 | 证据见 `reports/software-phase1-step3.md` |
| TD-004 | CLOSED | Measurement、CRC、framing、AFE v1 profile 和 validation config 已版本化；20 条合法与 9 类非法 AFE 黄金消息已冻结 | 字段、CRC、模型意义和错误家族的意外漂移可由 pytest 发现 | 证据见 `reports/software-phase1-step8.md` |
| TD-005 | CLOSED | `DeviceCapabilities` 已要求显式通道、安全范围、命令和 safe-shutdown 一致性 | 软件领域层不再需要根据板名猜测功能；线上协商仍属后续实现 | 证据见 `reports/software-phase1-step4.md` |
| TD-006 | CLOSED | Phase 4 Step 1 已实现 profile-neutral 有界 LF 字节流、超长恢复和 profile-configurable modular sequence tracking | 分段、粘包、超长、16/32-bit 回绕、缺帧、重复和乱序已有 HOST_TEST；真实 serial lifecycle 由 TD-025 跟踪 | 证据见 `reports/software-phase4-step1.md` |
| TD-007 | CLOSED | 正式 DC 与迟滞算法已迁入 `analog_validation.analysis`，具备有限值/单位/来源/质量/方向/可追溯约束；旧 dashboard 函数仅保留迁移回归对照 | 正式产品分析不再依赖裸 tuple 迟滞入口 | 证据见 `reports/software-phase3-step2.md` 和 `reports/software-phase3-step5.md` |
| TD-008 | CLOSED | `dc-sweep-analysis.v1` 保留所有点、输入/输出双引用、组件质量决定、逐点 `LOW/HIGH_SATURATION` 和 DC 排除原因 | 正式 DC 结果可解释具体使用或排除的每个点；旧函数不属于正式核心 | 证据见 `docs/dc-sweep-analysis.md` 和 `reports/software-phase3-step2.md` |
| TD-009 | P2 | Step 7 已实现 `result-export.v1`、DC/迟滞 typed builders、稳定 JSON/CSV 和安全文件写入；人类报告及校准/频响的专用 TestRun/export mapping 尚未实现 | 已有稳定机器结果文件，但最终用户仍缺少叙述、图表和完整分析类型覆盖 | Phase 5；结构化导出证据见 `reports/software-phase3-step7.md` |
| TD-010 | CLOSED | 正式 `src/analog_validation/` 包、单一版本来源、隔离构建和仓库外 wheel 导入已于 2026-08-29 验证 | 包装基础问题已解除；CLI 仍由 TD-014 跟踪 | 证据见 `reports/software-phase1-step1.md` |
| TD-011 | CLOSED | 独立 Python `.venv`、setuptools 和隔离 wheel 安装已于 2026-08-29 验证 | 原环境依赖 Codex 运行时的问题已解除 | 证据见 `reports/environment-setup-2026-08-29.md` |
| TD-012 | CLOSED | 冻结的 100 帧生成器已迁入正式 package，并由 CLI、集成测试和确定性 SimulatorAdapter 共同复用；stream SHA-256 保持不变；非理想和受控故障已在 Step 4 配置化 | 合成基础流水线不再存在第二份公式，增益/噪声/饱和/迟滞/故障均有确定性回归 | 证据见 `reports/software-phase2-step3.md` 和 `reports/software-phase2-step4.md` |
| TD-013 | P2 | 本地 mypy、Ruff、coverage、golden compatibility、隔离构建和外部 wheel smoke 已成为阶段门禁，但尚无 CI | 开发者可手动完整验证，远程变更仍不会自动执行质量门 | Phase 6 建立 CI |
| TD-014 | P2 | 无统一 CLI，`app.py` 仅打印状态 | 用户无法运行产品流程 | Phase 5 |
| TD-015 | CLOSED | CRC vectors、AFE wire records、预期 model JSON 和非法输入错误家族均已冻结 | 文件兼容性已有 host regression 保护 | 未来 schema 变化必须添加迁移样本 |
| TD-016 | CLOSED | 正式包已建立 Validation、Protocol、Framing、CRC、版本、Capability、Configuration 和 Adapter 错误层级；旧协议入口已删除 | UI/CLI 已有稳定捕获边界 | 证据见 `reports/software-phase1-step2.md`、Step 8 closure 和 `reports/software-phase2-step1.md` |
| TD-017 | P3 | 采购和控制器选择文档仍包含软件转向前候选 | 可能误读为立即采购指令 | 保留历史；采购前由新规划重新冻结 |
| TD-018 | P0 | 所有 AFE 硬件性能仍未验证；Step 7 只有 controller UART compatibility BENCH 证据 | 把窄范围串口证据扩大为模拟性能声明会损害可信度和安全 | 持续保持 AFE `VERIFIED_BENCH=0`，直到真实模拟台架阶段，并把两类证据分栏 |
| TD-019 | CLOSED | `validation-config.v1` 已使用不可执行的严格 JSON，限制文件大小，并对 profile、通道、单位、超时、来源和输出边界执行分层验证；DeviceAdapter 在 I/O 前复用这些安全门 | 配置不依赖任意 Python 代码；具体 Simulator/CSV/Serial I/O 仍按阶段实现 | 证据见 `reports/software-phase1-step7.md` 和 `reports/software-phase2-step1.md` |
| TD-020 | CLOSED | `csv-replay.v1` 已冻结 13 列、META/DATA/END、UTC、单位、状态、声明来源、质量、记录引用和限制；loader 只读且合法/非法黄金样本冻结错误族 | 历史数据不再依赖猜测列、单位或文件是否完整；播放生命周期仍由 Step 6 跟踪 | 证据见 `docs/csv-replay-v1.md` 和 `reports/software-phase2-step5.md` |
| TD-021 | CLOSED | 正式 `CsvReplayAdapter` 已提供显式只读能力、独立通道游标、立即/缩放时间、运行时速度、暂停/恢复、明确 EOF、引用保留和强制 `CSV_REPLAY` 来源，并通过共用 adapter 契约 | 历史文件可通过正式设备端口消费，不会把文件声明的 `BENCH_*` 提升为当前实物证据 | 证据见 `docs/adapters.md` 和 `reports/software-phase2-step6.md` |
| TD-022 | CLOSED | `read-workflow.v1` 已用不可变请求/结果和同一函数驱动 Simulator/CSV；全量能力预检发生在读取前，明确区分 `COMPLETED`、`UNSUPPORTED` 与 `INCOMPLETE`，所有路径释放 workflow 自己拥有的 adapter | 上层采集不再根据来源写分支，也不会把缺能力、数据耗尽或执行错误混成一种状态 | 证据见 `docs/read-workflow.md` 和 `reports/software-phase2-step7.md` |
| TD-023 | CLOSED | `phase2_public_api.json` 冻结公开 imports/schema/enum/signature/error/replay hash，`phase2_workflow_v1.json` 冻结 Simulator/CSV/UNSUPPORTED 端到端含义；隔离构建和仓库外 wheel 验证纳入阶段出口 | Phase 2 兼容性变化不再能静默发生；未来破坏性变更必须升级版本并记录迁移 | 证据见 `docs/phase2-public-api.md` 和 `reports/software-phase2-step8.md` |
| TD-024 | CLOSED | `phase3_public_api.json` 冻结公开 imports/schema/enum/signature/error/constants 与三份结果文件哈希；exact `SYNTHETIC` DC/迟滞结果冻结拟合、饱和排除、阈值、迟滞宽度及来源语义 | Phase 3 调用和结果兼容性变化不再能静默发生；这些基准不构成实物性能声明 | 证据见 `docs/phase3-public-api.md` 和 `reports/software-phase3-step8.md` |
| TD-025 | P2 | Step 7 已完成独立可选 `analog_validation_pyserial` backend、base/serial extras 外部安装、COM 枚举和一次 receive-only MSP430 SerialAdapter→ReadWorkflow HIL；尚无 owning worker、长时间 OS timing 或 physical reconnect test | 产品可安全选择真实串口，但当前证据仅为 COM4 五帧、单次打开/关闭、零写入；不能推广为生产级 worker 或串口可靠性 | Phase 5 处理 worker/UI/cancellation，后续单独评审 long-duration 与 disconnect HIL；证据见 `docs/pyserial-backend.md` 和 `reports/software-phase4-step7.md` |
| TD-026 | CLOSED | `protocol.envelope` 已提供不要求 namespace 的严格 token/CRC record；`framing.py` 仅保留 AFE shape wrapper | AFE 与 MSP430 形状可复用同一 envelope，旧 AFE API/bytes/errors 不变 | 证据见 `reports/software-phase4-step2.md`、三条 neutral golden records 和旧 20 valid/9 invalid 回归 |
| TD-027 | CLOSED | `afe-channel-map.v1` 已冻结 canonical `input/output/gain/threshold` 与 legacy telemetry v1 `input_mv/output_mv/gain/threshold`，转换必须显式声明 source/target；Step 4 AFE serial profile 已实际跨越此边界 | 串口 telemetry 已对齐 Simulator/workflow，同时历史 mapper/Measurement 不被静默重命名 | 证据见 `docs/afe-channel-mapping.md`、`docs/serial-profiles.md` 和对应 tests |
| TD-028 | CLOSED | 独立 MSP430 Equipment Health v1 parser/profile 和本仓库 10 valid/11 invalid fixtures 已实现；支持 device-output `TEL/ACK/STS/CFG/LOG`、32-bit TEL continuity、sentinel/fault mapping、typed raw outcome 和静态只读 capabilities | 不再依赖人工字段解析；Step 6 已完成 receive-only adapter 组合，真实 OS serial/HIL 仍由 TD-025 与 Phase 4 Step 7 跟踪 | 证据见 `docs/serial-profiles.md`、`reports/software-phase4-step5.md` 和 `reports/software-phase4-step6.md` |
| TD-029 | CLOSED | `serial-profile.v1` 和独立 `AfeV1SerialProfile` 已实现显式 identity、16-bit TEL continuity、严格 capability aggregation、canonical telemetry mapping、typed raw outcome 和失败回滚；20 valid/9 invalid golden 均通过新路径 | AFE 业务字段不再由调用者临时拼接解析，且 transport/profile/高层依赖方向已有执行门禁 | 证据见 `docs/serial-profiles.md` 和 `reports/software-phase4-step4.md` |
| TD-030 | CLOSED | Step 6 已建立显式 AFE capability projector：`adcN/dacN/pwmN/dinN` 映射为 `afe.chN.input/dac/pwm/threshold`，保留 native snapshot，并验证 identity、channel counts、numeric ranges 与 command subset | workflow channel 已与 telemetry 对齐；projector 不能增加命令或把 receive-only adapter 提升为输出设备 | 证据见 `src/analog_validation/serial_adapters/afe_v1.py`、共用/投影防御测试和 `reports/software-phase4-step6.md` |
| TD-031 | P2 | Measurement v1 尚无 watt/milliwatt 单位；MSP430 `power_mw` 已保留在 typed telemetry 和 INA219 availability 语义中，但未伪装为 `UNITLESS` Measurement | 通用 workflow 暂时不能按正式 Measurement channel 直接读取功率；错误添加单位会漂移 Phase 2/3 冻结契约 | 在后续 schema/version 评审中增加 power unit 与迁移样本；在此之前由 typed raw message 审计，不静默换单位 |

关闭技术债时必须记录对应代码、测试、文档和验证报告，不能只从表格删除。
