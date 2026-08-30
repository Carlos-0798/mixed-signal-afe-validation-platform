# Software Phase 1 文件级实施计划

**阶段名称：** 领域模型、配置与协议核心  
**预计时间：** 3–5 个初学者开发日  
**前置：** Software Phase 0 审计和需求追踪矩阵完成  
**硬件要求：** 无

## 当前进度

- [x] Step 1：正式 `src/analog_validation/` 包、单一版本来源、editable install、独立 wheel 构建和仓库外导入；
- [x] Step 2：错误分类；
- [x] Step 3：来源、质量与通用测量模型；
- [x] Step 4：Capability 与 TestRun；
- [ ] Step 5：CRC 与 framing 迁移；
- [ ] Step 6：AFE v1 profile；
- [ ] Step 7：配置模型；
- [ ] Step 8：测试、文档和阶段报告收口。

Step 1–4 的真实执行证据见 `reports/software-phase1-step1.md` 至 `reports/software-phase1-step4.md`。

## 1. 阶段目标

把当前 Phase 0 原型迁移为正式、版本化、无硬件依赖的产品核心。此阶段不追求串口、Dashboard 或自动控制，而是建立后续所有功能共同依赖的可靠地基。

## 2. 目标目录

```text
src/analog_validation/
├── __init__.py
├── version.py
├── errors.py
├── domain/
│   ├── __init__.py
│   ├── enums.py
│   ├── measurements.py
│   ├── capabilities.py
│   └── test_runs.py
├── protocol/
│   ├── __init__.py
│   ├── crc.py
│   ├── framing.py
│   └── afe_v1.py
└── config/
    ├── __init__.py
    ├── models.py
    └── validation.py

tests/
├── unit/
│   ├── test_crc.py
│   ├── test_framing.py
│   ├── test_afe_v1.py
│   ├── test_domain_models.py
│   └── test_config.py
└── golden/
    └── test_protocol_golden.py

test-data/golden/
├── afe_v1_valid.csv
├── afe_v1_invalid.csv
└── expected_frames.json
```

Phase 1 完成后，旧 `dashboard/protocol.py`、`dashboard/models.py` 和相关测试应完成一次性迁移；不长期维护两套 CRC 或模型实现。UI 占位文件可暂时保留，但不能成为新核心的依赖。

## 3. 小步实施顺序

### Step 1：建立 src 包和版本

修改/创建：

- `pyproject.toml`；
- `src/analog_validation/__init__.py`；
- `src/analog_validation/version.py`；
- 安装和 import 测试。

验收：隔离环境执行 editable install，不能依靠仓库当前目录碰巧可导入。

### Step 2：错误分类

创建 `errors.py`：

```text
AnalogValidationError
├── ValidationError
├── ProtocolError
│   ├── FramingError
│   ├── FrameTooLong
│   ├── CrcMismatch
│   └── UnsupportedProtocolVersion
├── CapabilityError
└── ConfigurationError
```

验收：调用者可以按稳定错误类型处理问题，错误信息仍适合用户阅读。

### Step 3：来源、质量与通用测量模型

创建：

- `EvidenceSource`；
- `QualityFlag`；
- immutable `Measurement`；
- 原始记录 ID/引用；
- schema version。

关键验证：非有限值、未知单位、缺来源和非法时间必须拒绝或显式标记，不能默认为有效 BENCH 数据。

### Step 4：Capability 与 TestRun

创建：

- `DeviceCapabilities`；
- 安全输入/输出范围；
- 支持命令集合；
- `TestRunMetadata` 和 `TestRunResult`；
- `UNSUPPORTED` 与不完整结果语义。

此阶段只建模，不连接真实设备。

### Step 5：拆分 CRC 和 framing

从 `dashboard/protocol.py` 迁移：

- CRC 到 `protocol/crc.py`；
- ASCII、字段、长度和 CRC envelope 到 `protocol/framing.py`；
- 保留 128-byte 当前上限；
- 增加黄金向量和更多边界测试。

验收：现有合法帧保持可解析；错误类型更精确；CRC 只有一个实现来源。

### Step 6：AFE v1 profile

在 `protocol/afe_v1.py` 中定义：

- 明确 profile 名和版本；
- telemetry 与 command 结构；
- capability 请求/响应的最小形状；
- profile 到领域模型的映射；
- 超出设备能力和超出安全范围的区别。

此步骤不定义 MSP430 Health Controller 业务消息；它在 Software Phase 4 进入独立 profile。

### Step 7：配置模型

第一版优先使用标准库和明确 dataclass 验证，避免在需求尚小的时候引入重型依赖。配置至少覆盖：

- profile；
- 通道；
- 单位；
- 输出安全边界；
- 测试超时；
- 数据来源；
- schema version。

不允许配置执行 Python 表达式或任意代码。

### Step 8：迁移测试与更新文档

- 更新 imports；
- 把 100 帧往返变为 pytest；
- 建立黄金消息；
- 更新 `docs/protocol.md`；
- 更新需求追踪状态；
- 生成 Software Phase 1 报告。

## 4. 明确不做

- 不安装或实现 pyserial；
- 不连接 MSP430；
- 不实现 GUI/Dashboard；
- 不实现真实硬件输出；
- 不实现完整 SimulatorAdapter 或 CSV Replay Adapter；
- 不实现校准、频响或报告；
- 不采购硬件；
- 不把 package 重构描述成新增硬件能力。

## 5. 测试要求

- CRC 标准向量、空输入和字节敏感性；
- ASCII、长度、空字段、空白、换行和 CRC 错误；
- 合法帧编码/解析往返；
- 协议版本接受和拒绝；
- Measurement 来源、单位、有限值和质量标志；
- Capability 安全范围和支持命令；
- TestRun 不完整状态不得成为 PASS；
- 配置未知字段、缺字段、错误类型和危险范围；
- 100 条确定性 synthetic telemetry 集成测试；
- 当前 DC 和迟滞测试在迁移期间继续通过。

## 6. 阶段出口条件

- `src/analog_validation/` 是唯一正式核心；
- 干净环境安装和 import 通过；
- 当前测试全部迁移并通过；
- 关键协议和领域模型达到规划书的 90% coverage 目标或记录明确差距；
- 无串口、GUI、板级 SDK 或硬件依赖进入领域核心；
- 文档、需求追踪、技术债和实际测试报告同步更新；
- 硬件相关状态仍为 `DEFERRED`/未验证。
