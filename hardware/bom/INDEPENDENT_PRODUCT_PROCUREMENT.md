# 独立产品采购清单（当前冻结版）

核对日期：2026-08-29  
预算边界：AFE 新项目单独 **USD 200**；Klein MM420 和另一个项目的 Adafruit 购物车均不占用这 USD 200。  
项目状态：设计/仿真阶段。以下器件尚未被实物验证；参考价不含税、运费和可能的关税，库存与结账价以下单当天为准。

## 0. 推荐下单方式与直接链接

当前推荐只建立 **Adafruit + Mouser 两个订单**。Adafruit负责模块、电源、面包板、线材和人机操作件；Mouser负责关键IC、精密无源件和保护器件。这样既利用现有Adafruit购物车节省运费，也避免为MCP6544再单独支付第三家授权渠道运费。

### Adafruit订单（A+B建议现在购买）

| 产品 | 数量 | 参考价 | 购买链接 | 备注 |
|---|---:|---:|---|---|
| 10 kOhm面包板微调电位器 #356 | 4 | $5.00 | [Adafruit #356](https://www.adafruit.com/product/356) | 当前有货、0.1 inch间距；最终外壳的面板旋钮以后单独决定 |
| 5色漫射LED包 #4203 | 1 | $4.95 | [Adafruit #4203](https://www.adafruit.com/product/4203) | 25只；使用红/绿时仍须串联限流电阻 |
| 0.1 inch可折断排针 #392 | 1 | $4.95 | [Adafruit #392](https://www.adafruit.com/product/392) | 以后焊接配置接口；面包板初期不必焊 |
| 5 V 2 A UL-listed电源 #276 | 1 | $7.95 | [Adafruit #276](https://www.adafruit.com/product/276) | AFE专属输入电源 |
| 2.1 mm面包板桶形插座 #373 | 1 | $0.95 | [Adafruit #373](https://www.adafruit.com/product/373) | 第一次使用前确认正负极和switched pin |
| 全尺寸面包板 #239 | 1 | $5.95 | [Adafruit #239](https://www.adafruit.com/product/239) | AFE专属，不拆另一项目电路 |
| 公对公跳线 #1957 | 1 | $1.95 | [Adafruit #1957](https://www.adafruit.com/product/1957) | AFE专属基本接线 |
| ADS1115 16-bit ADC #1085 | 1 | $14.95 | [Adafruit #1085](https://www.adafruit.com/product/1085) | 自动验证附件，不是模拟本体运行前提 |
| QT-to-male-header #4209 | 1 | $0.95 | [Adafruit #4209](https://www.adafruit.com/product/4209) | ADS1115专用，不占用INA219的线 |

