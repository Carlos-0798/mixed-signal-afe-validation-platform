# 技术债与已知缺口

**更新日期：** 2026-08-30<br>
**来源：** Software Phase 0 审计

优先级：`P0` 阻塞安全或正确性；`P1` 阻塞下一主要里程碑；`P2` 应在 v1 前解决；`P3` 可后置。

| ID | 优先级 | 技术债/缺口 | 影响 | 计划处理 |
|---|---|---|---|---|
| TD-001 | CLOSED | Git 身份和首个 Phase 0 基线于 2026-08-29 建立 | 已具有可恢复基线和历史差异 | 后续阶段保持小步提交 |
| TD-002 | CLOSED | 正式核心已迁入 `src/analog_validation/`，旧 protocol/shared-model files 已删除；`dashboard/measurements` 仅保留待 Phase 3 迁移的旧分析 | UI、领域和协议依赖方向已分离 | 证据见 `reports/software-phase1-step8.md`；旧分析由 TD-007/008/009 跟踪 |
| TD-003 | CLOSED | 正式 Measurement 强制来源、状态、质量、单位、UTC 时间和原始引用 | 合成、仿真、回放与 BENCH 标签不再依赖文件名 | 证据见 `reports/software-phase1-step3.md` |
| TD-004 | CLOSED | Measurement、CRC、framing、AFE v1 profile 和 validation config 已版本化；20 条合法与 9 类非法 AFE 黄金消息已冻结 | 字段、CRC、模型意义和错误家族的意外漂移可由 pytest 发现 | 证据见 `reports/software-phase1-step8.md` |
| TD-005 | CLOSED | `DeviceCapabilities` 已要求显式通道、安全范围、命令和 safe-shutdown 一致性 | 软件领域层不再需要根据板名猜测功能；线上协商仍属后续实现 | 证据见 `reports/software-phase1-step4.md` |
| TD-006 | P2 | 无流式分帧和序列追踪 | 真实串口分段、粘包和丢帧无法处理 | Phase 4 |
| TD-007 | P1 | 正式 DC 算法已迁入 `analysis.dc_sweep` 并具备有限值/单位/来源/质量/可追溯约束；旧 dashboard DC 仅保留回归对照，正式迟滞算法仍未迁移 | 正式 DC 入口已安全，但旧裸值入口和迟滞路径仍可能产生不可追溯结果 | Phase 3 Step 5 完成迟滞迁移并处理旧兼容入口后关闭；DC 证据见 `reports/software-phase3-step2.md` |
| TD-008 | CLOSED | `dc-sweep-analysis.v1` 保留所有点、输入/输出双引用、组件质量决定、逐点 `LOW/HIGH_SATURATION` 和 DC 排除原因 | 正式 DC 结果可解释具体使用或排除的每个点；旧函数不属于正式核心 | 证据见 `docs/dc-sweep-analysis.md` 和 `reports/software-phase3-step2.md` |
| TD-009 | P1 | 校准、频响、判定和报告均为占位 | 不能形成成熟测试产品 | Phase 3 Steps 3、6、7 和 Phase 5 |
| TD-010 | CLOSED | 正式 `src/analog_validation/` 包、单一版本来源、隔离构建和仓库外 wheel 导入已于 2026-08-29 验证 | 包装基础问题已解除；CLI 仍由 TD-014 跟踪 | 证据见 `reports/software-phase1-step1.md` |
| TD-011 | CLOSED | 独立 Python `.venv`、setuptools 和隔离 wheel 安装已于 2026-08-29 验证 | 原环境依赖 Codex 运行时的问题已解除 | 证据见 `reports/environment-setup-2026-08-29.md` |
| TD-012 | CLOSED | 冻结的 100 帧生成器已迁入正式 package，并由 CLI、集成测试和确定性 SimulatorAdapter 共同复用；stream SHA-256 保持不变；非理想和受控故障已在 Step 4 配置化 | 合成基础流水线不再存在第二份公式，增益/噪声/饱和/迟滞/故障均有确定性回归 | 证据见 `reports/software-phase2-step3.md` 和 `reports/software-phase2-step4.md` |
| TD-013 | P2 | 本地 mypy、Ruff 和 coverage 已可运行，但尚无冻结规则和 CI | 自动质量门仍不能在每次变更时执行 | Phase 1 冻结核心规则；Phase 6 建立 CI |
| TD-014 | P2 | 无统一 CLI，`app.py` 仅打印状态 | 用户无法运行产品流程 | Phase 5 |
| TD-015 | CLOSED | CRC vectors、AFE wire records、预期 model JSON 和非法输入错误家族均已冻结 | 文件兼容性已有 host regression 保护 | 未来 schema 变化必须添加迁移样本 |
| TD-016 | CLOSED | 正式包已建立 Validation、Protocol、Framing、CRC、版本、Capability、Configuration 和 Adapter 错误层级；旧协议入口已删除 | UI/CLI 已有稳定捕获边界 | 证据见 `reports/software-phase1-step2.md`、Step 8 closure 和 `reports/software-phase2-step1.md` |
| TD-017 | P3 | 采购和控制器选择文档仍包含软件转向前候选 | 可能误读为立即采购指令 | 保留历史；采购前由新规划重新冻结 |
| TD-018 | P0 | 所有硬件性能仍未验证 | 错误成果声明会损害可信度和安全 | 持续保持 `VERIFIED_BENCH=0`，直到真实台架阶段 |
| TD-019 | CLOSED | `validation-config.v1` 已使用不可执行的严格 JSON，限制文件大小，并对 profile、通道、单位、超时、来源和输出边界执行分层验证；DeviceAdapter 在 I/O 前复用这些安全门 | 配置不依赖任意 Python 代码；具体 Simulator/CSV/Serial I/O 仍按阶段实现 | 证据见 `reports/software-phase1-step7.md` 和 `reports/software-phase2-step1.md` |
| TD-020 | CLOSED | `csv-replay.v1` 已冻结 13 列、META/DATA/END、UTC、单位、状态、声明来源、质量、记录引用和限制；loader 只读且合法/非法黄金样本冻结错误族 | 历史数据不再依赖猜测列、单位或文件是否完整；播放生命周期仍由 Step 6 跟踪 | 证据见 `docs/csv-replay-v1.md` 和 `reports/software-phase2-step5.md` |
| TD-021 | CLOSED | 正式 `CsvReplayAdapter` 已提供显式只读能力、独立通道游标、立即/缩放时间、运行时速度、暂停/恢复、明确 EOF、引用保留和强制 `CSV_REPLAY` 来源，并通过共用 adapter 契约 | 历史文件可通过正式设备端口消费，不会把文件声明的 `BENCH_*` 提升为当前实物证据 | 证据见 `docs/adapters.md` 和 `reports/software-phase2-step6.md` |
| TD-022 | CLOSED | `read-workflow.v1` 已用不可变请求/结果和同一函数驱动 Simulator/CSV；全量能力预检发生在读取前，明确区分 `COMPLETED`、`UNSUPPORTED` 与 `INCOMPLETE`，所有路径释放 workflow 自己拥有的 adapter | 上层采集不再根据来源写分支，也不会把缺能力、数据耗尽或执行错误混成一种状态 | 证据见 `docs/read-workflow.md` 和 `reports/software-phase2-step7.md` |
| TD-023 | CLOSED | `phase2_public_api.json` 冻结公开 imports/schema/enum/signature/error/replay hash，`phase2_workflow_v1.json` 冻结 Simulator/CSV/UNSUPPORTED 端到端含义；隔离构建和仓库外 wheel 验证纳入阶段出口 | Phase 2 兼容性变化不再能静默发生；未来破坏性变更必须升级版本并记录迁移 | 证据见 `docs/phase2-public-api.md` 和 `reports/software-phase2-step8.md` |

关闭技术债时必须记录对应代码、测试、文档和验证报告，不能只从表格删除。
