# Configurable Analog Front-End & Validation Platform

## 可配置模拟前端与自动化验证平台 - 完整开发规格书

**项目类型：** Independent Mixed-Signal Embedded Systems Project  
**主要平台：** MSP-EXP430FR6989 LaunchPad + 可配置模拟前端  
**可选独立主机：** RP2040/STM32 USB Adapter（后期）  
**文档版本：** 1.0  
**文档日期：** 2026-08-28  
**目标岗位：** Embedded Software、Firmware、Hardware Validation、Electrical/Test Engineering

---

## 1. 文档用途

本文档用于启动一个新的 Codex 开发任务，并作为项目需求、硬件边界、实现顺序和验收标准的初始依据。

项目目标不是复制课程实验，而是把课程中涉及的放大器、Schmitt Trigger、振荡器、VCO、滤波器和晶体管级，重新组织成一个可复用的低压模拟信号调理与自动化验证平台。

Codex 和开发者必须遵守：

- 数据手册参数与实物测量结果分开记录；
- 未完成硬件验证前，不得声称达到目标精度；
- 不接入 110V/220V 市电；
- 不覆盖用户已有项目和代码；
- 不将本项目与 OSU Lab Bench Monitor Capstone 混合；
- 本项目可以与 MSP430 Equipment Health Controller 集成，但保持独立仓库、文档和功能边界。

---

## 2. 项目定位

### 2.1 项目名称

**Configurable Analog Front-End & Validation Platform**  
中文：**可配置模拟前端与自动化验证平台**

### 2.2 核心问题

嵌入式控制器通常无法直接可靠地读取所有传感器信号。实际系统需要完成：

- 输入保护；
- 放大或衰减；
- 偏置和电平转换；
- 模拟滤波；
- 阈值和迟滞检测；
- 模数转换；
- 校准；
- 故障判断；
- 自动测试和记录。

本项目构建一款独立、低压、模块化且可复用的模拟前端产品，用于读取、调理和验证常见低速模拟传感器。它在没有MCU时保留完整的基本模拟功能，也允许MSP430或其他3.3V MCU、可替换USB验证控制器和实验室仪器通过公开接口接入。

### 2.3 最终产品形态

成熟版本是一块自制低压扩展板，具有：

- 两路 0-3.3V 模拟输入；
- 输入保护与缓冲；
- 可配置增益；
- 可配置低通滤波；
- Schmitt Trigger 数字阈值输出；
- 高精度外部 ADC；
- 测试信号输入/输出；
- I2C/SPI/GPIO 接口；
- 面向测量的测试点和端子；
- MSP430 集成模式；
- 独立模拟模式；
- Python 自动验证模式。

产品身份不由任何特定MCU定义。MSP430FR6989、STM32、RP2040和未来定制USB控制器只能作为可替换的兼容/验证profile，不能成为模拟核心工作的隐藏依赖。

---

## 3. 与其他项目的边界

### 3.1 与 Lab Bench Monitor 的关系

没有继承或从属关系。

Lab Bench Monitor 是 OSU Senior Capstone 小组项目。本项目是独立个人项目，不使用 Capstone 的仓库、团队成果、代码所有权或项目叙述。

### 3.2 与 MSP430 Equipment Health Controller 的关系

两个项目是可以通过公开接口协作、但分别成立和交付的独立产品：

```text
Independent Products with Public Integration Interfaces
│
├── MSP430 Equipment Health Controller（独立产品）
│   ├── 实时温度/功耗监测
│   ├── PWM 风扇控制
│   ├── FRAM 日志
│   └── 故障安全状态机
│
├── Configurable Analog Front-End & Validation Platform（独立产品）  <-- 本项目
│   ├── 放大、滤波和阈值检测
│   ├── 高精度 ADC
│   ├── 校准和故障注入
│   └── 独立模拟功能
│
└── 可选的 Python Diagnostic Console / Adapter Layer
    ├── 实时图形
    ├── 自动测量
    └── CSV/PDF 报告
```

两个项目保持独立：

- 独立仓库；
- 独立 README；
- 独立测试计划；
- 独立BOM、硬件验收和发布包；
- 独立 LinkedIn Project 条目；
- 通过明确的 3.3V、I2C/SPI/GPIO 接口集成；
- README 相互链接，但不复制或混淆成果。
- AFE在MSP430完全断开时仍满足Standalone Analog和Standalone USB Validation功能。

