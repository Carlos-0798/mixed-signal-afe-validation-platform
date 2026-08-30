# 技术债与已知缺口

**更新日期：** 2026-08-29  
**来源：** Software Phase 0 审计

优先级：`P0` 阻塞安全或正确性；`P1` 阻塞下一主要里程碑；`P2` 应在 v1 前解决；`P3` 可后置。

| ID | 优先级 | 技术债/缺口 | 影响 | 计划处理 |
|---|---|---|---|---|
| TD-001 | CLOSED | Git 身份和首个 Phase 0 基线于 2026-08-29 建立 | 已具有可恢复基线和历史差异 | 后续阶段保持小步提交 |
| TD-002 | P1 | 核心代码位于 `dashboard/` 包 | UI、领域和协议边界含义混乱 | Phase 1 迁移到 `src/analog_validation/` |
| TD-003 | CLOSED | 正式 Measurement 强制来源、状态、质量、单位、UTC 时间和原始引用 | 合成、仿真、回放与 BENCH 标签不再依赖文件名 | 证据见 `reports/software-phase1-step3.md` |
| TD-004 | P1 | Measurement、CRC 和 framing 已进入正式包，但 AFE profile 仍未版本化 | 业务字段修改仍可能静默破坏兼容性 | Step 6 建立 AFE v1 profile 和黄金消息 |
| TD-005 | CLOSED | `DeviceCapabilities` 已要求显式通道、安全范围、命令和 safe-shutdown 一致性 | 软件领域层不再需要根据板名猜测功能；线上协商仍属后续实现 | 证据见 `reports/software-phase1-step4.md` |
| TD-006 | P2 | 无流式分帧和序列追踪 | 真实串口分段、粘包和丢帧无法处理 | Phase 4 |
| TD-007 | P1 | Measurement 已强制显式处理 NaN/Inf/缺失；旧 DC/迟滞分析尚未应用质量和方向规则 | 旧分析仍可能对异常裸数据产生无意义结果 | Phase 3 迁移分析并保存逐点质量 |
| TD-008 | P2 | 饱和排除只保存数量，不保存逐点原因 | 报告不可解释 | Phase 3 |
| TD-009 | P1 | 校准、频响、判定和报告均为占位 | 不能形成成熟测试产品 | Phase 3/5 |
| TD-010 | CLOSED | 正式 `src/analog_validation/` 包、单一版本来源、隔离构建和仓库外 wheel 导入已于 2026-08-29 验证 | 包装基础问题已解除；CLI 仍由 TD-014 跟踪 | 证据见 `reports/software-phase1-step1.md` |
| TD-011 | CLOSED | 独立 Python `.venv`、setuptools 和隔离 wheel 安装已于 2026-08-29 验证 | 原环境依赖 Codex 运行时的问题已解除 | 证据见 `reports/environment-setup-2026-08-29.md` |
| TD-012 | P1 | 100帧流水线和合成 CLI 检查不在 pytest | 回归时可能丢失 | Phase 1/2 转为自动集成测试 |
| TD-013 | P2 | 本地 mypy、Ruff 和 coverage 已可运行，但尚无冻结规则和 CI | 自动质量门仍不能在每次变更时执行 | Phase 1 冻结核心规则；Phase 6 建立 CI |
| TD-014 | P2 | 无统一 CLI，`app.py` 仅打印状态 | 用户无法运行产品流程 | Phase 5 |
| TD-015 | P2 | 已有 CRC 参数和 5 个黄金向量，但尚无版本化 AFE 消息与 schema 迁移样本 | CRC 漂移可发现，业务协议漂移仍缺保护 | Step 6/8 |
| TD-016 | CLOSED | 正式包已建立 Validation、Protocol、Framing、CRC、版本、Capability 和 Configuration 错误层级 | UI/CLI 已有稳定捕获边界；具体协议迁移仍在 Step 5 | 证据见 `reports/software-phase1-step2.md` |
| TD-017 | P3 | 采购和控制器选择文档仍包含软件转向前候选 | 可能误读为立即采购指令 | 保留历史；采购前由新规划重新冻结 |
| TD-018 | P0 | 所有硬件性能仍未验证 | 错误成果声明会损害可信度和安全 | 持续保持 `VERIFIED_BENCH=0`，直到真实台架阶段 |

关闭技术债时必须记录对应代码、测试、文档和验证报告，不能只从表格删除。
