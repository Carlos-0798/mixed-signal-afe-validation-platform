# Software Phase 4 文件级实施计划

**阶段名称：** 串口传输、对等控制器 profiles 与真实链路边界<br>
**规划状态：** 进行中，进度 1/8<br>
**预计时间：** 5–8 个初学者开发日<br>
**前置：** Software Phase 3 的分析、runner 与结构化结果兼容基线完成<br>
**硬件要求：** Steps 1–6 无；Step 7 可选使用已连接的 MSP430 LaunchPad<br>
**AFE 硬件验证：** 0

## 当前进度

- [x] Step 1：profile-neutral 有界字节流与序列连续性；
- [ ] Step 2：profile-neutral CRC envelope 与 AFE v1 兼容迁移；
- [ ] Step 3：串口发现、连接、超时、重连与原始帧日志；
- [ ] Step 4：AFE v1 serial profile；
- [ ] Step 5：MSP430 Equipment Health v1 只读 profile；
- [ ] Step 6：SerialAdapter、共用 workflow 与异常链路集成；
- [ ] Step 7：可选的 MSP430 只读串口 HIL；
- [ ] Step 8：黄金兼容、构建、文档和阶段收口。

Step 1 已增加 `analog_validation.transport`，使用设备无关的有界 LF 字节流状态机处理分段、粘包、超长记录和重新同步，并使用 profile 指定的位宽跟踪首次、连续、缺帧、重复、乱序和回绕序列。32 项集中测试和 1,079 项完整回归通过，正式 package 5,752/5,752 statements 覆盖。它尚未打开串口、实现设备 profile 或验证物理链路。

## 1. 本阶段解决什么

此前的 `decode_frame()` 接收的是“一条已经完整取得的记录”。真实串口交付的却是任意大小的 byte chunks：一条消息可能分三次到达，也可能三条消息一次到达；损坏设备还可能持续发送没有换行的 bytes。

Phase 4 在业务 profile 之前建立一个受限、可恢复的通信边界：

1. 从任意分段中恢复完整记录；
2. 对超长记录停止增长并丢弃到下一个 LF；
3. 在 profile 层分别验证 AFE 和 MSP430 的 CRC、字段与版本；
4. 明确记录 sequence gap、CRC 错误、timeout、断开与重连；
5. 把原始记录和接收上下文保留下来供审计；
6. 让 Simulator、CSV、AFE、MSP430 和未来控制器继续使用同一领域/分析接口。

## 2. 两个项目的对等独立边界

Analog Validation Studio 与 MSP430 Equipment Health Controller 是两个对等、独立的产品。它们不会合并，也不存在上下级、宿主/附属或所有权转移关系。

| 归属 | Analog Validation Studio | MSP430 Equipment Health Controller |
|---|---|---|
| 产品职责 | 通用采集、适配器、Measurement、分析、测试执行和报告 | 固件、传感采样、FRAM、设备状态、热控制和板端 UART 语义 |
| 仓库与发布 | 独立仓库、版本、测试统计、README 和发布记录 | 独立仓库、版本、测试统计、README 和发布记录 |
| 兼容接口 | 实现独立 `msp430-equipment-health.v1` profile/adapter | 提供公开、冻结的 UART Protocol v1 |
| 不允许的耦合 | 不导入另一个仓库，不包含其引脚、寄存器、DriverLib 或风扇业务逻辑 | 不依赖 Analog Studio 才能独立运行或展示 |
| 证据 | 只计算本仓库自己的 HOST/HIL/BENCH 结果 | 其 176 tests、FRAM 和 soak 证据继续归该项目 |

共享 CRC 参数和串口传输原则是接口兼容，不是项目合并。未来 RP2040、STM32 或仪器也应通过相同的 profile/adapter 扩展点接入。

## 3. 已对齐的 MSP430 外部接口基线

Software Phase 4 以 MSP430 项目的以下公开行为作为兼容输入：

- UART 115200 baud、8-N-1、ASCII、LF 输出、CRLF 输入；
- 完整接收记录上限 128 bytes；
- CRC-16/CCITT-FALSE，检查向量 `123456789 -> 0x29B1`；
- `TEL`、`CMD`、`ACK`、`STS`、`CFG` 和 `LOG` 消息家族；
- telemetry sequence 为无符号 32-bit，时间为设备 `uptime_ms`；
- 当前冻结设备基线为 MSP430 Git commit `151fdcfa60661bce1ba04af13c1d3509706f7d4a` 和正常固件 `0.3.2-phase6-protocol`。

