# 采购与复用计划

> **更新说明（2026-08-29）：** 在确认 AFE 必须是独立、可复用产品后，当前下单依据已改为 `INDEPENDENT_PRODUCT_PROCUREMENT.md` 和带链接/公式的 `independent-product-purchase.xlsx`。本文件保留旧购物车逐项分析和早期决策背景；其中“依赖旧购物车共享面包板/电源”的预算方案不再作为冻结采购方案。

价格/库存核对日期：2026-08-29。价格均为美元参考价，不含税、运费和可能的进口附加费；下单页为准。用户已确认截图是尚未下单的“另一个项目购物车”，所以其中任何项目都不能记为现有库存。

## 1. 先给结论

- 截图中的面包板、线材、跳线、测试夹、剥线钳、热缩管和 USB 线都能复用。
- 10 kOhm NTC 可以在后期作为真实模拟传感器；DS18B20 和 INA219 是数字器件，不能用来代替本项目模拟输入通道。
- INA219 默认 I2C 地址 0x40，Adafruit ADS1115 默认 0x48，地址本身不冲突；两者仍需 3.3 V 逻辑、公共地和固件资源核对。
- 5 V 风扇、MOSFET 驱动和三芯 JST 线属于 Equipment Health Controller，不是 AFE 核心件。
- 截图中的 4.7 kOhm 电阻为 5%，适合 LED 限流、I2C 上拉或普通保护；精密增益、阈值和滤波计算仍要买 1% 电阻并实测。
- 截图中的 5 V 适配器和桶形插座不能直接给 3.3 V AFE/MCU 信号节点供电。
- 如果两个项目同时推进，工具可以共享，但面包板、LaunchPad 和已接好的电路不应频繁拆来拆去。

## 2. 截图购物车逐项判断

| 截图项目 | 判断 | 本项目如何使用 / 注意事项 |
|---|---|---|
| DS18B20 x2 | 保留给原项目 | 数字 1-Wire 温度传感器，不经过本项目模拟 AFE；附带 4.7 kOhm 上拉不能代替精密网络 |
| INA219 x1 | 可作后期集成扩展 | 数字 I2C 电流监测，不是模拟电流输入；默认地址可与 ADS1115 共存 |
| 10 kOhm 3950 NTC x1 | 可直接复用 | 很好的后期模拟传感器样例；需要分压器、标定和自热评估 |
| 5 V 风扇 x2 | 原项目专用 | 可在 Phase 5 故障/负载实验中间接使用，但不应从 LaunchPad 直接驱动 |
| MOSFET Driver x2 | 原项目优先 | 适合风扇/负载，不是小信号 AFE 增益级；先核对逻辑与负载电流 |
| QT-to-male-header x2 | 一根留 INA219、一根留 ADS1115 | 非常合适，可避免再买 ADS1115 转接线 |
| JST PH 三芯线 x2 | 原项目优先 | 与风扇驱动接口匹配；AFE 无核心需求 |
| 全尺寸面包板 x2 | 两项目各一块 | 数量合理；避免为了调 AFE 拆掉另一项目 |
| 母公、母母、公公跳线 | 两项目共享 | 公公跳线是面包板核心；母公/母母用于模块和排针 |
| 22 AWG 固芯线套装 | 两项目共享 | 很适合面包板定长布线；注意不要剥皮过长造成相邻短路 |
| USB-C to Micro-B | 先核对两端接口 | MSP-EXP430FR6989 官方套件通常已含 Micro-USB 数据线；截图线只有电脑端具备 USB-C 时才合适 |
| 剥线钳、鳄鱼夹 | 两项目共享 | 必备搭建/测量工具；鳄鱼夹要防止互碰短路 |
| 4.7 kOhm 5% x25 | 可复用但非精密 | 用作普通上拉/限流；精密网络另买 1% |
| Perma-Proto x1 | 暂给原项目或保持未焊 | AFE 面包板验证前不要焊死；Phase 4/5 稳定后再决定是否为 AFE 买第二块 |
| 热缩管 | 两项目共享 | 只用于焊接后的绝缘；面包板阶段需求很少 |
| 5 V 2 A 适配器、桶形插座 x2 | 原项目优先，AFE 条件复用 | 必须经过确认的 3.3 V 稳压器；绝不能把 5 V 直接送入 MCU/ADC/AFE 输入 |
| PCB coaster | 无电气用途 | 纪念品，不计入 BOM |

