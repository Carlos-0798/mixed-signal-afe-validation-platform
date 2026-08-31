# Software Phase 4 文件级实施计划

**阶段名称：** 串口传输、对等控制器 profiles 与真实链路边界<br>
**规划状态：** 进行中，进度 6/8<br>
**预计时间：** 5–8 个初学者开发日<br>
**前置：** Software Phase 3 的分析、runner 与结构化结果兼容基线完成<br>
**硬件要求：** Steps 1–6 无；Step 7 可选使用已连接的 MSP430 LaunchPad<br>
**AFE 硬件验证：** 0

## 当前进度

- [x] Step 1：profile-neutral 有界字节流与序列连续性；
- [x] Step 2：profile-neutral CRC envelope 与 AFE v1 兼容迁移；
- [x] Step 3：串口发现、连接、超时、重连与原始帧日志；
- [x] Step 4：AFE v1 serial profile；
- [x] Step 5：MSP430 Equipment Health v1 只读 profile；
- [x] Step 6：SerialAdapter、共用 workflow 与异常链路集成；
- [ ] Step 7：可选的 MSP430 只读串口 HIL；
- [ ] Step 8：黄金兼容、构建、文档和阶段收口。

Step 1 已增加 `analog_validation.transport`，使用设备无关的有界 LF 字节流状态机处理分段、粘包、超长记录和重新同步，并使用 profile 指定的位宽跟踪首次、连续、缺帧、重复、乱序和回绕序列。

Step 2 已把 ASCII token、terminator、长度和 CRC 规则拆到 `protocol.envelope`，原 `framing.py` 成为完全兼容的 AFE wrapper；新增三个 profile-neutral 黄金形状、Step 1→2 分段复合链和 `afe-channel-map.v1` 显式 legacy/canonical mapping。51 项新增测试、1,130 项完整回归和 5,846/5,846 正式 package statements 通过。它仍未打开串口、解释 MSP430 业务字段、实现设备 profile 或验证物理链路。

Step 3 已新增 replaceable `SerialBackend` port、`SerialSession` 生命周期和 `BoundedRawEventLog`。发现、打开、bounded read、正常 timeout、断线清半帧、每次断线有限重连、确定性逻辑关闭、超长恢复和 raw event 的 `PENDING_PROFILE/PARSED/REJECTED` 状态都由故障可注入的内存 backend 验证。日志默认 1,024 条/256 KiB，仅驻留内存且不自动持久化或上传。88 项新增测试、1,218 项完整回归和 6,274/6,274 正式 package statements 通过；没有 OS backend、pyserial、COM I/O 或硬件证据。

Step 4 已新增 `analog_validation.profiles` 与独立 `AfeV1SerialProfile`。它明确声明 `afe`/`1`、16-bit telemetry sequence 和 128-byte record limit；旧 mapper 经显式 mapping 输出 canonical channels；capability 多记录响应严格聚合；协议错误进入 bounded `REJECTED` raw outcome，程序/状态错误不会冒充设备错误。全部 20 valid + 9 invalid AFE golden records 已通过新路径，完整回归为 1,277 项和 6,499/6,499 正式 statements；仍未访问 COM、MSP430 或 AFE 实物。

Step 5 已从对等项目提交 `151fdcfa60661bce1ba04af13c1d3509706f7d4a` 的公开 `docs/protocol.md` 独立实现 `msp430-equipment-health.v1`。本仓库自己的 10 条合法与 11 条非法 fixtures 冻结 `TEL/ACK/STS/CFG/LOG`、CRC、范围、unknown state 和 32-bit wrap。温度/INA219 unavailable 语义映射为 `None + INVALID + MISSING`，原始 sentinel、零值、power 和 fault bits 保留在 typed message；能力固定为只读且无 `SAFE_SHUTDOWN`。新增 121 项测试后完整回归为 1,398 项，正式 package 6,916/6,916 statements；没有导入对等仓库代码、打开 COM 或执行硬件操作。