---

## 4. 三种工作模式

### 4.1 Standalone Analog Mode

不依赖 MCU，使用跳线、DIP 开关或电位器：

- 设置输入偏置；
- 选择放大倍数；
- 选择滤波档位；
- 设置 Schmitt Trigger 阈值；
- 输出调理后的模拟信号；
- 通过 LED 显示比较器状态。

这是硬件模块的最低独立功能。

### 4.2 External Controller Integrated Mode

模拟平台可与任意满足接口契约的3.3V控制器连接。MSP430FR6989是一个必须验证的兼容性profile，而不是产品唯一主控：

- MSP430 ADC12 读取模拟输出；
- MSP430 GPIO 读取比较器输出；
- I2C 读取 ADS1115；
- SPI 控制可选 AD9833；
- MSP430 运行校准、扫频和故障检测；
- UART 将数据发送到 Python Dashboard。

STM32、RP2040或未来定制USB控制器可以实现相同的版本化协议和capability接口。更换控制器不得要求修改AFE模拟核心。

### 4.3 USB Validation Mode

后期通过 RP2040/STM32 USB Adapter 或支持的 USB 测试仪器：

- 自动输入阶跃或扫频信号；
- 自动采集输入/输出；
- 计算增益、截止频率和迟滞；
- 运行故障注入；
- 自动生成测试数据和报告。

---

## 5. 项目范围

### 5.1 必须实现

| ID | 功能 | 最低验收标准 |
|---|---|---|
| FR-001 | 单通道输入缓冲 | 0-3.3V 输入范围内稳定、无明显振荡 |
| FR-002 | 可配置放大 | 至少支持 x1、x2、x5、x10 四档 |
| FR-003 | 低通滤波 | 至少支持两个可选择截止频率 |
| FR-004 | Schmitt Trigger | 可设置上下阈值并测量迟滞 |
| FR-005 | 控制器无关ADC采集 | 至少一个参考控制器能定时采集、单位换算、越界检测；MSP430兼容性单独验收 |
| FR-006 | 控制器无关UART遥测 | Python通过同一版本化协议读取输入、输出、增益档和数字阈值状态，不依赖板级SDK |
| FR-007 | 自动 DC Sweep | 自动生成或手动施加多点输入并计算增益 |
| FR-008 | Python Dashboard | 显示实时输入/输出、状态和测试结果 |

### 5.2 完整作品集功能

| ID | 功能 | 验收标准 |
|---|---|---|
| FR-101 | 双通道模拟输入 | 两路可以独立配置并采集 |
| FR-102 | ADS1115 采集 | 16-bit 低速精密采集和差分测量 |
| FR-103 | 自动频率扫描 | 输出扫频、采集结果并绘制幅频曲线 |
| FR-104 | 自动迟滞测试 | 自动计算上下切换阈值和迟滞宽度 |
| FR-105 | 校准 | 保存增益/偏置校准系数并应用到测量结果 |
| FR-106 | 故障注入 | 开路、短路、超范围、饱和和过度噪声测试 |
| FR-107 | 自动报告 | 导出 CSV 和测试摘要 |
| FR-108 | 自制 PCB | 原理图、布局、测试点和版本记录完整 |
| FR-109 | 独立模拟模式 | 不连接 MCU 时仍能完成基本放大/滤波/阈值功能 |
| FR-110 | 可替换控制器 | 至少两个controller profile通过同一DeviceAdapter契约；更换控制器不修改模拟核心 |

### 5.3 明确不做

- 市电测量；
- 高压差分探头；
- 医疗级或安全认证测量；
- MHz 级专业示波器；
- 高频 RF 前端；
- 商业计量仪器精度承诺；
- 第一版复杂数字电位器和模拟矩阵。

---

## 6. 电气设计边界

### 6.1 电压域

```text
数字逻辑：3.3V
模拟供电：3.3V，必要时局部使用 5V
允许的外部模拟输入：0-3.3V
MCU ADC 输入：必须保持在 0-VCC 范围
所有设备：公共 GND
```

禁止把负电压或超过 3.3V 的信号直接送入 MSP430 ADC、GPIO、ADS1115 或比较器输入。

### 6.2 单电源设计

第一版不使用 +/-12V 或 +/-15V 双电源。对于交流信号，建立约 1.65V 虚拟中点：

