# 独立产品架构

状态日期：2026-08-29

## 1. 产品身份

**Configurable Analog Front-End & Validation Platform 本身就是独立产品。**

它不是 MSP430 Equipment Health Controller 的扩展板、子模块或必需配件。MSP430只是一个受支持的外部系统和兼容性示例。产品必须能够被其他3.3 V MCU、USB验证控制器、实验室仪器或纯手动控制单独使用。

产品成熟形态包含三个可独立演进的部分：

```text
AFE Base Unit                 Optional Validation Controller       Host Software
独立模拟核心                  可替换自动化控制层                   控制/分析/报告

保护/缓冲/增益/滤波           ADC/DAC/PWM/边沿计时                 DeviceAdapter
Schmitt/物理配置              USB/UART/I2C/SPI                     协议与CRC
模拟/数字标准接口             参考实现可用STM32/RP2040/MSP430      校准/拟合/报告
```

三部分通过公开、版本化接口连接，不共享隐藏依赖。

## 2. AFE Base Unit：没有MCU也必须工作

这是产品最核心、最稳定的一层。断开所有MCU和电脑后，它仍必须能够：

- 接受安全范围内的0-3.3 V模拟输入；
- 提供输入保护和缓冲；
- 通过跳线、DIP开关或电位器选择增益；
- 选择至少两档低通滤波；
- 设置Schmitt Trigger阈值并输出数字状态；
- 输出调理后的模拟信号；
- 用测试点和LED提供基本可观察性。

模拟功能不能依赖固件启动、I2C配置或特定开发板供电。数字控制以后可以作为增强，但必须保留安全的手动默认状态。

## 3. Optional Validation Controller：可替换而非产品身份

验证控制器的作用是自动测试，不定义AFE产品本身。它可以是：

- STM32 NUCLEO-G474RE参考验证控制器；
- RP2040/Metro软件友好控制器；
- MSP430FR6989兼容性适配器；
- 未来定制USB控制板；
- 获得权限后的实验室仪器适配器。

任何一种控制器被替换时，AFE模拟核心的原理图、增益档、滤波档和保护设计都不应重做。

当前提议的NUCLEO-G474RE只是开发阶段的**参考验证控制器**：它提供DAC/PWM刺激、ADC采集、定时器边沿捕获和USB串口。它不是最终产品必须内置的MCU，也不会把产品变成STM32附属板。

## 4. Host Software：控制器无关

Python层只依赖公开协议和`DeviceAdapter`接口：

```text
DeviceAdapter
├── SimulatorAdapter
├── CsvReplayAdapter
├── SerialProtocolAdapter
│   ├── STM32 reference-controller profile
│   ├── RP2040 profile
│   └── MSP430 compatibility profile
└── FutureInstrumentAdapter
```

分析代码不得直接调用某块板的寄存器名、COM端口号或专用SDK。板级差异封装在adapter和capability描述中，例如：

```text
adc_channels
dac_channels
pwm_channels
digital_capture
max_safe_voltage_mv
supported_commands
firmware_protocol_version
```

如果某块板没有DAC，软件可以选择PWM-RC或手动输入策略，而不是让整个产品失效。

## 5. 公开电气与通信接口

V1接口原则：

- 逻辑电平：3.3 V nominal；除非单独验证，不宣称5 V tolerant；
- 模拟输入/输出：0-3.3 V范围，最终安全余量由实测决定；
- 必须有公共GND；电源输入和信号地清晰标注；
- 接口提供模拟输入、调理后输出、Schmitt数字输出、I2C、UART、可选SPI和配置GPIO；
- 连接器必须有方向、1脚、信号名和电压域标记；
- 上电默认配置不能短接输出、悬空关键输入或把未知控制器引脚直接驱动AFE；
- UART CSV/CRC协议保持控制器无关；I2C设备地址和寄存器行为单独版本化。

具体pinout在Phase 1接线冻结前定义。MSP430、STM32和RP2040各自拥有独立pin-map文档，不把某一个pin map写进AFE核心逻辑。

## 6. 产品工作模式

### Mode A：Standalone Analog Product

不连接MCU；用户使用旋钮/跳线配置，在测试点或输出端读取结果。这是最低独立产品能力。

### Mode B：Standalone USB Validation Product

AFE连接参考验证控制器和Python。用户可以自动DC sweep、阈值测试、数据记录和报告，不需要MSP430 Equipment Health Controller。

### Mode C：External Controller Integration

任意满足接口契约的3.3 V控制器都可读取模拟/数字输出或控制测试流程。MSP430FR6989是必须保留的兼容性示例之一，而不是唯一主控。

### Mode D：Laboratory Instrument Validation

函数发生器、示波器和电源通过独立适配器或人工流程提供更高可信度证据；实验室不可用不影响A/B模式开发。

## 7. 独立性验收标准

产品在以下检查全部通过前，不能称为独立和可复用：

- [ ] 拔掉MSP430后，手动缓冲、增益、滤波和Schmitt功能仍可工作；
- [ ] 拔掉所有MCU后，不会出现危险或未定义默认状态；
- [ ] Python合成/回放测试不导入任何板级SDK；
- [ ] 至少两个不同控制器profile可以使用同一UART协议或同一DeviceAdapter测试集；
- [ ] MSP430兼容性测试与AFE产品验收分开报告；
- [ ] 更换控制器不要求修改模拟核心原理图；
- [ ] README、BOM、接线、校准和发布包均以AFE产品命名，不以MSP430项目命名；
- [ ] 数据来源继续区分SYNTHETIC、SPICE、BENCH_DMM、BENCH_CONTROLLER和BENCH_SCOPE；
- [ ] 无实验室仪器时不声称高频、相位、噪声或校准级准确度已验证。

## 8. 对第二块板选型的影响

第二块板的选择标准从“是否替代MSP430”改为“是否是好的参考验证控制器”。因此NUCLEO-G474RE仍是合理候选，但其角色被严格限定：

- 它帮助开发和验证产品；
- 它不是AFE必须依赖的核心部件；
- 它可以在未来被RP2040、定制USB板或实验室仪器替换；
- 其固件属于独立adapter/reference-controller目录；
- AFE产品即使不附带NUCLEO也能以Standalone Analog Mode交付和使用。
