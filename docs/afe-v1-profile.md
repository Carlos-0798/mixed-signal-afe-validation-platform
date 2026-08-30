# AFE v1 Profile

**Profile name:** `afe`  
**Wire namespace:** `AFE`  
**Profile version:** `1`  
**Evidence:** HOST_TEST only  
**Hardware validation:** None

本文定义独立 Analog Front-End Validation Platform 的第一版业务协议。它使用 Step 5 已验证的 ASCII CSV framing 和 CRC-16/CCITT-FALSE，但不属于任何特定 MCU。

## 1. 分层关系

```text
UART bytes
  -> bounded ASCII/CSV/CRC framing
  -> AFE v1 profile and field validation
  -> controller-neutral domain models
  -> future adapter/test runner/report
```

Framing 只确认“信封完整”；AFE v1 确认“信封中是哪种消息、字段类型和范围是什么”；领域模型再提供来源、质量、安全范围和测试语义。

## 2. 版本化 envelope

所有 AFE v1 payload 均以以下字段开头：

```text
AFE,1,<message_type>,...
```

- `AFE` 表示独立 AFE 产品 namespace；
- `1` 是 profile 版本，不是板卡版本或固件版本；
- 不是版本 `1` 的记录抛出 `UnsupportedProtocolVersion`；
- MSP430 Equipment Health Controller 的业务消息不会使用这个 profile，后续使用独立 profile/adapter。

## 3. Telemetry

```text
AFE,1,TEL,<seq>,<time_ms>,<channel>,<input_mv>,<output_mv>,<gain_milli>,<threshold>,<fault_hex>,<crc16>
```

| 字段 | 范围或格式 |
|---|---|
| `seq` | unsigned 16-bit |
| `time_ms` | unsigned 32-bit uptime；不是 UTC 时间 |
| `channel` | unsigned 8-bit channel index |
| `input_mv`, `output_mv` | signed 16-bit integer millivolts |
| `gain_milli` | unsigned 16-bit；`1000` 表示 1.000 ratio |
| `threshold` | `0` 或 `1` |
| `fault_hex` | 四位大写十六进制 |

映射到通用领域模型时，一帧生成四条 Measurement：input、output、gain 和 threshold。Measurement 时间使用主机收到记录时的带时区时间，而不是把设备 uptime 错当作 UTC。

如果 `fault_hex != 0000`，映射结果为 `SUSPECT + DEVICE_FAULT`。v1 不解释各 fault bit 的具体含义，避免在 fault assignment 冻结前制造错误语义。

## 4. Commands

| 含义 | Payload 形状 | 通用 Capability |
|---|---|---|
| Read status | `AFE,1,CMD,<seq>,GET,STATUS,<channel>` | `READ_MEASUREMENT` |
| Read digital | `AFE,1,CMD,<seq>,READ,DIGITAL,<channel>` | `READ_DIGITAL_STATE` |
| Set gain | `AFE,1,CMD,<seq>,SET,GAIN,<channel>,<0..255>` | `RUN_DEVICE_COMMAND` |
| Set filter | `AFE,1,CMD,<seq>,SET,FILTER,<channel>,<0..255>` | `RUN_DEVICE_COMMAND` |
| Analog stimulus | `AFE,1,CMD,<seq>,SET,STIMULUS_MV,<channel>,<int16>` | `SET_ANALOG_STIMULUS` |
| PWM stimulus | `AFE,1,CMD,<seq>,SET,PWM_PERMILLE,<channel>,<0..1000>` | `SET_PWM_STIMULUS` |
| DC sweep | `AFE,1,CMD,<seq>,RUN,DC_SWEEP,<channel>` | `RUN_DEVICE_COMMAND` |
| Hysteresis | `AFE,1,CMD,<seq>,RUN,HYSTERESIS,<channel>` | `RUN_DEVICE_COMMAND` |
| Frequency sweep | `AFE,1,CMD,<seq>,RUN,FREQUENCY_SWEEP,<channel>` | `RUN_DEVICE_COMMAND` |
| Save calibration | `AFE,1,CMD,<seq>,SAVE,CALIBRATION` | `RUN_DEVICE_COMMAND` |
| Safe shutdown | `AFE,1,CMD,<seq>,SAFE,SHUTDOWN` | `SAFE_SHUTDOWN` |

编码器只接受经过 dataclass 验证的 `AfeCommand`。解析器拒绝多余字段、缺失字段、未知命令和越界值。

## 5. Capability exchange

### 5.1 Request

```text
AFE,1,CAP_REQ,<seq>,<crc16>
```

### 5.2 Multi-record response

能力响应由一条 DEVICE、零至多条 CHANNEL 和一条 END 组成。所有记录使用相同 sequence。

```text
AFE,1,CAP,<seq>,DEVICE,<device_id>,<command_mask_hex>,<crc16>
AFE,1,CAP,<seq>,CHANNEL,<ADC|DAC|PWM>,<index>,<minimum>,<maximum>,<unit>,<crc16>
AFE,1,CAP,<seq>,CHANNEL,DIN,<index>,-,-,-,<crc16>
AFE,1,CAP,<seq>,END,<entry_count>,<crc16>
```

采用多记录响应的原因是单个 capability snapshot 可能超过 128-byte framing 上限。分记录后每个通道都有独立单位和安全范围，也能在不推翻 envelope 的情况下增加通道。

### 5.3 Command mask

| Bit | DeviceCommand |
|---:|---|
| `0x0001` | `READ_MEASUREMENT` |
| `0x0002` | `READ_DIGITAL_STATE` |
| `0x0004` | `SET_ANALOG_STIMULUS` |
| `0x0008` | `SET_PWM_STIMULUS` |
| `0x0010` | `RUN_DEVICE_COMMAND` |
| `0x0020` | `SAFE_SHUTDOWN` |

未知 bit 被拒绝，不能被静默当作“可能支持”。

### 5.4 领域命名

AFE v1 将 numeric index 映射为：

- `adc0`…`adc255`；
- `dac0`…`dac255`；
- `pwm0`…`pwm255`；
- `din0`…`din255`。

这套命名只属于 AFE profile mapping。通用 `DeviceCapabilities` 仍不依赖板卡寄存器、引脚或 SDK 名称。

## 6. Capability 与 safety 的错误区别

执行命令前，`validate_command_capability` 检查：

1. profile name/version；
2. 设备是否明确声明所需命令；
3. channel 是否存在；
4. 自动输出是否声明 SAFE_SHUTDOWN；
5. 输出单位和值是否位于声明安全范围。

设备没有能力或 channel 时抛出 `CapabilityError`；输出数值或单位不安全时抛出 `ConfigurationError`。这让未来 UI 能正确显示“当前设备不支持”和“请求配置危险”两种不同问题。

## 7. 当前限制

- 没有串口 transport、超时、重试或 sequence tracker；
- capability 多记录收集目前是纯函数，不处理真实异步到达；
- 没有 ACK/NACK message；
- 没有冻结 fault-bit assignment；
- 没有固件实现或 controller contract test；
- 合成工具已经迁移到正式 AFE v1 API，但完整 SimulatorAdapter 属于 Phase 2；
- 所有范围都来自测试 fixture，不是硬件安全证据。

## 8. 证据边界

AFE v1 单元测试、20 条合法黄金消息、9 类非法黄金消息和 100 帧确定性集成流水线验证 Python model、编码、解析、映射和错误分类。它们不能证明 UART 电气、固件 parser、ADC/DAC、AFE 电压范围、safe shutdown 时序或任何实物性能。