截图购物车小计为 $137.75。若尚未下单，不建议删减面包板和工具；可考虑把只服务原项目的数量留给原项目，不因为 AFE 再加购风扇、MOSFET Driver 或 JST PH 线。

## 3. 第一单：低风险核心件（NOW）

推荐将通用 Adafruit 小件并入原订单；半导体和精密无源件集中在 DigiKey 或 Mouser 的一个授权渠道下单，减少运费和假货风险。Amazon/eBay/无品牌套件可用于普通跳线和收纳，不应用于关键 IC、比较器和精密测量链。

| 器件/订货建议 | 数量 | 推荐渠道与当前参考 | 购买理由 |
|---|---:|---|---|
| MCP6004-I/P，PDIP-14 | 3 | DigiKey，约 $0.59/只；或 Mouser | 需要至少 2 只，第三只是插错/损坏备用；1.8-6 V、轨到轨 I/O、约 1 MHz GBW |
| MCP6544-I/P，PDIP-14、push-pull | 2 | Mouser，约 $1.43/只 | 需要 1 只，另一只备用；不要误买开漏输出的近似型号 |
| 14-pin、0.3 inch DIP 插座 | 5 | DigiKey，约 $0.55/只 | 避免反复拔插损伤 IC，引脚定位更清楚 |
| 10 kOhm 线性面包板电位器 Adafruit #356 | 4 | Adafruit，约 $1.25/只 | 三个工作位置加一个备用；必须是 linear，不买 audio/log taper |
| ADS1115 breakout Adafruit #1085 | 1 | Adafruit，约 $14.95 | Phase 4 才正式使用，但模块明确、现有 QT 线可复用，适合作为一次性核心采购 |
| 1% 金属膜通孔电阻，1/4 W | 下列每值 10 只 | DigiKey/Mouser 单值散买；合计预算 $10-18 | 比昂贵且阻值不合适的“大套装”更省钱，也减少缺关键值 |
| BAT41-TAP Schottky，DO-35 | 10 | DigiKey，约 $0.32/只（10只价） | 在产、低结电容的通孔保护候选；BAT46 已被标为 obsolete，不建议新采购 |
| 1N4148 通孔二极管 | 20 | DigiKey，约 $0.055/只（10只价） | 通用开关/实验；不是低压钳位的唯一选择 |
| 100 nF X7R 通孔去耦 | 20 | DigiKey/Mouser | 每个 IC 一只且靠近电源脚，多买是为了两个项目通用 |
| 电容通孔组合包 | 1 | DigiKey 的 SparkFun #13698，约 $11.50；或等价授权包 | 覆盖通用实验值；精密滤波电容仍需单独确认公差和实测 |
| 精密滤波电容：10 nF、100 nF、1 uF，5% | 每值 5 | DigiKey/Mouser；1 uF 薄膜可参考 TDK B32522C1105J000 | 建立可复现的 RC 档位；若套装无法保证 5%，单独购买 |
| 10 uF 电解 x10、100 uF 电解 x5 | 1组 | DigiKey/Mouser | 电源缓冲；极性器件，额定电压建议 >=10 V |
| LED 红/绿各 5 | 10 | Adafruit/DigiKey/Micro Center | 状态输出；与 330 Ohm 或 1 kOhm 限流电阻配套 |
| 2N3904 通孔 | 10 | DigiKey/Mouser | Phase 5 开关/故障注入，多余可用于原项目 |
| 2N7000 通孔 | 5 | DigiKey/Mouser | 低电流开关实验；不要把它当作风扇功率 MOSFET |
| 2.54 mm 可折断直排针和短路帽 | 排针 2 条、短路帽 10 | Adafruit/DigiKey | 建立明确的 x1/x2/x5/x10 和滤波档位 |