```text
3.3V -- 10k --+-- 10k -- GND
              |
              +-- buffer --> VBIAS ≈ 1.65V
```

VBIAS 必须由运放缓冲，并配置充分去耦。

### 6.3 输入保护

面包板原型建议：

- 4.7kΩ-10kΩ 串联限流；
- 低电容 Schottky 钳位到 0V/3.3V；
- 100nF 局部去耦；
- 明确标注输入范围；
- 上电前用万用表确认输入电压。

产品 PCB 阶段再评估：

- TVS/ESD 保护；
- 保险丝或 PTC；
- 反接保护；
- 接口屏蔽与地规划。

---

## 7. 硬件采购清单

价格是 2026-08-28 的预算参考，购买前重新确认。

### 7.1 第一批：必须购买

| 器件 | 数量 | 建议来源 | 预算 | 作用 |
|---|---:|---|---:|---|
| MCP6004 PDIP 四路运放 | 2 | DigiKey/Mouser；[Microchip 产品页](https://www.microchip.com/en-us/product/mcp6004) | $2-6 | 缓冲、放大、VBIAS、有源滤波 |
| MCP6544 PDIP 四路比较器 | 1 | DigiKey/Mouser；[Microchip 比较器选型](https://www.microchip.com/en-us/parametric-search/365) | $1-3 | Schmitt Trigger、窗口阈值 |
| 1% 电阻包 | 1 | DigiKey/Micro Center | $8-15 | 增益、偏置、迟滞、滤波 |
| 电容包 | 1 | DigiKey/Micro Center | $8-15 | 去耦、滤波、时间常数 |
| 10kΩ 电位器 | 3 | [Adafruit #356](https://www.adafruit.com/product/356) | $3.75 | 输入、偏置和阈值调节 |
| 1N4148 二极管 | 10 | DigiKey/Mouser | $1-2 | 钳位和电路实验 |
| Schottky 钳位二极管 | 5-10 | DigiKey/Mouser | $1-3 | 低压输入保护 |
| 2N3904 NPN | 3 | DigiKey/Mouser | $1-2 | 晶体管开关与输出级 |
| 2N7000 MOSFET | 3 | DigiKey/Mouser | $1-3 | 低功耗开关/故障注入 |
| LED | 5-10 | 元件包 | $1-2 | 状态输出 |
| 全尺寸面包板 | 1 | [Adafruit #239](https://www.adafruit.com/product/239) | $5.95 | 原型 |
| 公对公跳线 | 1组 | [Adafruit #1957](https://www.adafruit.com/product/1957) | 约 $1.95 | 接线 |
| 测试钩/鳄鱼夹 | 1组 | Adafruit/Micro Center | $4-8 | 测量连接 |

如已有面包板、线材和通用元件，第一阶段通常约 $30-50；从零购买约 $50-75。

### 7.2 建议常用阻值

```text
100Ω, 330Ω, 1kΩ, 2.2kΩ, 4.7kΩ,
10kΩ, 22kΩ, 47kΩ, 100kΩ, 1MΩ
```

### 7.3 建议常用电容

```text
100pF, 1nF, 10nF, 100nF,
1uF, 10uF, 100uF
```

每个 IC 的电源引脚附近必须放置 100nF 去耦电容。面包板上也应把去耦电容放在尽可能靠近 IC 的位置。

### 7.4 第二批：功能扩展

| 器件 | 数量 | 来源 | 参考价格 | 作用 |
|---|---:|---|---:|---|
| ADS1115 16-bit ADC | 1 | [Adafruit #1085](https://www.adafruit.com/product/1085) | $14.95 | 四路单端/两路差分精密采集 |
| QT-to-header cable | 1 | [Adafruit #4209](https://www.adafruit.com/product/4209) | $0.95 | ADS1115 到 MSP430 I2C |
| AD9833 模块/器件 | 1 | [Analog Devices AD9833](https://www.analog.com/en/products/ad9833.html) | 视模块而定 | 自动正弦/三角/方波和扫频 |
| Perma-Proto | 1 | [Adafruit #1606](https://www.adafruit.com/product/1606) | 约 $10.95 | PCB 前的永久焊接版本 |

ADS1115 采用 3.3V 逻辑，默认地址 0x48，与 MSP430 Health Controller 中可能使用的 INA219 默认地址 0x40 不冲突。

### 7.5 第三批：产品化

- 定制 PCB；
- 螺丝端子；
- 2.54mm 排针/排母；
- 测试点；
- DIP 开关或跳线；
- USB/电源保护；
- 外壳和面板；
- 备用 PCB 和 IC；
- 焊接工具或学校实验室焊接设备。

PCB、元件和外壳额外预算约 $40-80，取决于运输和返板次数。

---

## 8. 测试仪器策略

### 8.1 最低要求

数字万用表是必须的，用于：

- 上电前连续性检查；
- 3.3V/5V 确认；
- VBIAS 测量；
- 电阻值和电位器检查；
- 输入输出 DC 测量。

可选低成本型号：[Adafruit Pocket Autoranging Multimeter #850](https://www.adafruit.com/product/850)，约 $24.95。

### 8.2 OSU 实验室仪器

如果获得允许，最终验证优先使用学校实验室的：

- 双通道示波器；
- 函数发生器；
- 限流直流电源；
- 数字万用表。

不得默认拥有个人项目使用权限；开发前确认实验室规定、开放时间和监督要求。

### 8.3 低成本家庭方案

[EspoTek Labrador](https://espotek.com/labrador/product/espotek-labrador-board/) 约 $29，集成低成本示波器、波形发生器、简单电源、逻辑分析仪和万用表。

限制：

- 示波器约 750kS/s；
- 官方近似带宽约 100kHz；
- 电源输出功率有限且纹波较高；
- 不用于精密电源或高频测量；
- 购买前确认 Windows 11/当前操作系统兼容性。

用途：低频传感器、滤波器、Schmitt Trigger、信号调理的调试和初步自动扫频。

### 8.4 高级工具（非必需）

[Digilent Analog Discovery 3](https://digilent.com/shop/analog-discovery-3/) 零售价约 $379，包含 125MS/s 示波器、波形发生器、逻辑分析仪和可调电源。除非计划长期进行大量 ECE 项目，否则不应作为第一阶段采购。

---

## 9. 模拟通道架构

### 9.1 单通道 V1

```text
INPUT 0-3.3V
   |
   v
Protection: series resistor + clamp
   |
   v
MCP6004 Buffer
   |
   +----> Schmitt Trigger ----> DIGITAL_OUT
   |
   v
Non-Inverting Gain Stage: x1/x2/x5/x10
   |
   v
Selectable Low-Pass Filter
   |
   +----> MSP430 ADC A10
   |
   +----> ADS1115 AIN0 (V2)
   |
   +----> ANALOG_OUT test point
```

### 9.2 增益档位

非反相放大器：

```text
Gain = 1 + Rf/Rg
```

建议目标档位：x1、x2、x5、x10。具体 1% 电阻组合必须通过计算、LTspice 和实测确认。

第一版使用跳线切换反馈电阻，不立即使用数字电位器或模拟开关，以降低调试复杂度。

### 9.3 滤波档位

第一版使用一阶 RC 低通：

```text
fc = 1 / (2*pi*R*C)
```

目标档位：

- 约 10Hz：慢速温度/环境传感器；
- 约 100Hz：一般低速传感器；
- 约 1kHz：快速控制信号。

第二版再实现二阶 Sallen-Key 滤波器。二阶电路的 Q、元件比例和运放带宽必须通过正式计算与 LTspice 验证，不得只使用两个相同 RC 级联并直接声称是 Butterworth 响应。

### 9.4 Schmitt Trigger

使用 MCP6544 比较器，通过正反馈形成迟滞。

要求：

- 上阈值和下阈值可计算；
- Python 工具通过缓慢上升/下降输入测量实际阈值；
- 实测与理论值比较；
- 比较器数字输出保持在 3.3V 逻辑域；
- LED 必须有独立限流电阻，不能影响逻辑阈值。

### 9.5 双通道 V2

- Channel A：低速直流传感器，支持增益和低通；
- Channel B：交流耦合、1.65V 偏置，支持波形/振动/音频低频实验；
- 两通道共用参考电压但保留独立输入保护；
- 布局时模拟输入与数字开关信号分离。

---

## 10. 控制器无关集成与MSP430兼容profile

AFE产品不依赖MSP430。本节的MSP430FR6989分配是一个必须维护的外部兼容profile；参考验证控制器、RP2040或未来定制USB控制器分别使用自己的pin map和固件adapter。

### 10.1 接口计划

| 功能 | 建议引脚 | 说明 |
|---|---|---|
| ADC 输入 | J1.2 / P9.2 / A10 | 读取调理后的 0-3.3V 信号 |
| 比较器数字输出 | 可用 GPIO，例如 P1.5 | 支持边沿中断和事件计数 |
| I2C SDA | J1.10 / P4.0 | ADS1115 SDA |
| I2C SCL | J1.9 / P4.1 | ADS1115 SCL |
| SPI | 按官方 BoosterPack pinout 分配 | 可选 AD9833；实现前确认与其他外设冲突 |
| PWM 刺激信号 | 可用 Timer_B PWM 引脚 | 方波、阶跃和 RC-DAC 实验 |
| PC 通信 | 板载 Backchannel UART | Python Dashboard |

引脚必须集中定义在 `board_pins.h`，并与 MSP430 Equipment Health Controller 的引脚映射进行冲突检查。

### 10.2 ADC 采样

第一阶段使用 MSP430 ADC12：

- 定时器触发或固定周期采样；
- 8/16/32 点平均；
- 保存原始 ADC code 和换算 mV；
- 检测接近 0 和满量程的饱和；
- 不在 ISR 中执行浮点计算。

第二阶段加入 ADS1115，用于：

- 更高分辨率的低速测量；
- 差分输入；
- 与 MSP430 ADC12 交叉验证；
- 校准测试。

ADS1115 最高 860SPS，因此不称其为示波器。

### 10.3 测试信号

优先顺序：

1. 手动电位器 DC sweep；
2. MSP430 PWM 方波；
3. PWM + RC 形成近似 DAC/阶跃；
4. OSU 函数发生器或 Labrador；
5. AD9833 自动正弦扫频。

---

## 11. 固件架构

### 11.1 技术原则

- C；
- TI Code Composer Studio；
- 裸机、事件驱动；
- 不使用动态内存；
- 所有外设调用有超时；
- 采样、控制和 UART 发送解耦；
- 使用固定点整数表示 mV、mHz、毫增益和阈值；
- 电路参数和校准系数由配置结构管理。

### 11.2 目录结构

```text
firmware/
├── app/
│   ├── main.c
│   ├── app_state.c/.h
│   └── measurement_scheduler.c/.h
├── board/
│   ├── board_init.c/.h
│   └── board_pins.h
├── drivers/
│   ├── adc12.c/.h
│   ├── ads1115.c/.h
│   ├── comparator_input.c/.h
│   ├── pwm_stimulus.c/.h
│   ├── ad9833.c/.h
│   └── uart_transport.c/.h
├── afe/
│   ├── afe.c/.h
│   ├── afe_config.c/.h
│   ├── calibration.c/.h
│   ├── dc_sweep.c/.h
│   ├── frequency_sweep.c/.h
│   └── fault_detection.c/.h
├── protocol/
│   ├── protocol.c/.h
│   └── crc16.c/.h
└── tests/
```

### 11.3 公共 AFE API

```c
typedef struct {
    int16_t input_mv;
    int16_t output_mv;
    uint16_t gain_milli;
    uint16_t noise_mv;
    uint16_t frequency_hz;
    uint8_t threshold_state;
    uint16_t fault_flags;
} afe_status_t;

bool afe_init(void);
bool afe_set_gain(uint8_t channel, uint8_t gain_id);
bool afe_set_filter(uint8_t channel, uint8_t filter_id);
bool afe_read_status(uint8_t channel, afe_status_t *status);
bool afe_run_dc_sweep(uint8_t channel);
bool afe_run_hysteresis_test(uint8_t channel);
bool afe_run_self_test(void);
```

V1 的增益和滤波可能由硬件跳线设置，因此 `set` 函数可以返回“不支持自动配置”，但协议和 API 仍保留，以支持后续 PCB。

---

## 12. 通信协议

### 12.1 UART

- 115200 baud；
- 8N1；
- ASCII CSV；
- 每行最多 128 bytes；
- CRC-16/CCITT-FALSE；
- 与 MSP430 Health Controller 保持同一 CRC 和基本传输层，但使用 `AFE` 消息命名空间。

### 12.2 遥测

```text
AFE,TEL,<seq>,<time_ms>,<channel>,<input_mv>,<output_mv>,<gain_milli>,<threshold>,<fault_hex>,<crc16>\n
```

示例：

```text
AFE,TEL,120,45120,0,500,2487,4974,1,0000,A31C
```

### 12.3 命令

```text
AFE,CMD,<seq>,GET,STATUS,<channel>,<crc16>
AFE,CMD,<seq>,SET,GAIN,<channel>,<gain_id>,<crc16>
AFE,CMD,<seq>,SET,FILTER,<channel>,<filter_id>,<crc16>
AFE,CMD,<seq>,RUN,DC_SWEEP,<channel>,<crc16>
AFE,CMD,<seq>,RUN,HYSTERESIS,<channel>,<crc16>
AFE,CMD,<seq>,RUN,FREQUENCY_SWEEP,<channel>,<crc16>
AFE,CMD,<seq>,SAVE,CALIBRATION,<crc16>
```

---

## 13. Python 工具

### 13.1 功能

- 串口选择和自动重连；
- 实时输入/输出曲线；
- 当前增益、滤波、阈值状态；
- DC sweep；
- hysteresis sweep；
- frequency sweep；
- 理论值与实测值对比；
- 校准系数计算；
- CSV 导出；
- 测试结果 PASS/FAIL；
- Simulation Mode。

### 13.2 目录

```text
dashboard/
├── app.py
├── serial_worker.py
├── protocol.py
├── models.py
├── measurements/
│   ├── dc_sweep.py
│   ├── hysteresis.py
│   ├── frequency_response.py
│   └── calibration.py
├── reporting/
│   ├── csv_export.py
│   └── summary.py
└── tests/
```

### 13.3 自动分析

DC sweep：

- 对有效线性区做最小二乘拟合；
- 计算增益、偏置、R-squared；
- 自动排除饱和区；
- 标记异常点但保留原始数据。

Hysteresis：

- 分别分析上升和下降方向；
- 计算 `Vth_high`、`Vth_low` 和宽度；
- 记录重复测量的标准差。

Frequency response：

- 计算每个频率下 `Vout/Vin`；
- 转换为 dB；
- 估计 -3dB 截止频率；
- 不在输入或输出饱和时计算有效增益。

---

## 14. 仓库结构

建议独立仓库名：

```text
mixed-signal-afe-validation-platform
```

结构：

```text
mixed-signal-afe-validation-platform/
├── README.md
├── LICENSE
├── ASSUMPTIONS.md
├── docs/
│   ├── DEVELOPMENT_SPEC.md
│   ├── architecture.md
│   ├── theory.md
│   ├── wiring.md
│   ├── protocol.md
│   ├── calibration.md
│   ├── test-plan.md
│   └── risk-register.md
├── simulation/
│   ├── ltspice/
│   └── expected-results/
├── hardware/
│   ├── breadboard/
│   ├── schematics/
│   ├── kicad/
│   ├── bom/
│   └── datasheets/
├── firmware/
├── dashboard/
├── tools/
│   ├── telemetry_simulator.py
│   └── synthetic_sweep_generator.py
├── tests/
├── test-data/
├── reports/
└── media/
```

---

## 15. 分阶段开发计划

### Phase 0：架构、仿真和软件骨架（1-2天）

- 创建仓库；
- 放入本文档；
- 建立 assumptions 和 risk register；
- 建立 Python telemetry simulator；
- 定义 UART/CRC；
- 使用 LTspice 仿真缓冲器、增益级、RC 滤波和 Schmitt Trigger；
- 生成理论结果表。

验收：不需要硬件，Python 测试可运行，仿真电路具有预期行为。

### Phase 1：输入、缓冲和增益（2-4天）

- 面包板电源和去耦；
- VBIAS；
- 输入保护；
- MCP6004 buffer；
- x1/x2/x5/x10；
- 电位器 DC sweep；
- 万用表验证。

验收：记录各增益档的理论与实测输入输出表。

### Phase 2：滤波和 Schmitt Trigger（3-5天）

- 两个以上低通档位；
- 比较器迟滞；
- GPIO 中断；
- 手动上升/下降输入；
- OSU/Labrador 波形验证。

验收：得到截止频率和上下阈值的实测结果。

### Phase 3：控制器无关自动采集（3-5天）

- 参考验证控制器ADC；
- DAC或PWM stimulus；
- UART；
- DC sweep engine；
- 饱和检测；
- Python 实时曲线。
- 独立MSP430兼容profile，不与产品核心固件混合；

验收：自动完成多点输入/输出记录并导出 CSV。

### Phase 4：精密 ADC 和校准（3-5天）

- ADS1115；
- MSP430 ADC 与 ADS1115 对照；
- 增益和偏置校准；
- 校准系数保存；
- 重复性分析。

验收：校准前后误差均有真实数据对比。

### Phase 5：自动扫频和故障注入（4-7天）

- 函数发生器/Labrador/AD9833；
- 自动频率响应；
- 开路、短路、饱和、噪声和元件变化；
- PASS/FAIL；
- 报告生成。

验收：形成完整验证报告和至少 50 个初步测试记录。

### Phase 6：PCB 和成品（1-3周）

- KiCad schematic；
- ERC；
- PCB layout；
- DRC；
- 测试点、丝印和接口；
- BOM；
- 生产和焊接；
- bring-up；
- 与面包板结果比较。

完整作品集版本预计 5-8 周；全力开发且器件到货顺利，可在 2-3 周完成可展示的面包板版本。

---

## 16. 目标指标

以下是工程目标，不是已经实现的成果。

### V1 目标

- DC 增益误差：不超过 5%；
- 截止频率误差：不超过 15%；
- 重复迟滞阈值标准差：不超过满量程的 2%；
- 0-3.3V 输入下无持续振荡；
- UART 连续采集 30 分钟无固件崩溃；
- 输入超范围能够被软件标记。

### V2 目标

- 校准后 DC 增益误差：不超过 2%；
- 自动识别输出饱和区；
- 至少 3 种增益和 2 种滤波配置自动测试；
- 至少 50 条功能/故障测试；
- 至少 2 小时连续采集；
- PCB 与面包板主要测量差异有记录和解释。

目标是否可行必须由实际元件精度、仪器能力和测试结果决定。

---

## 17. 测试计划

### 17.1 电源与安全

- 上电前电源与地短路检查；
- 3.3V 和 VBIAS；
- IC 静态电流；
- 反接保护；
- 输入 0V、1.65V、3.3V；
- 任何节点不得超过器件绝对最大额定值。

### 17.2 放大器

- 每个增益档至少 10 个 DC 输入点；
- 输出线性拟合；
- 饱和起点；
- 输入偏置；
- 负载变化；
- 示波器观察是否振荡；
- 电源去耦移除/恢复对稳定性的影响只在安全条件下测试。

### 17.3 滤波器

- 至少 10 个对数分布频率点；
- 输入幅值保持在线性区；
- 测量 Vin 和 Vout；
- 幅度比与 dB；
- -3dB 截止频率；
- 与 LTspice 比较；
- 记录仪器带宽限制。

### 17.4 Schmitt Trigger

- 输入缓慢上升；
- 记录 high threshold；
- 输入缓慢下降；
- 记录 low threshold；
- 重复 20 次；
- 计算平均值、标准差和迟滞宽度；
- 检查输出电平与 MSP430 GPIO 兼容性。

### 17.5 故障注入

- 输入开路；
- 输入短路到 GND；
- 输入固定到 3.3V；
- 运放输出饱和；
- ADC 通信断开；
- I2C 超时；
- 比较器输出不变化；
- 电阻/电容切换到错误值；
- 人工叠加噪声或不稳定输入。

---

## 18. 完成定义

- [ ] 仓库可从干净环境运行软件测试；
- [ ] LTspice 文件和理论计算可重复；
- [ ] 原理图与实际接线一致；
- [ ] MCP6004 缓冲/增益稳定；
- [ ] 至少两个滤波档位验证；
- [ ] Schmitt Trigger 上下阈值完成重复测量；
- [ ] MSP430 ADC 和 UART 工作；
- [ ] Python 能完成 DC sweep 和结果导出；
- [ ] ADS1115 或其他参考测量与 MSP ADC 对照；
- [ ] 故障注入具有预期响应；
- [ ] 至少一组结果由实验室仪器复核；
- [ ] 所有简历数字来自真实测试；
- [ ] README 包含限制、照片、接线、构建和结果；
- [ ] 与 MSP430 Health Controller 的接口已文档化；
- [ ] 与 Lab Bench Monitor 的团队成果完全分离。

---

## 19. 风险登记

| 风险 | 影响 | 缓解 |
|---|---|---|
| 输入超过 3.3V | 损坏 MCU/ADC | 串联限流、钳位、万用表检查 |
| 运放输入/输出未覆盖电源轨 | 数据削波 | 查阅 common-mode 和 output swing，保留裕量 |
| 面包板寄生参数 | 高频响应和稳定性失真 | 降低初始频率，短接线，去耦，PCB 复核 |
| USB 仪器接地 | 地环路/误连接 | 只测低压公共地系统，先确认地参考 |
| Labrador 带宽/电源限制 | 测量不准确 | 仅用于初步调试，关键数据用实验室仪器复核 |
| ADS1115 采样率低 | 无法捕获快速波形 | 定位为低速精密 ADC，不称为示波器 |
| MCP6004 只有约 1MHz GBW | 高增益高频失真 | 限制频率范围并记录 gain-bandwidth tradeoff |
| 自动扫频输入饱和 | 得到虚假频响 | 每点检查 Vin/Vout 峰值和饱和标志 |
| 两个项目代码耦合 | 无法独立展示 | 独立仓库，接口协议共享，禁止复制业务逻辑 |

---

## 20. Codex 开发规则

1. 第一次任务只完成 Phase 0，不一次生成全部硬件代码。
2. 硬件未连接时使用 simulation、synthetic data 和 host tests。
3. 所有电路值必须说明公式、数据表依据或仿真依据。
4. 不把 SPICE 结果描述成实测结果。
5. 不把 USB 低成本仪器结果包装成实验室级精度。
6. 所有引脚集中定义，避免与另一个 MSP430 项目冲突。
7. 固件不使用动态内存。
8. Python parser 必须能处理坏帧、缺字段和超长输入。
9. 每个开发阶段更新 `ASSUMPTIONS.md` 和 `test-plan.md`。
10. 每次硬件反馈都记录器件型号、供电、接线、仪器和测量条件。
11. 不执行或建议任何市电实验。
12. 不将 Lab Bench Monitor 的小组内容复制进本项目。

---

## 21. 可直接交给新 Codex 的首条任务

```text
请根据 docs/DEVELOPMENT_SPEC.md，从零创建 Configurable Analog Front-End & Validation Platform 项目。

本轮只完成 Phase 0，不声称任何硬件已经验证：
1. 检查工作区状态，不覆盖已有文件；
2. 创建文档指定的独立仓库目录结构；
3. 创建 ASSUMPTIONS.md，列出需要用户确认的 MSP430 工具链、现有元件、实验室仪器权限和实物接线；
4. 创建理论计算文档，覆盖非反相增益、一阶 RC 截止频率、Schmitt Trigger 上下阈值和 ADC 单位换算；
5. 创建 LTspice 仿真文件的组织位置和仿真任务清单；如果当前环境无法运行 LTspice，不得伪造仿真结果；
6. 定义 AFE UART CSV 协议和 CRC-16/CCITT-FALSE；
7. 创建 Python telemetry simulator、协议 parser 和 synthetic DC sweep generator；
8. 为 CRC、协议、线性拟合、饱和区排除和迟滞计算创建 pytest；
9. 创建最小 README，明确项目当前处于设计/仿真阶段；
10. 运行当前环境可执行的测试，报告真实结果、未验证假设和 Phase 1 所需的用户硬件反馈。

边界：这是独立个人项目；可以通过公开接口与 MSP430 Equipment Health Controller 集成；不得与 OSU Lab Bench Monitor Capstone 混合；不得在没有实物证据时声称完成硬件测量。
```

---

## 22. 完成后的简历方向

只有实际完成后才能使用以下结构，方括号必须替换为真实结果：

```text
Configurable Analog Front-End & Validation Platform | MSP430FR6989, C, Python, KiCad, ADC, I2C

• Designed a reusable low-voltage analog front end integrating input protection, switchable-gain amplification, selectable filtering, hysteresis-based threshold detection, and precision signal acquisition.
• Developed MSP430 firmware and Python validation tools to automate DC sweeps, threshold characterization, calibration, fault injection, telemetry, and test-data export.
• Validated gain, cutoff frequency, hysteresis, saturation, and fault behavior through [真实数量] automated and bench tests, achieving [真实结果] after calibration across [真实范围].
```

本项目在 LinkedIn 上应标记为 Independent Project。未完成实物前使用 `In Development`，不提前填写预期性能为既成成果。
