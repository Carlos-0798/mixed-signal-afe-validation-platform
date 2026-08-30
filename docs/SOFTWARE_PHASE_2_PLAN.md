# Software Phase 2 文件级实施计划

**阶段名称：** 适配器框架、模拟器与 CSV 回放<br>
**预计时间：** 4–6 个初学者开发日<br>
**前置：** Software Phase 1 的版本化核心和黄金兼容测试完成<br>
**硬件要求：** 无

## 当前进度

- [x] Step 1：`DeviceAdapter` 公共契约、生命周期和主机侧输出安全门；
- [x] Step 2：可复用适配器契约测试；
- [ ] Step 3：确定性 `SimulatorAdapter` 基本数据流；
- [ ] Step 4：模拟增益、偏置、噪声、饱和、迟滞和受控故障；
- [ ] Step 5：严格、不可变的版本化 CSV replay 格式与 parser；
- [ ] Step 6：`CsvReplayAdapter` 的速度、暂停、恢复和结束状态；
- [ ] Step 7：同一上层工作流和明确 `UNSUPPORTED` 能力降级；
- [ ] Step 8：集成、打包、文档和 Software Phase 2 报告收口。

Step 1–2 的真实执行证据见 `reports/software-phase2-step1.md` 和 `reports/software-phase2-step2.md`。下一步是实现确定性、只读起步的 SimulatorAdapter，并让它继承同一契约测试。

## 1. 阶段目标

让产品在完全没有硬件的情况下，通过同一个公共接口运行模拟数据和历史文件回放。适配器只负责“如何取得或发送数据”，领域模型、分析和报告不得知道底层是模拟器、CSV、串口、MSP430 还是未来仪器。

本阶段完成后形成软件 MVP 的设备层基础，但测试 runner、CLI、Dashboard、串口和实物控制仍属于后续阶段。

## 2. 目标目录

```text
src/analog_validation/adapters/
├── __init__.py
├── base.py
├── simulator.py
└── csv_replay.py

tests/
├── contracts/
│   └── test_device_adapter_contract.py
├── unit/
│   ├── test_adapter_base.py
│   ├── test_simulator_adapter.py
│   └── test_csv_replay_adapter.py
└── integration/
    └── test_phase2_adapter_workflow.py

test-data/replay/
├── valid/
└── invalid/
```

## 3. 生命周期与安全语义

```text
DISCONNECTED
  -> CONNECTED_READ_ONLY
  -> CAPABILITIES_CONFIRMED
  -> ARMED
  -> RUNNING
  -> SAFE_SHUTDOWN
  -> DISCONNECTED
```

- `connect` 只能建立只读连接，不能隐式产生输出；
- 获取并验证 `DeviceCapabilities` 后才能读设备数据；
- `ARMED` 必须同时通过版本化配置、设备能力、安全范围和 `SAFE_SHUTDOWN` 检查；
- `set_stimulus` 只允许从 `ARMED`/`RUNNING` 调用；
- 测试结束、异常或中止时先尝试 `safe_shutdown`，再释放资源；
- 模拟和回放模式永远不能把数据标成 `BENCH_*`，也不能访问真实串口。

## 4. 小步实施顺序

### Step 1：公共契约与状态机

创建 `AdapterState`、`DeviceAdapter` 和稳定 adapter 错误类型。公共方法负责状态检查、能力检查、配置检查、单位/来源检查和安全关闭；具体适配器只实现受保护 hook。

验收：越级读取、未解锁输出、超范围输出、错误来源和错误单位均被稳定错误拒绝；断开时清理状态；所有测试无硬件运行。

### Step 2：契约测试

把所有适配器都必须满足的行为整理为可复用测试，包括连接/断开幂等性、能力缓存、来源一致性、只读行为、结束状态和错误分类。Simulator 与 CSV Replay 必须运行同一套契约测试。

### Step 3：基础 SimulatorAdapter

把 Phase 1 的确定性生成器迁入正式 package，使用可注入 seed 与 clock，输出正式 `Measurement`，并公开明确的模拟能力。相同 seed、配置和读取顺序必须产生相同结果。

### Step 4：模拟非理想和故障

逐项加入可配置增益、偏置、噪声、上下限饱和、迟滞、丢帧和协议/通信故障。故障必须通过质量标志或稳定错误表达，不能生成伪造的 BENCH 数据。

### Step 5：CSV schema 与 parser

定义版本、列、单位、UTC 时间、来源、质量和结束条件。读取采用严格验证，不执行文件内容，不覆盖原始文件，不静默猜单位或来源。

### Step 6：CsvReplayAdapter

支持顺序回放、速度倍率、暂停、恢复和明确 EOF。回放生成新记录时保留原记录引用，并统一标记 `CSV_REPLAY`；原文件内容和时间戳不被修改。

### Step 7：共享工作流与能力降级

用同一上层函数驱动 Simulator 和 CSV Replay。当配置需要缺失能力时，生成明确 `UNSUPPORTED`，而不是崩溃、假装执行或让整个平台失效。

### Step 8：阶段收口

完成端到端测试、隔离构建、仓库外安装、README、状态、需求追踪、技术债和 Phase 2 报告。冻结 replay 黄金文件和公共 adapter API。

## 5. 明确不做

- 不安装或调用 pyserial；
- 不扫描 COM 端口；
- 不连接 MSP430、STM32、RP2040 或实验室仪器；
- 不执行真实 ADC/DAC/PWM 输出；
- 不实现测试 runner、CLI 或 Dashboard；
- 不把 Simulator/CSV Replay 描述成硬件测量；
- 不在本阶段采购 AFE 专用硬件。

## 6. 阶段出口条件

- Simulator 与 CSV Replay 实现同一 `DeviceAdapter` 契约；
- 生命周期和输出安全转换有自动测试；
- 模拟器可重复且可注入规划内故障；
- replay 不修改原文件且有明确来源、暂停和结束状态；
- 能力不足产生 `UNSUPPORTED` 语义；
- 核心仍不依赖串口、GUI、板级 SDK 或真实硬件；
- 软件声明继续区分 `HOST_TEST`、`SYNTHETIC`、`CSV_REPLAY` 和未验证硬件。
