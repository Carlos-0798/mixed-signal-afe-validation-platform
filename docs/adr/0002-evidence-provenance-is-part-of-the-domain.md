# ADR-0002：证据来源是领域模型的一部分

**Status:** Accepted  
**Date:** 2026-08-29

## Context

本项目同时使用公式、合成数据、CSV 回放、SPICE 和未来实物测量。如果来源只写在日志或文件名中，经过导出、拟合或报告后容易丢失，进而把模拟结果误认为实测结果。

## Decision

- 每个原始数据集和 TestRun 必须有受控枚举形式的来源标签；
- 派生结果必须引用其输入运行或数据集；
- 原始记录不可被校准或过滤结果覆盖；
- 报告必须显示来源、软件版本、配置和未验证限制；
- 只有 `BENCH_*` 来源可支持真实硬件性能声明；
- 不完整来源不得默认为 `BENCH`，而应拒绝或标记为未知且不可用于 PASS。

第一版来源至少包含：`THEORY`、`SYNTHETIC`、`CSV_REPLAY`、`SPICE_IDEAL`、`SPICE_MODEL`、`HOST_TEST`、`BENCH_DMM`、`BENCH_CONTROLLER`、`BENCH_SCOPE`。

## Consequences

- 模型和文件格式会多一些元数据；
- 测试和报告可以可靠区分软件演示与硬件证据；
- 将来导入旧 CSV 时必须明确原始来源，不能靠猜测；
- 简历或作品集数字可以回溯到原始证据。

## Alternatives considered

1. **只在 README 写免责声明：** 拒绝，数据离开 README 后会失去上下文。
2. **只按目录区分来源：** 拒绝，文件移动或合并后不可靠。
3. **允许缺省为实测：** 因证据风险拒绝。