Adafruit A+B 规划小计约 **$47.40**。若稍后确认NUCLEO，再加一根[USB-A to Micro-B数据线 #592](https://www.adafruit.com/product/592)，参考$2.95。

### Mouser订单（A+B建议现在购买）

| 器件 | 数量 | 购买链接 | 链接性质/检查事项 |
|---|---:|---|---|
| MCP6004-I/P | 3 | [Mouser直接产品页](https://www.mouser.com/ProductDetail/Microchip-Technology/MCP6004-I-P) | 必须是PDIP-14的`I/P`版本 |
| MCP6544-I/P | 2 | [Mouser直接产品页](https://www.mouser.com/ProductDetail/Microchip-Technology/MCP6544-I-P) | 必须是PDIP-14、push-pull；这是选择Mouser为主元件单的关键原因 |
| 14-pin DIP socket | 5 | [3M 4814-3004-CP](https://www.mouser.com/ProductDetail/3M-Electronic-Solutions-Division/4814-3004-CP) | 14位置、0.3 inch、通孔；不要误买16-pin |
| 4-position DIP switch | 3 | [DS01C-254-S-04BE搜索页](https://www.mouser.com/c/?q=DS01C-254-S-04BE) | 2.54 mm通孔；下单前确认现货 |
| 1%金属膜电阻 | 13值×10 | [Yageo MFR 1%通孔筛选页](https://www.mouser.com/c/passive-components/resistors/through-hole-resistors/?m=YAGEO&series=MFR&tolerance=1%20%25) | 按本页下方13个值逐一加入，不买5%替代品 |
| BAT41-TAP | 10 | [Mouser直接产品页](https://www.mouser.com/ProductDetail/Vishay-Semiconductors/BAT41-TAP) | DO-35信号钳位候选 |
| 1N4148-TAP | 20 | [Mouser搜索页](https://www.mouser.com/c/?q=1N4148-TAP) | 选择active、through-hole |
| 100 nF去耦电容 | 20 | [Mouser径向陶瓷筛选页](https://www.mouser.com/c/passive-components/capacitors/ceramic-capacitors/?capacitance=0.1%20uF&termination%20style=Radial&tolerance=10%20%25) | 去耦用10%可接受；不要把宽公差件用于精密滤波 |
| 10 nF/100 nF/1 uF精密滤波电容 | 各5 | [Mouser通孔薄膜5%筛选页](https://www.mouser.com/c/passive-components/capacitors/film-capacitors/?mounting%20style=Through%20Hole&tolerance=5%20%25) | 三个值逐一选择5%或更好 |
| 10 uF/100 uF电解电容 | 10/5 | [Mouser通孔电解筛选页](https://www.mouser.com/c/passive-components/capacitors/aluminum-electrolytic-capacitors/?mounting%20style=Through%20Hole) | 额定电压>=10 V，注意极性 |
| MCP1702-3302E/TO | 3 | [Mouser直接产品页](https://www.mouser.com/ProductDetail/Microchip-Technology/MCP1702-3302E-TO) | 固定3.3 V、TO-92 |
| 1N5817/18/19反接保护 | 10 | [Mouser通孔1N5817搜索页](https://www.mouser.com/c/?q=1N5817%20through%20hole) | 选择active且有现货的通孔型号 |
| MF-R025可恢复保险 | 5 | [Mouser直接产品页](https://www.mouser.com/ProductDetail/Bourns/MF-R025) | 250 mA hold / 500 mA trip |
| 2.54 mm短路帽 | 10 | [Mouser短路帽筛选页](https://www.mouser.com/c/connectors/headers-wire-housings/shunts-jumpers/) | 与0.1 inch排针匹配 |
| 2N3904通孔 | 10 | [Mouser搜索页](https://www.mouser.com/c/?q=2N3904%20through%20hole) | 选择active；记录厂家和引脚顺序 |
| 2N7000-G | 5 | [Mouser直接产品页](https://www.mouser.com/ProductDetail/Microchip-Technology/2N7000-G) | 仅用于低电流开关/故障注入 |

Mouser A+B 规划小计约 **$58.85**。部分链接是筛选页而不是单一料号页，因为精密电阻/电容必须分别选择多个值；进入页面后仍要核对`Active`、`Through Hole`、公差、最小购买量和美国结账页关税提示。

### 控制器确认后再加入

- [NUCLEO-G474RE — Mouser](https://www.mouser.com/ProductDetail/STMicroelectronics/NUCLEO-G474RE)，规划$20.13；必须先接受STM32Cube工具链。
- [USB-A to Micro-B数据线 #592 — Adafruit](https://www.adafruit.com/product/592)，规划$2.95；电脑端适配现有USB-A。

每行链接、状态和公式预算也已整理到 `independent-product-purchase.xlsx`。Excel中的`DIRECT`表示直接型号页；`SEARCH/FILTER`表示仍要按该行规格选值，不能无检查地购买搜索结果第一项。

## 1. 这次清单如何体现“独立产品”

采购按三层划分：

1. **A — AFE Base Unit（产品本体）**：没有 MSP430、没有其他 MCU、没有电脑时，也能用 DIP 开关/电位器手动完成保护、缓冲、增益、滤波和 Schmitt Trigger 配置。
2. **B — Automation Add-on（自动验证附件）**：ADS1115、故障注入晶体管等用于采集和自动测试；拔掉后不影响 AFE 的模拟功能。
3. **C — Replaceable Reference Controller（可替换参考控制器）**：NUCLEO-G474RE 只是目前推荐的自动化控制器，不是产品身份。以后可以换成 MSP430、RP2040、定制 USB 板或实验室仪器，而不用重做 AFE。

工具可以在项目间共享，但 AFE 自己至少拥有一块面包板、一套公对公跳线和一套独立 3.3 V 供电链，避免另一项目暂停或长期占用接线时本项目也停工。

## 2. A — 独立 AFE 产品本体：建议现在购买

| 类别 | 精确型号/规格 | 数量 | 参考渠道 | 预算价 | 为什么需要 |
|---|---|---:|---|---:|---|
| 四运放 | MCP6004-I/P，PDIP-14 | 3 | DigiKey / Mouser | $1.77 | 两只工作、一只备用；用于缓冲、非反相增益和有源处理 |
| 四比较器 | MCP6544-I/P，PDIP-14，push-pull | 2 | Mouser / DigiKey | $2.86 | 一只工作、一只备用；用于 Schmitt Trigger，不能误买成不同输出结构 |
| IC 插座 | 3M 4814-3004-CP，14-pin、0.3 inch | 5 | Mouser | $3.20 | 新手插错或更换 IC 时保护引脚 |
| 手动调节 | Adafruit #356，10 kOhm breadboard trim potentiometer | 4 | Adafruit | $5.00 | 手动设阈值/偏置；当前有货，适合Phase 1面包板 |
| 手动配置 | DS01C-254-S-04BE，4-position THT DIP switch | 3 | DigiKey | $2.22 | 脱离 MCU 选择增益/滤波档；仅切换小信号，不用于切断整条电源 |
| 精密电阻 | 1% metal-film THT，见下方阻值表 | 每值 10 | DigiKey / Mouser | $14.00 | 决定增益、滤波和阈值；关键阻值不能只靠 5% 套件 |
| 输入保护 | BAT41-TAP，DO-35 | 10 | DigiKey | $3.20 | 低电容 Schottky 保护候选；最终钳位效果仍需实测 |
| 通用二极管 | 1N4148，THT | 20 | DigiKey / Mouser | $1.10 | 开关、隔离和实验备用 |
| 去耦 | 100 nF X7R，THT | 20 | DigiKey / Mouser | $3.00 | 每个 IC 电源脚附近放置，吸收快速电流变化 |
| 精密滤波电容 | 10 nF、100 nF、1 uF，5% 或更好 | 每值 5 | DigiKey / Mouser | $10.00 | 形成可复现的一阶 RC 档位 |
| 电源缓冲 | 10 uF x10、100 uF x5，额定 >=10 V | 1 组 | DigiKey / Mouser | $5.00 | 稳压器与电源入口缓冲；电解电容有极性 |
| 状态指示 | Adafruit #4203，5色漫射LED 25-pack | 1 | Adafruit | $4.95 | 使用红/绿显示状态；必须串联330 Ohm或1 kOhm限流 |
| 配置连接 | Adafruit #392排针 + 2.54 mm shunts x10 | 1 组 | Adafruit + Mouser | $5.95 | 为后续可插拔配置和永久板预留；面包板阶段可先用DIP开关 |
| 3.3 V 稳压 | MCP1702-3302E/TO，TO-92 | 3 | DigiKey | $1.95 | 把独立 5 V 输入降到 3.3 V；两只备用防止接反损坏 |
| 反接保护 | 1N5817/1N5818/1N5819，active THT Schottky | 5–10 | DigiKey / Mouser | $1.90 | 防止直流输入极性接反；下单时按现货选在产等效型号 |
| 可恢复保险 | Bourns MF-R025，250 mA hold / 500 mA trip，THT | 5 | DigiKey | $2.95 | 错接/短路时增加一层保护；它不是精密限流器，也不会瞬间动作 |
| 独立 5 V 电源 | Adafruit #276，5 V 2 A，UL Listed | 1 | Adafruit / Newark | $7.95 | AFE 专用墙插电源；不能把其 5 V 直接送进 3.3 V 信号节点 |
| 面包板电源座 | Adafruit #373，2.1 mm barrel jack | 1 | Adafruit | $0.95 | 与 #276 配合；接线前确认中心正极、地和 switched pin |
| 专用面包板 | Adafruit #239 full-size breadboard | 1 | Adafruit | $5.95 | AFE 不依赖拆除另一个项目的电路 |
| 专用跳线 | Adafruit #1957 male/male jumpers | 1 套 | Adafruit | $1.95 | 面包板基本连接；颜色固定映射电源、地和信号 |

**A 层规划小计：$85.85。** 已删除不必要的通用电容套件，因为本单已经分别包含去耦、精密滤波和电源缓冲电容；这比买一盒公差未知且大量重复的套件更节省。

建议的 1% 电阻值：

```text
100, 330, 1k, 2.2k, 4.7k, 10k,
16.0k, 22k, 40.2k, 47k, 90.9k, 100k, 1M ohm
```

这些是“计划阻值”，不是测量值。到货后用 MM420 逐个测量关键电阻，并把实测值写入 as-built BOM，再重新计算实际增益、截止频率和 Schmitt 阈值。

## 3. B — 自动验证附件：建议与第一单一起买

| 器件 | 数量 | 参考渠道 | 预算价 | 角色 |
|---|---:|---|---:|---|
| Adafruit ADS1115 #1085 | 1 | Adafruit | $14.95 | 外置 16-bit ADC 采集候选；不替代 MM420 校核，也不属于模拟链运行的前提 |
| Adafruit QT-to-male-header #4209 | 1 | Adafruit | $0.95 | AFE 自己拥有 ADS1115 连接线，不占用另一项目的 INA219 线 |
| 2N3904 THT | 10 | DigiKey / Mouser | $1.50 | 低压开关和可控故障注入 |
| 2N7000 THT | 5 | DigiKey / Mouser | $3.00 | 低电流开关实验；不能驱动风扇等功率负载 |

**B 层小计：$20.40。A+B 建议现在下单合计：$106.25。**

## 4. C — 可替换参考验证控制器：确认工具链后购买

| 器件 | 数量 | 参考渠道 | 预算价 | 当前决定 |
|---|---:|---|---:|---|
| STM32 NUCLEO-G474RE | 1 | DigiKey / ST 授权渠道 | $20.13 | 推荐但未锁定；只有在接受 STM32Cube 开发工具链后才下单 |
| USB-A to Micro-B data cable，Adafruit #592 或等价 | 1 | Adafruit | $2.95 | 电脑已有 USB-A；必须是数据线，不是仅充电线 |

**C 层小计：$23.08。A+B+C 全部购买合计：$129.33。**

为什么不是第二块 MSP430：参考控制器需要方便产生测试刺激、采集 ADC、测量数字边沿并通过 USB 与 Python 通信。NUCLEO-G474RE 很适合做当前参考实现，但公开接口会保持 3.3 V、UART/I2C/SPI/GPIO 和模拟 I/O 中立；现有 MSP-EXP430FR6989 作为兼容性 profile 使用，而不是产品依赖。

## 5. 预算结论

| 付款阶段 | 项目内小计 | $200 内剩余 | 建议 |
|---|---:|---:|---|
| A+B：独立本体 + 自动验证附件 | **$106.25** | **$93.75** | 现在可以下单 |
| A+B+C：再加入参考控制器和 USB 数据线 | **$129.33** | **$70.67** | 工具链确认后购买 |

剩余 $70.67 不是“还应花掉的钱”。它用于税、两家渠道运费、价格波动、错件补购和 Phase 1 实测后真正暴露出的缺口。若结账后的总价逼近 $180，先暂停而不是为了“一次买全”继续加器件；至少保留约 $20 返工余量。

## 6. 与另一个项目购物车的关系

### 可以共享，但不决定 AFE 能否运行

- 22 AWG 固芯线套装、剥线钳、鳄鱼夹、热缩管：属于实验室工具/耗材，可以跨项目共享。
- 10 kOhm NTC：以后可作为真实模拟传感器样例，但不是 AFE 核心件。
- MM420：跨项目测量工具，费用已明确在 $200 之外。

### 不计作 AFE 已有库存

旧购物车尚未下单，因此本清单没有把旧购物车的面包板、QT 线、跳线或电源按 $0 处理。若两单合并结账，应在收货时把其中一套面包板、一套公对公跳线、一根 QT 线和一个 5 V 电源明确标记为 AFE 资产。

### 不需要为 AFE 重复购买

- DS18B20、INA219、5 V 风扇、Adafruit MOSFET Driver、JST PH 风扇线：属于另一个项目或数字/功率侧扩展，不是 AFE Base Unit 的必需件。
- Perma-Proto、焊台、焊锡：面包板架构通过前暂缓；过早焊死会增加返工成本。

## 7. 独立供电的第一次接线原则

```text
5 V UL-listed adapter
  -> 2.1 mm barrel jack
  -> MF-R025 resettable fuse
  -> reverse-polarity Schottky diode
  -> MCP1702-3.3 LDO + datasheet-required capacitors
  -> 3.3 V AFE rail
  -> 100 nF local decoupling at every IC
```

- MCP1702 是电源稳压器，不是精密电压基准；3.3 V 轨必须用 MM420 实测并记录。
- 首次通电先不插 MCP6004、MCP6544、ADS1115 或控制板，只测空载 3.3 V 和极性。
- 5 V 适配器可提供 2 A，并不表示 AFE 会吸收 2 A；MF-R025 与 MCP1702 的保护只是降低风险，不能代替检查接线。
- DIP 开关只切换电阻/电容等小信号配置，不把它当整机电源开关。
- 未取得示波器/函数发生器权限时，只完成 DC 与低速验证，不声称频响、相位、噪声或硬件性能已验证。

## 8. 下单渠道组合

为了兼顾真品、运费和一次买齐：

1. **Adafruit 一单**：#276、#373、#239、#1957、#356 x4、#4203、#392、#1085、#4209，以及确认控制器后的#592。若和另一个项目合并结账，按项目分摊数量和账目。
2. **Mouser 一单**：MCP6004、MCP6544、插座、DIP开关、MCP1702、保险丝、二极管、精密电阻电容、晶体管和短路帽。选择Mouser为主，是因为MCP6544-I/P可与其余关键件放在同一授权渠道订单。
3. **NUCLEO设为HOLD**：确认STM32Cube工具链后，优先加入同一Mouser单；若当日Mouser缺货，再用DigiKey授权产品页作为备选。

不要从无品牌 marketplace 购买 MCP6004、MCP6544、MCP1702、ADS1115 或关键精密器件。普通收纳盒、标签和非关键线材可以按本地价格选择。

## 9. 下单前逐行检查

- [ ] 完整制造商料号完全一致；封装为 PDIP/THT/TO-92，或 breakout 已焊好排针/连接器。
- [ ] 状态是 Active/In Production，数量有现货；替代料先对照数据手册，不只看标题。
- [ ] MCP6544 明确是所需 push-pull 输出版本。
- [ ] 电位器是 10 kOhm linear；DIP 开关是 2.54 mm through-hole。
- [ ] 电阻为 1%，关键滤波电容为 5% 或更好。
- [ ] 5 V 适配器与 2.1 mm 插座机械匹配；第一次接线确认正负极。
- [ ] USB 线包含 data conductors，电脑端是 USB-A。
- [ ] 结账含税运后仍保留至少约 $20 的项目余量。
- [ ] 收货前不把任何一项标成 `RECEIVED`，搭建前不声称硬件已验证。

机器可编辑、带购买链接和公式预算的版本见 `independent-product-purchase.xlsx`。原CSV保留为前一版追踪快照，不再作为本次下单依据。
