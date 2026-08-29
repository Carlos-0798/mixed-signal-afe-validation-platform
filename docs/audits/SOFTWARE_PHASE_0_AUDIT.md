# Software Phase 0 现状审计

**审计日期：** 2026-08-29  
**审计范围：** Analog Validation Studio 主机软件、测试、工具、打包和相关文档  
**证据等级：** `HOST_TEST` 与静态代码检查  
**不在范围：** 硬件、串口电气、MSP430 固件、实验室仪器和实物 AFE

## 1. 审计目的

在继续开发前回答四个问题：

1. 当前真正已经实现并重新验证了什么；
2. 哪些文件值得保留；
3. 哪些内容需要重构、替换或后置；
4. Software Phase 1 应从哪些具体文件开始。

本审计不把历史报告当成当前结果。所有下列命令均在当前仓库的 `.venv` 中重新执行。

## 2. 当前主机基线

| 项目 | 当前结果 |
|---|---|
| Git | `main`，尚无 commit；项目文件全部为 untracked |
| Python | 3.12.13 |
| pytest | 8.4.2 |
| 单元测试 | 23 passed in 0.03s |
| Python 编译检查 | `dashboard/` 与 `tools/` compileall 通过 |
| 遥测流水线 | 100 条合成消息生成、编码、CRC 校验、解析和对象比对通过 |
| 合成扫频 CLI | 21 条数据行生成成功，来源均为 `SYNTHETIC` |
| setuptools | 当前 `.venv` 中 `pip show setuptools` 未找到；干净安装仍需验证 |

这些结果只证明当前主机代码在所述条件下工作，不证明串口、MSP430、ADC、AFE 或其他硬件工作。

## 3. 文件与模块处置结论

| 路径 | 当前作用 | 结论 | 原因与后续 |
|---|---|---|---|
| `dashboard/protocol.py` | CRC、帧编解码、AFE telemetry/command 解析 | **重构并保留算法** | CRC 和严格解析基础可靠；需拆分 CRC、帧、profile，增加版本、能力、序列和流式输入 |
| `dashboard/models.py` | Telemetry、Command、SweepPoint 和结果 dataclass | **替换为版本化领域模型** | 缺少来源、单位、质量标志、原始数据、设备能力和 TestRun |
| `dashboard/measurements/dc_sweep.py` | 线性拟合和固定阈值饱和排除 | **重构并保留算法** | 已有测试；需有限值验证、排除原因、残差、配置化规则和数据质量 |
| `dashboard/measurements/hysteresis.py` | 首次转换点中值和迟滞宽度 | **重构并保留算法** | 已有测试；需状态验证、扫描方向、重复周期、统计和质量标志 |
| `dashboard/measurements/calibration.py` | 占位 | **替换** | 尚无实现 |
| `dashboard/measurements/frequency_response.py` | 占位 | **后置到 Software Phase 3** | 先完成公共模型和离线输入格式 |
| `dashboard/serial_worker.py` | 占位 | **后置到 Software Phase 4** | 先冻结 DeviceAdapter 和协议边界 |
| `dashboard/reporting/*` | 占位 | **后置到 Software Phase 3/5** | 等 TestRun 和证据 schema 稳定 |
| `dashboard/app.py` | 打印 Phase 0 状态 | **替换** | 不是产品 CLI 或 Dashboard；UI 必须后置于核心 |
| `tools/telemetry_simulator.py` | 合成 telemetry 生成 | **迁入 SimulatorAdapter** | 保留确定性 seed 和故障生成思路，删除长期 `sys.path` 注入 |
| `tools/synthetic_sweep_generator.py` | 合成 DC sweep CSV | **保留为示例并接入领域模型** | 当前能独立生成数据，但与 TestRun/质量模型分离 |
| `tests/test_crc.py` | CRC 标准向量 | **保留并扩展** | 增加独立模块、更多边界和编码往返 |
| `tests/test_protocol.py` | 帧、CRC、命令和字段错误 | **保留并扩展** | 增加版本、能力、流式分段、序列和黄金文件 |
| `tests/test_dc_sweep.py` | 拟合和饱和测试 | **保留并扩展** | 增加 NaN/Inf、排除原因、输入顺序、残差和质量标记 |
| `tests/test_hysteresis.py` | 转换和错误测试 | **保留并扩展** | 增加非法状态、多个转换、方向和重复性 |
| `pyproject.toml` | 最小 setuptools 配置 | **重构** | 改为 `src` 布局、产品元数据、开发依赖和可重复安装测试 |
| `README.md` | Phase 0 状态和入口 | **保留并持续更新** | 当前证据边界正确；软件产品使用流程后续补充 |
| `docs/DEVELOPMENT_SPEC.md` | 原始规格 | **冻结保留** | 作为历史需求来源，不用软件优先计划覆盖原文 |
| `docs/PRODUCT_PLAN.md` | 当前执行基准 | **保留** | 后续状态和变更从此追踪 |
| `firmware/`、`hardware/` | 未来硬件占位与采购资料 | **后置** | Software v1 不依赖这些目录完成 |