建议的 1% 电阻值是：

```text
100, 330, 1k, 2.2k, 4.7k, 10k,
16.0k, 22k, 40.2k, 47k, 90.9k, 100k, 1M ohm
```

其中 10 kOhm、40.2 kOhm 和 90.9 kOhm 是理论增益档位的关键值；16.0 kOhm 可与 10 nF 构成约 995 Hz 的示例低通。最终以实际电阻实测值重新计算，不只相信色环。

### 核心增量预算

在截图订单照常购买、已有 LaunchPad 和万用表的假设下，本项目新增核心件预计 **$70-87**，未含税运：

- Adafruit：ADS1115 + 4 个电位器约 $19.95；
- 授权元件渠道：IC、插座、精密电阻、电容、二极管、晶体管、排针等约 $50-67。

如果暂缓 ADS1115 和 Phase 5 晶体管/排针，最低 Phase 1/2 启动可再少约 $20-25，但以后会产生第二次运费。

## 4. 确认后购买（CONFIRM）

| 条件件 | 何时需要 | 推荐与预算 | 为什么不能盲买 |
|---|---|---|---|
| 独立验证控制器 | 需要两项目同时连接或无OSU仪器时 | 当前首选STM32 NUCLEO-G474RE，DigiKey约 $20.13；备选Metro RP2040约 $14.95、LP-MSPM0G3507约 $23.36但库存不稳定 | 不再限定第二块MSP430；按`docs/CONTROLLER_BOARD_SELECTION.md`的角色和工具链取舍决定 |
| 限流 3.3 V 电源 | LaunchPad 供电能力不足或需要独立验证 | 优先申请 OSU 台式电源；购买前明确电流、纹波和端子 | 仅有 5 V 墙插并不等于有安全 3.3 V 实验电源 |
| EspoTek Labrador | OSU 不允许个人项目，且 Windows 11 实测兼容 | 官方约 $29 | 官方页列出的 Windows 支持没有明确写 Windows 11；约 100 kHz 级能力只适合低频初调，不是最终精密证据 |
| 焊接系统 | 进入 Perma-Proto/PCB 且实验室不能焊接 | Pinecil V2 裸笔约 $25.99/$35.99，但含合规 PD 电源、线、支架、焊锡和助焊剂后约 $55-90；Hakko FX-888DX 官方约 $121.47 | 现在的面包板阶段不需焊台；只买“烙铁”并不构成安全完整系统 |

现有LaunchPad用于MSP430兼容profile，官方板载eZ-FET并包含Micro-USB数据线。AFE模拟核心和Standalone USB Validation模式不得依赖该板；参考验证控制器按`docs/CONTROLLER_BOARD_SELECTION.md`另行选择。

## 5. 暂缓购买（LATER）

- **AD9833 模块**：等 Phase 2 测出真实频率范围，并确认所选模块的供电、输出幅度、直流偏置和 3.3 V SPI 兼容性。
- **第二块 Perma-Proto**：等面包板 V1 的增益和滤波稳定；焊错永久板比第二次运费更贵。
- **定制 PCB、端子、外壳、面板**：Phase 6 原理图和接口冻结后采购。
- **Analog Discovery 3**：除非长期做大量 ECE 项目且学校仪器不可用；不是此项目启动条件。
- **精密电压基准、校准级 DMM**：Phase 4 看到误差预算后再决定。
- **随机低价运放/二极管套装**：型号真实性、批次和数据手册不明确会使排错成本高于省下的钱。

## 6. 三种预算方案

