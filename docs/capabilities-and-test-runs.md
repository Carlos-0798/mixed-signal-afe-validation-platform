# Capability 与 TestRun 模型

**版本：** `capabilities.v1` / `test-run.v1`  
**当前证据：** HOST_TEST  
**硬件验证：** 无

本文说明 Software Phase 1 Step 4 新增的两个产品级基础模型。它们不连接真实串口、不控制输出，也不代表任何板卡或 AFE 已经通过实测。

## 1. 初学者先理解两个问题

### 1.1 Capability：设备“明确说自己能做什么”

不同控制器的硬件资源不同。例如有些板有 ADC，但没有 DAC；有些只能 PWM 输出；有些能输出，却没有软件可调用的安全关闭命令。如果软件只看到“MSP430”或“RP2040”这个名称就自行猜测功能，很容易执行不存在或不安全的操作。

`DeviceCapabilities` 因此只接受明确数据：

- 设备 ID、协议 profile 名称和版本；
- ADC、DAC、PWM、数字输入通道；
- 每个模拟输入/输出通道的安全范围和单位；
- 设备明确支持的命令；
- 是否明确支持 `SAFE_SHUTDOWN`。

软件不会根据板卡名称、USB VID/PID 或厂商推导这些能力。这是平台能够兼容 MSP430、其他 MCU、模拟器和未来仪器适配器的关键。

### 1.2 TestRun：一次测试“到底形成了什么结论”

测试程序启动过，不等于测试通过。数据缺失、设备不支持、中途停止和程序错误都不能显示为 PASS。

`TestRunResult` 使用六种互斥结果：

| 结果 | 含义 | 可以当作完成的工程结论吗 |
|---|---|---|
| `PASS` | 必需数据完整，按规则判定通过 | 可以 |
| `FAIL` | 必需数据完整，按规则判定失败 | 可以 |
| `INCOMPLETE` | 缺少必需数据或步骤 | 不可以 |
| `UNSUPPORTED` | 当前设备缺少必需能力 | 不可以 |
| `ABORTED` | 用户或系统中止 | 不可以 |
| `ERROR` | 执行期间发生错误 | 不可以 |

模型强制 `PASS`/`FAIL` 必须引用证据记录，而且不能同时存在缺失要求；`INCOMPLETE`/`UNSUPPORTED` 必须明确列出缺少什么。因此“不完整却显示 PASS”在领域模型层就会被拒绝。

## 2. 安全范围如何工作

`SafeRange` 是带单位的闭区间。例如 `0.0–3.3 V` 表示两个端点也在声明范围内。它只接受有限数值，拒绝布尔值、字符串、NaN 和正负无穷。

`ChannelRange` 把一个通道与一个范围绑定。`DeviceCapabilities` 要求：

- 安全输入范围必须恰好覆盖所有声明的 ADC 通道；
- 安全输出范围必须恰好覆盖所有声明的 DAC/PWM 通道；
- 通道名和范围不能重复；
- 一个命令只有在对应通道存在时才能被声明；
- `supports_safe_shutdown` 与 `SAFE_SHUTDOWN` 命令必须一致。

在未来自动输出前，`require_automated_output(...)` 会依次检查：命令、通道、安全关闭能力、单位和数值范围。能力缺失抛出 `CapabilityError`；用户配置的单位或数值不安全则抛出 `ConfigurationError`。两者分开后，界面才能告诉用户究竟是“设备做不到”还是“请求本身不安全”。

注意：当前只是主机端安全门模型。没有硬件连接，也没有验证 0–3.3 V 对未来实物一定安全。真正范围必须在选型、数据手册审查和实物验证后由版本化 profile 填入。

## 3. TestRun 保存什么

`TestRunMetadata` 保存形成可复现记录所需的最小信息：

- 运行 ID 和测试类型；
- 配置 ID 与配置版本；
- 带时区的开始/结束时间，统一存为 UTC；
- 软件版本；
- 设备 ID、profile 名和 profile 版本；
- 明确的证据来源；
- 原始输入记录 ID；
- test-run schema 版本。

`TestRunResult` 再保存最终结果、摘要、结果证据 ID 和缺失要求。所有集合在构造时被冻结，避免测试结束后被其他代码悄悄修改。

## 4. 示例

下面的示例只描述模拟器能力，不表示真实硬件安全：

```python
from analog_validation import (
    ChannelRange,
    DeviceCapabilities,
    DeviceCommand,
    MeasurementUnit,
    SafeRange,
)

capabilities = DeviceCapabilities(
    device_id="simulator-001",
    profile_name="afe-simulator",
    profile_version="1.0",
    dac_channels=("dac0",),
    safe_output_ranges=(
        ChannelRange("dac0", SafeRange(0.0, 3.3, MeasurementUnit.VOLT)),
    ),
    supported_commands=frozenset(
        {DeviceCommand.SET_ANALOG_STIMULUS, DeviceCommand.SAFE_SHUTDOWN}
    ),
    supports_safe_shutdown=True,
)

capabilities.require_automated_output(
    DeviceCommand.SET_ANALOG_STIMULUS,
    "dac0",
    1.65,
    MeasurementUnit.VOLT,
)
```

## 5. 当前边界与后续步骤

- Step 4 没有实现 capability 的串口请求/响应；AFE v1 profile 在 Step 6 定义。
- Step 4 没有执行真实测试；Simulator/CSV/Serial adapter 在后续阶段接入。
- Step 4 没有完成判定引擎；当前只保证结果对象不能把缺失数据伪装为 PASS。
- Step 4 没有证明任何物理电压、精度、接线或安全关闭行为。
- `BENCH_*` 仍只是受控来源标签；真正 BENCH 证据必须来自实物执行记录。