这些信息用于设计本项目自己的兼容 profile，不会把另一个仓库复制为运行时依赖。外接 DS18B20、NTC、INA219、MOSFET、风扇和 5 V 电源尚未在 MSP430 项目中完成 BENCH 验证，因此其 unavailable sentinel 和 fault flags 必须作为不可用状态处理，不能变成测量零值或合成值。

## 4. 目标架构

```text
Serial backend / in-memory substitute
                 |
                 v
transport.stream       bounded chunks -> complete raw records
                 |
                 v
transport envelope     ASCII/token/CRC rules without device meaning
                 |
          +------+------+
          |             |
          v             v
    AFE v1 profile   MSP430 Health v1 profile
          |             |
          +------+------+
                 |
                 v
SerialAdapter -> DeviceCapabilities / Measurement / raw provenance
                 |
                 v
ReadWorkflow / analysis / exports / future CLI and Dashboard
```

依赖方向只能向下。transport 不得导入 profile、Measurement、analysis、GUI 或板卡 SDK；profile 不得打开 COM port；adapter 不得重新实现 CRC 或分析公式。

## 5. 已冻结的设计决策

### 5.1 字节流与业务解析分离

字节流层只识别 LF 和长度限制。它会原样保留 CRLF、非 ASCII、空行和损坏内容，交给具体 profile 决定是否接受。这避免通用 transport 隐式偏向 AFE 或 MSP430。

### 5.2 超长记录必须恢复

记录一旦超过 profile 声明的上限，状态机停止扩展有效 buffer，持续丢弃直到下一个 LF，并输出带丢弃 byte 数的结构化 issue。随后同一 chunk 中的合法记录仍可被接收。

### 5.3 sequence 位宽属于 profile

AFE v1 使用 16-bit sequence；MSP430 UART Protocol v1 使用 32-bit sequence。`SequenceTracker` 由 profile 提供位宽，使用 modular half-range 规则区分前进与旧帧。重复和乱序只报告，不把 high-water mark 向后移动。

### 5.4 profile 选择必须显式

不能根据板名、COM 号或 USB VID/PID 猜测当前固件能力。用户配置或握手结果必须明确指定 profile 和版本；不兼容版本返回明确错误。

### 5.5 MSP430 第一版只读

第一版兼容 profile 只声明读取 telemetry/status 所需能力，不声明自动输出、风扇 PWM 刺激或 `SAFE_SHUTDOWN`。MSP430 `SET FAN_PWM` 不等于 AFE stimulus，不能借用来运行 DC sweep 或迟滞 runner。

### 5.6 证据不跨仓库继承

MSP430 项目的两小时 soak 证明其自身固件/Dashboard 链路，不证明 Analog Studio adapter。Step 7 必须由本仓库自己的代码、配置、raw log 和报告产生新的兼容性证据。即使完成，也只能声称 MSP430 串口/profile 兼容，不代表 AFE、外部传感器或风扇通过 BENCH。

## 6. 八个实施检查点

### Step 1：profile-neutral 有界字节流与序列连续性

新增 `transport/stream.py` 和 `transport/sequence.py`。冻结 chunk feed、complete raw records、overlong issue、disconnect reset、16/32-bit wrap、gap、duplicate 和 out-of-order 行为。保持 Phase 1–3 公开 namespaces 不变。

验收：分段、粘包、exact limit、跨 chunk 超长、同 chunk 恢复、任意 bytes、reset、16/32-bit wrap 和 half-range 歧义均有测试；正式包覆盖保持 100%。

**状态：已完成。** 32 项集中测试和 1,079 项完整回归通过；新增 158 statements 全覆盖。没有打开串口或使用硬件。

### Step 2：profile-neutral CRC envelope 与 AFE v1 兼容迁移

把当前 `protocol/framing.py` 中硬编码的 `AFE` namespace 拆为通用 token/CRC envelope 与 AFE wrapper。保留现有 `encode_frame()`、`decode_frame()`、AFE v1 golden bytes 和 Phase 1–3 public API 的完全兼容。

同时冻结 channel naming policy，解决 wire mapper 的 `afe.chN.input_mv/output_mv` 与 Simulator/workflow 的 `afe.chN.input/output` 不一致。优先建立显式 mapping，不静默重命名旧记录。

验收：旧 20 valid + 9 invalid AFE records byte-for-byte 不变；通用 envelope 能解析无 `AFE` namespace 的 MSP fixture，但不解释其业务字段。

### Step 3：串口 lifecycle 与原始帧日志

定义可替换的 serial backend port，实现发现、打开、bounded read、timeout、disconnect、有限重连和 deterministic close。正式 package 可以把 pyserial 放在可选 extra，核心导入仍不得要求 serial driver。