Step 6 已新增独立 `analog_validation.serial_adapters` namespace，把一个显式选择的 `SerialSession`、`SerialProfile` 和 capability projector 组合到冻结的 `DeviceAdapter`/`ReadWorkflow` 契约。第一版严格 receive-only：无 write API、无 generic command escape hatch、输出命令被剥离且不声明 safe shutdown。AFE 的 `adcN/dacN/pwmN/dinN` 能力显式投影到 `afe.chN.input/dac/pwm/threshold`，同时保留 native snapshot；MSP430 使用静态只读能力。两个配置均通过共用八项 adapter contract 和产品 workflow；重连会使 capability/buffer 失效，DC/迟滞 runners 对 MSP430 返回 `UNSUPPORTED` 且零写入。新增 74 项测试后完整回归为 1,472 项，正式 package 7,198/7,198 statements；没有访问 COM、板卡或执行命令。

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

**状态：已完成。** 通用 envelope 与 AFE wrapper 分层完成；三条黄金 envelope records 可 exact decode/re-encode，其中两个为无 `AFE` namespace 的 MSP430 协议形状。旧 AFE API、20 valid、9 invalid、Phase 2/3 public manifests 和 synthetic stream 均未漂移。`afe-channel-map.v1` 要求显式声明 source/target naming，旧 telemetry mapper 不静默改名。51 项新增测试和 1,130 项完整回归通过；正式 package 5,846/5,846 statements 覆盖。没有 serial I/O 或硬件。

### Step 3：串口 lifecycle 与原始帧日志

定义可替换的 serial backend port，实现发现、打开、bounded read、timeout、disconnect、有限重连和 deterministic close。正式 package 可以把 pyserial 放在可选 extra，核心导入仍不得要求 serial driver。

原始事件至少保留 received bytes、UTC receive time、port identity、profile、parse result/error 和 sequence observation。日志必须有数量/大小边界和隐私说明。

验收：使用内存 backend 覆盖 partial read、multiple records、timeout、open/read/close failure、disconnect/reconnect 和 overlong recovery；无真实 COM 依赖。

**状态：已完成。** 正式核心保持标准库依赖，新增 428 个正式 package statements 全覆盖。故障可注入内存 backend 覆盖发现契约、生命周期状态、bytes-like/size 违规、partial/coalesced input、timeout、打开/读取/关闭故障、断线清半帧、0/1/2 次有限重连、超长恢复、UTC clock、raw log eviction/privacy 和 CRC envelope→sequence→parse/reject 复合链。完整 1,218 项回归、静态检查、隔离构建和仓库外 wheel smoke 通过。实际 COM、pyserial 和 MSP430 均未访问。

### Step 4：AFE v1 serial profile

把现有 AFE v1 encode/decode/mapping 包装为 serial profile，实现 profile identity、16-bit sequence、capability exchange 和 record/error mapping。保持 AFE 是独立业务 profile，不把 MSP 字段加入其消息。

验收：全部旧 AFE golden records 通过新的 profile 路径；能力和安全 gate 不退化；尚无 AFE 设备时标记 HOST_TEST only。

**状态：已完成。** 新 `serial-profile.v1` port 冻结显式 identity、typed result/reset 和 profile state error；AFE 实现复用原 decoder/CRC/capability/mapping，不加入 MSP 字段。TEL 独立使用 16-bit continuity，command/capability sequence 保持 transaction correlation，避免合法 capability 多记录被误报 duplicate。Telemetry 转为 canonical `afe.chN.*` Measurements；capability 仍保留冻结的 `adcN/dacN/pwmN/dinN` 安全语义，留待 Step 6 做显式 adapter projection。59 项新增测试、1,277 项完整回归、6,499/6,499 statements、构建和仓库外无 pyserial smoke 通过。证据见 `docs/serial-profiles.md` 和 `reports/software-phase4-step4.md`；硬件证据为 0。

### Step 5：MSP430 Equipment Health v1 只读 profile

