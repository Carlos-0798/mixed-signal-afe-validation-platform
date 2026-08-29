# 第二块控制板选型

核对日期：2026-08-29

## 1. 先定义角色

第二块板不必复制 MSP-EXP430FR6989。更有价值的架构是：

```text
PC / Python orchestrator
        |
        +---- USB/UART ---- MSP430FR6989：外部兼容性示例之一
        |
        +---- USB/UART ---- 验证控制器：刺激、采样、计时、故障注入
                               |
                               +---- 0-3.3 V AFE
                               +---- ADS1115
```

这样两个项目不会混成一个项目：AFE Validation Platform本身是产品，MSP430只是使用公开接口的外部兼容对象之一，验证控制器只是可替换测试设备。Python通过统一adapter管理不同控制器；没有OSU仪器时也能完成低速自动化，有仪器时再把示波器/函数发生器作为另一种后端接入。

## 2. 强制条件

- 原生 3.3 V GPIO/ADC，不能用 5 V GPIO 直接连接AFE；
- 有预焊排针或标准插座，当前无焊台也能使用；
- USB编程和串口通信；
- 至少有ADC、PWM、I2C和UART；有DAC和板载调试器优先；
- 官方文档、工具链和长期可获得性明确；
- 板卡自己的ADC/DAC只能算嵌入式测量资源，不能冒充实验室校准仪器。

## 3. 候选比较

| 候选 | 当前参考价 | 优点 | 局限 | 定位 |
|---|---:|---|---|---|
| **STM32 NUCLEO-G474RE** | DigiKey约 $20.13，当前有库存 | 板载STLINK-V3E、Virtual COM、Micro-USB；STM32G4有丰富ADC/DAC/运放/比较器/定时器资源；Arduino和Morpho插座免焊 | 新增STM32CubeIDE/CubeMX工具链；功能多，初学阶段配置复杂；不是校准仪器 | **首选验证控制器** |
| **TI LP-MSPM0G3507** | DigiKey参考约 $23.36 | 80 MHz Cortex-M0+、双12-bit 4 MSPS ADC、DAC、比较器、运放；板载调试器；可以继续使用TI/CCS生态 | 当前TI/DigiKey即时库存不稳定；为了等板可能拖延项目 | 同生态首选，恢复稳定库存时重新比较 |
| **Adafruit Metro RP2040** | Adafruit约 $14.95 | 3.3 V、预装插座、USB-C、STEMMA QT、CircuitPython非常适合初学者；12-bit ADC和PWM | 无真正DAC、无板载调试器；RP2040 ADC约8.7 ENOB，不适合作参考仪器；需USB-A-to-C线 | 首选易学软件控制器 |
| **Raspberry Pi Pico H / 预焊排针RP2040** | Adafruit约 $5 | 极低成本、Micro-USB、MicroPython/C、ADC/PWM/I2C/UART | 无QT、无板载调试器、接线标签较密、ADC同样不精密 | 最低成本协议/故障注入器 |
| 第二块 MSP-EXP430FR6989 | 约 $29.72，购买页可能有附加费 | 固件和工具链完全一致、学习负担最低 | 只是复制现有能力；没有独立DAC；对验证平台的能力提升较小 | 只有需要两个完全相同MSP430目标时选择 |

## 4. 明确排除

- **Arduino UNO R4 Minima**：官方说明为5 V only，直接连接3.3 V AFE会引入电平风险；不因其带DAC而选择。
- **普通ESP32开发板**：适合无线遥测，但ADC、射频噪声和不同板卡电源设计会增加模拟排错变量；当前项目不需要Wi-Fi。
- **无预焊排针的小板**：当前无焊接设备，不应为省几美元提前引入机械接触风险。
- **RP2350/Pico 2作为首选**：性能更强，但当前并不需要；Adafruit当前文档还提示部分A2 stepping受E9 erratum影响。成熟RP2040已经足够承担简单软件控制器。

## 5. 推荐决定

当前推荐购买 **NUCLEO-G474RE**，把它定义为可替换的参考验证控制器，而不是AFE产品的主控身份：

- AFE模拟核心在没有任何MCU时仍可独立运行；
- MSP430FR6989只验证一个公开兼容接口profile；
- NUCLEO生成DAC/PWM低速刺激并读取ADC；
- NUCLEO的定时器捕获Schmitt输出边沿；
- ADS1115继续作为低速独立对照；
- Python统一控制、记录来源标签和生成报告。

这会增加一套STM32工具链，但换来真正的跨平台device adapter和更强的自动化验证故事。实施时先只使用GPIO、UART、ADC、DAC和一个定时器，不一次学习全部STM32外设。选择NUCLEO不会改变AFE作为独立产品的身份，详见`PRODUCT_ARCHITECTURE.md`。

## 6. 预算影响

```text
AFE NOW核心件                 $86.63
NUCLEO-G474RE                 $20.13
小计                         $106.76
AFE $200预算剩余              $93.24
```

NUCLEO-G474RE使用USB Micro-B连接STLINK-V3E。现有MSP430随附的USB-A to Micro-B线可轮换使用；若要两板同时连接电脑，再预算约$3-6购买第二根数据线。即使增加一根线，仍有约$87-90留给税运和后期仪器。

## 7. 不能被开发板替代的验证

NUCLEO的ADC/DAC可以做自动低速扫描和相对比较，但不能证明自己的绝对精度，也不能可靠发现所有模拟振荡。以下结论仍需OSU仪器、未来合适的个人仪器，或明确标为未验证：

- 精确幅频和相频响应；
- 高频噪声与振荡；
- 快速建立时间和比较器传播延迟；
- 校准级绝对准确度。

## 8. 最终确认点

在把板卡从CSV的`CONFIRM`改为`NOW`前，只需确认是否接受安装和学习STM32CubeIDE。若不希望增加第二套嵌入式工具链，则选择Metro RP2040走CircuitPython易学路线，或等待LP-MSPM0G3507恢复稳定库存继续使用CCS。

## 9. 官方与采购页面

- ST NUCLEO-G474RE系列页面：https://www.st.com/en/evaluation-tools/stm32-mcu-mpu-eval-tools/products.html
- DigiKey NUCLEO-G474RE：https://www.digikey.com/en/products/detail/stmicroelectronics/NUCLEO-G474RE/10231585
- TI LP-MSPM0G3507：https://www.ti.com/tool/LP-MSPM0G3507
- DigiKey LP-MSPM0G3507：https://www.digikey.com/en/products/detail/texas-instruments/LP-MSPM0G3507/20512419
- Adafruit Metro RP2040：https://www.adafruit.com/product/5786
- Raspberry Pi Pico系列官方文档：https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html
- Adafruit预焊排针Pico：https://www.adafruit.com/pico

价格和库存只代表2026-08-29核对结果；实际下单时重新确认。