原始事件至少保留 received bytes、UTC receive time、port identity、profile、parse result/error 和 sequence observation。日志必须有数量/大小边界和隐私说明。

验收：使用内存 backend 覆盖 partial read、multiple records、timeout、open/read/close failure、disconnect/reconnect 和 overlong recovery；无真实 COM 依赖。

### Step 4：AFE v1 serial profile

把现有 AFE v1 encode/decode/mapping 包装为 serial profile，实现 profile identity、16-bit sequence、capability exchange 和 record/error mapping。保持 AFE 是独立业务 profile，不把 MSP 字段加入其消息。

验收：全部旧 AFE golden records 通过新的 profile 路径；能力和安全 gate 不退化；尚无 AFE 设备时标记 HOST_TEST only。

### Step 5：MSP430 Equipment Health v1 只读 profile

从冻结的 MSP430 protocol 文档和 golden fixtures 创建本仓库自己的互操作样本，解析 `TEL`，可选解析 `ACK/STS/CFG/LOG`，使用 32-bit sequence，并映射为通用 Measurement/status。

关键语义：温度 `-32768` 映射为 `value=None`、`INVALID` + `MISSING`；INA219 communication fault 存在时，随帧零电压/电流/功率为 unavailable；raw sentinel/fault bits 必须保留。第一版 capabilities 为只读且 `safe_shutdown=false`。

验收：合法、坏 CRC、坏字段、sentinel、fault、32-bit wrap 和 unknown state fixtures 全部冻结；不导入 MSP430 仓库代码。

### Step 6：SerialAdapter 与产品内复合链

组合 backend、stream、profile、sequence、raw log 与 `DeviceAdapter` 生命周期。让 AFE/MSP profile 通过同一 adapter 接口进入现有 `ReadWorkflow`，并保证关闭和重连路径不会提升 evidence。

验收：`config -> SerialAdapter -> raw stream -> profile -> Measurement -> ReadWorkflow -> export` 在内存 backend 中通过；只读 MSP 对 DC/迟滞 output runner 返回 `UNSUPPORTED` 且零写入。

### Step 7：可选 MSP430 只读串口 HIL

在 owner 确认板卡仍运行冻结固件、端口正确且允许只读访问后，使用本项目 SerialAdapter 读取 telemetry。默认不发送命令、不刷写、不改变 FRAM、不要求外接器件。

验收：记录设备/固件 identity、端口、配置、连续帧、CRC、sequence/uptime、sentinel/fault、timeout 和断开/重连结果；输出 Analog-owned HIL 报告。如果设备不可用，明确标记 `NOT RUN`，不阻塞 host-compatible Phase 4 closure。

### Step 8：黄金兼容、构建与阶段收口

冻结 Phase 4 public API、profile schemas、AFE/MSP golden records、端到端内存串口结果和错误层级。运行完整 pytest/coverage/Ruff/mypy/build/外部安装检查，更新 README、status、traceability、风险和 GitHub 展示材料。

验收：旧 Phase 1–3 golden contracts 不变；Phase 4 新接口可由外部 adapter 使用；真实 HIL 与 host-only 结果分栏；硬件 claims 不扩大到 AFE 或 MSP 外设。

## 7. 阶段出口条件

- transport 不包含设备业务、Measurement 分析或 GUI；
- AFE 和 MSP430 profiles 具有独立名称、版本、fixtures 和 capability 声明；
- 分段、粘包、超长、坏 CRC、sequence gap、timeout、断线和重连测试通过；
- 原始 bytes、错误和 provenance 可追溯且有资源边界；
- 只读设备不会获得输出能力；
- 没有板卡时仍能完成 host compatibility；
- 使用板卡时，只报告本项目实际执行的只读 HIL；
- 两个项目继续保持独立仓库、产品身份、证据和发布路线。

## 8. 安全与停止条件

- Step 7 前不访问物理端口；
- 没有 owner 明确授权不发送设备命令或刷写；
- 不把 COM4 写死为公共 API；
- 不用 wire color、板名或 USB identity 推断电气能力；
- 不把 unavailable sentinel 当作零值；
- 不把 upstream 项目测试数计入本项目；
- 发现未知固件、协议漂移、端口竞争或重复断连时停止 HIL，保留 raw evidence；
- AFE 电路、外部 5 V、传感器、风扇和任何接线不属于 Software Phase 4。

## 9. 下一检查点

Step 2 将只重构 profile-neutral token/CRC envelope、保留 AFE v1 byte compatibility，并冻结 channel naming mapping。它不会打开串口、实现 MSP430 业务 profile或运行物理 HIL。