从冻结的 MSP430 protocol 文档和 golden fixtures 创建本仓库自己的互操作样本，解析 `TEL`，可选解析 `ACK/STS/CFG/LOG`，使用 32-bit sequence，并映射为通用 Measurement/status。

关键语义：温度 `-32768` 映射为 `value=None`、`INVALID` + `MISSING`；INA219 communication fault 存在时，随帧零电压/电流/功率为 unavailable；raw sentinel/fault bits 必须保留。第一版 capabilities 为只读且 `safe_shutdown=false`。

验收：合法、坏 CRC、坏字段、sentinel、fault、32-bit wrap 和 unknown state fixtures 全部冻结；不导入 MSP430 仓库代码。

**状态：已完成。** `protocol.msp430_health_v1` 提供独立 immutable models、严格 device-output parser/encoder 和五个受支持单位的 Measurement mapping；`profiles.Msp430HealthV1SerialProfile` 提供显式 identity、32-bit TEL continuity、typed raw outcomes、失败回滚和静态只读 capabilities。`CMD` 只作为不支持输入被拒绝，正式代码不提供命令 encoder。10 valid + 11 invalid fixtures、sentinel/fault、unknown TEL state、unknown numeric LOG state、uint32 wrap、内存串口复合链和无对等 runtime import 均通过。120 项集中测试加 1 项架构门禁、1,398 项完整回归和 6,916/6,916 statements 通过；物理串口与硬件均未访问。

### Step 6：SerialAdapter 与产品内复合链

组合 backend、stream、profile、sequence、raw log 与 `DeviceAdapter` 生命周期。让 AFE/MSP profile 通过同一 adapter 接口进入现有 `ReadWorkflow`，并保证关闭和重连路径不会提升 evidence。

验收：`config -> SerialAdapter -> raw stream -> profile -> Measurement -> ReadWorkflow -> structured export-ready result` 在内存 backend 中通过；只读 MSP 对 DC/迟滞 output runner 返回 `UNSUPPORTED` 且零写入。通用 read-only workflow 的新文件格式不在本步骤临时发明，留给版本化导出需求单独评审。

**状态：已完成。** `SerialAdapterConfig` 冻结显式 profile name/version 与有界 poll/buffer policy；adapter 验证 session/profile/record-limit identity，保留 native/projected capabilities 和 bounded raw snapshot，并把 transport/profile failures 转成稳定 adapter 错误。AFE 和 MSP430 两种配置都通过共用契约；AFE 的内存 capability + telemetry 链进入 `ReadWorkflow` 并保留 raw lineage，MSP430 sentinel/fault 链进入同一 workflow 且保持 `HOST_TEST`。断线重连要求重新确认能力；CRC/超长/timeout/buffer overflow 均有边界测试。DC 与迟滞 runner 使用没有 write 方法的 backend，均在能力预检返回 `UNSUPPORTED`，实际 write 次数为 0。74 项新增测试、1,472 项完整回归、7,198/7,198 statements、140-file mypy、Ruff、依赖检查、隔离构建和仓库外无 pyserial 的安装后 SerialAdapter→ReadWorkflow smoke 通过。结构化 `ReadWorkflowResult` 已形成 export-ready lineage；本步骤没有新增文件导出格式。证据见 `reports/software-phase4-step6.md`。

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

Step 7 是可选、需要单独授权的 MSP430 只读串口 HIL。开始前必须确认板卡仍运行冻结的公开接口、目标 COM 端口属于该板且没有被其他程序占用，并先实现/验证最小 concrete OS backend。HIL 默认只接收设备主动 telemetry，不发送 `CMD`、不刷写、不改变 FRAM、不要求外接传感器或风扇。结果必须记录当前 identity、原始帧、CRC、sequence/uptime、sentinel/fault、timeout 和断连行为；任何前置条件不明确时标记 `NOT RUN`，不阻塞 Step 8 的 host-compatible 收口。