| 方案 | AFE 项目预算内购买 | 适合情况 | AFE 预计小计（税运前） |
|---|---|---|---:|
| 最低启动 | Phase 1/2 关键 IC、插座、精密电阻/电容/二极管和电位器；暂缓 ADS1115/Phase 5 件 | 预算优先，愿意以后补单 | 约 $45-65 |
| 推荐一次购齐核心件 | 完整 AFE 核心件，包括 ADS1115 和便宜备用件 | 希望减少第二次元件运费 | 约 $70-87；CSV 当前逐项合计 $86.63 |
| 双项目并行/自动验证 | 推荐方案 + NUCLEO-G474RE验证控制器 | 两个项目长期保持接线，或需要DAC/ADC自动低速验证 | 当前精确小计约 $106.76；另留 $3-6 给第二根USB数据线 |

已确认 $200 只用于 AFE 项目，MM420 和另一个项目的 $137.75 购物车均在预算外单独核算。**本文件早期版本**的 AFE `NOW` 项逐项参考小计是 $86.63、余量约 $113.37；该数字依赖共享旧购物车物料，现已被带链接的独立产品清单 $106.25（A+B）/ $129.33（A+B+C）替代。

这项预算依赖另一项目实际购买并共享面包板、跳线、固芯线、测试夹和一根 QT 线。建议将 ADS1115 与四个 10 kOhm 电位器并入同一笔 Adafruit 结账以减少运费，但把约 $19.95 记在本项目账下；若另一购物车取消，本项目要先从 $113.37 余量中补齐基础搭建工具。

## 7. 渠道原则和下单验收

### 渠道优先级

1. IC、精密电阻电容和保护器件：DigiKey、Mouser 或厂商授权分销商；
2. Adafruit 专用模块/连接线：Adafruit 原站，减少版本不一致；
3. 普通工具和收纳：Adafruit、Micro Center 或可信本地店；
4. 市场平台只买非关键机械/线材，不能仅凭商品标题替代数据手册。

### 每一行下单前核对

- 完整制造商料号和封装，必须是 through-hole/PDIP 或明确带已焊排针的 breakout；
- `Active/In Production`，不选 obsolete；
- 运放/比较器供电范围包含 3.3 V；比较器确认 `push-pull`；
- 电阻公差 1%，滤波关键电容 5% 或更好；
- 电解电容极性和额定电压；
- 数量包含 1-2 个合理备用，不囤积昂贵模块；
- 分销商结账页的运费、关税和交期；
- 到货后拍外包装标签和料号，测量并建立 `as-built BOM`。

## 8. 参考产品页

- TI MSP-EXP430FR6989：https://www.ti.com/tool/MSP-EXP430FR6989
- Mouser MSP-EXP430FR6989：https://www.mouser.com/ProductDetail/Texas-Instruments/MSP-EXP430FR6989
- MCP6004：https://www.microchip.com/en-us/product/MCP6004
- DigiKey MCP6004-I/P：https://www.digikey.com/en/products/detail/microchip-technology/MCP6004-I-P/523060
- MCP6544：https://www.microchip.com/en-us/product/MCP6544
- Mouser MCP6544-I/P：https://www.mouser.com/ProductDetail/Microchip-Technology/MCP6544-I-P
- DigiKey BAT41-TAP：https://www.digikey.com/en/products/detail/vishay-general-semiconductor-diodes-division/BAT41-TAP/4825749
- DigiKey 1N4148：https://www.digikey.com/en/products/detail/onsemi/1N4148/458603
- DigiKey SparkFun capacitor kit #13698：https://www.digikey.com/en/products/detail/sparkfun-electronics/13698/17887656
- Adafruit ADS1115 #1085：https://www.adafruit.com/product/1085
- Adafruit 10 kOhm potentiometer #356：https://www.adafruit.com/product/356
- Klein Tools MM420 官方页：https://www.kleintools.com/catalog/multimeters/digital-multimeter-auto-ranging-600v-0
- Lowe's MM420：https://www.lowes.com/pd/Klein-Tools-Digital-Multimeter-TRMS-Auto-Ranging-600V-Temp/5014305581
- Home Depot MM420：https://www.homedepot.com/p/320822810
- EspoTek Labrador：https://espotek.com/labrador/

产品链接用于核对型号而非背书；库存、价格、Windows 支持和附加费在购买日重新确认。