## 4. 已验证的可复用基础

### 4.1 CRC 和基本帧

- CRC-16/CCITT-FALSE 参数正确；
- 标准向量、空输入和大小写敏感测试存在；
- 帧限制为 128 bytes；
- 非 ASCII、内嵌换行、错误 CRC 和部分字段越界能够拒绝；
- telemetry 构建与解析可往返。

### 4.2 DC 分析

- 普通最小二乘增益、偏置和 R² 计算存在；
- 固定输出阈值可以区分保留点和排除点；
- 点数不足和输入全相同能够报错。

### 4.3 迟滞分析

- 可以从上升 0→1 和下降 1→0 的相邻采样中估计中点；
- 可以计算上下阈值和宽度；
- 缺少转换和上下阈值反转能够报错。

### 4.4 合成工具

- telemetry simulator 使用固定随机种子，可重复生成数据；
- synthetic sweep generator 明确输出 `SYNTHETIC` 来源；
- 两个工具均能在当前环境执行。

## 5. 关键缺口

### 5.1 产品架构

- 核心代码仍位于名为 `dashboard` 的包中，UI、领域、协议和设备边界没有产品化分层；
- 不存在 `DeviceAdapter`、Capability、Measurement、TestRun 或 QualityFlag；
- 不存在 Simulator/CSV Replay/Serial 契约测试；
- AFE 与 MSP430 profile 尚未分离实现。

### 5.2 协议

- 没有协议版本和能力协商；
- 没有 ACK、错误响应、超时和重复序列策略；
- 没有流式接收缓冲，当前 parser 只能处理已切分好的完整记录；
- 没有原始字节、接收时间和拒绝原因记录模型；
- telemetry 的物理范围与未来设备能力没有关联。

### 5.3 数据与分析

- 模型没有数据来源、单位、质量标志和 schema 版本；
- DC sweep 不拒绝 NaN/Inf，也不保存残差和逐点排除原因；
- 饱和边界写死为 25/3275 mV；
- 迟滞算法没有验证状态只能为 0/1，也不检查扫描方向或重复周期；
- 校准、频响、PASS/FAIL 和报告尚未实现。

### 5.4 用户产品

- 没有正式 CLI 入口、Dashboard、安装验证或发布流程；
- 用户错误目前可能以 Python traceback 呈现；
- 没有示例项目、黄金数据、JSON 摘要或人类可读报告；
- 没有 CHANGELOG、CI、类型检查、lint 或 coverage 工具。

### 5.5 工程与版本控制

- Git 仓库没有首个 commit，所有文件都未跟踪，因此没有可恢复的版本基线；
- 当前 `.venv` 没有可由 `pip show` 找到的 setuptools，不能由现状推断干净安装一定成功；
- `mixed_signal_afe_validation_platform.egg-info` 是本地产物且被忽略，不是发布证据；
- 历史 smoke check 尚未全部进入 pytest，回归保护不足。

## 6. 结论

当前代码是有价值的 Phase 0 算法原型，不是成熟软件产品。建议：

- 保留 CRC、严格帧检查、拟合、饱和和迟滞算法及其测试意图；
- 在 Software Phase 1 建立 `src/analog_validation/` 的正式领域和协议核心；
- 不在 Phase 1 实现串口、GUI、硬件控制或复杂插件系统；
- 使用兼容测试或一次性迁移更新现有导入，避免长期维持两个核心实现；
- 完成 Phase 1 后再建立 SimulatorAdapter 和 CsvReplayAdapter。

没有任何审计结论提升硬件证据等级。硬件仍为未采购、未连接、未验证。

