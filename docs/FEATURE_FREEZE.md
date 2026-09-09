# 功能冻结与成果收敛

**冻结日期：** 2026-09-08<br>
**软件版本：** `0.1.0b1`<br>
**状态：** 本地未提交成果已进入功能冻结；发布治理仍为 Software Phase 6 的 7/8

## 冻结目的

Analog Validation Studio 已具备完整的软件主链：从受控数据输入、分析、工程判断、
批次执行、协作取消，到项目历史、可验证产物、报告、CLI 和 Dashboard。当前重点从
“继续增加功能”转为“保持稳定、便于安装、演示、解释和评审”。冻结不等于发布，
也不改变 Git 历史或任何外部可见状态。

## 已冻结的产品范围

- 控制器中立的测量、能力、安全范围、配置、协议和 adapter 契约；
- `SYNTHETIC` Simulator 与严格 `CSV_REPLAY` 的 read、DC、迟滞、校准、频响和有限
  live monitor 工作流；
- 单 owner worker、真实进度、暂停/恢复、批次级协作取消和 cleanup；
- `COMPLETE`、`PARTIAL`、`CANCELLED`、`ERROR` 批次语义，以及严格可读取的
  manifest v1/v2 和当前 v3；
- create-new、原子发布、不覆盖、SHA-256 完整性检查和 Replay 输入归档；
- 人类报告、结构化 JSON/CSV、确定性 12 产物演示、项目历史与比较；
- 本地 CLI 和 Precision Lab Console Dashboard 的新手引导与证据边界。

## 冻结后的变更准则

只有下列情况可以打破功能冻结，并且仍需独立评审和完整验证：

1. 会造成错误结论、数据损坏、安全边界失效或无法 cleanup 的 P0/P1 缺陷；
2. 已被真实重复任务或陌生用户观察到、会阻断主链的交互问题；
3. 已发布契约的兼容、安全、隐私或可安装性问题；
4. 发布前必须修复的文档与实际行为不一致。

其余想法进入技术债或后续路线，不在冻结期直接实现。每次例外都应说明触发证据、
影响范围、回归风险和验收结果，避免以“顺手优化”为由扩大变更。

## 明确延期的事项

- 从归档 Replay 输入一键重跑；
- READ/LIVE 原始输出 observation 持久化；
- 项目历史曲线叠加；
- manifest 签名、作者认证、多用户权限和云协作；
- Dashboard 运行时迁移与完整屏幕阅读器支持；
- 真实串口长期运行、真实 AFE 和实验室仪器验证。

这些事项并非当前产品主链缺失。只有观察到明确需求或进入对应硬件阶段后才重新排序。

## 收敛验收门

- 完整 pytest 与 package statement coverage 100%；
- Ruff、mypy、`pip check` 和 `git diff --check`；
- 从工作树外的只读源码快照隔离构建 sdist 和 wheel；
- wheel 安装到全新环境，并确认导入来自该环境的 `site-packages`；
- 普通路径和 Unicode 路径演示逐文件 SHA-256 一致；
- 安装后的 CSV_REPLAY 项目批次、manifest v3、stderr/stdout 隔离、输入归档和
  源文件改动后的历史验证；
- 隐私路径扫描和证据标签复核。

本轮实测证据记录在
[功能冻结与成果收敛报告](../reports/feature-freeze-and-consolidation-2026-09-08.md)。

## 证据与发布边界

`SYNTHETIC`、`CSV_REPLAY`、`HOST_TEST`、`SPICE_IDEAL`、
`BENCH_CONTROLLER` 和 `BENCH` 必须始终分开。软件 PASS、确定性演示、主机性能检查
和 Replay 历史都不是硬件验证。当前已记录的最高证据仍只是既有的
`BENCH_CONTROLLER` MSP430 UART 兼容性；已验证 AFE 硬件性能仍为 0。

本轮不执行 commit、push、PR 修改、merge、tag、Release、包发布、可见性修改、
许可证修改或历史重写。Software Phase 6 Step 8 仍只能由 owner 明确授权。
