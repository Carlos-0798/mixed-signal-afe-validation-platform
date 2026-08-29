# 初学者项目启动指南

更新时间：2026-08-29

## 1. 我们究竟要做什么

这个项目要做一条“可配置的模拟信号处理通道”，并建立一套能够证明它是否按设计工作的验证方法。它不是一块普通传感器板，也不是只把若干模块接到 MSP430 上。

信号会依次经过以下功能：

```text
0-3.3 V 测试信号/传感器
        |
        v
输入保护 -> 缓冲 -> 可选增益 -> 可选低通滤波 -> ADC 采样
                                      |
                                      +-> Schmitt Trigger 数字事件
```

- **输入保护**像安全带：误接或瞬态出现时限制电流、钳位电压，但不能把任意高压变成安全电压。
- **缓冲器**隔离前后电路：它让后级读取信号时尽量不“拖动”原信号。
- **非反相放大器**把小信号放大。理想增益为 `1 + Rf/Rg`，但真实输出不能无限接近电源轨。
- **低通滤波器**保留慢变化信号、衰减快速噪声。一阶 RC 截止频率为 `1/(2*pi*R*C)`。
- **Schmitt Trigger**使用两个不同阈值。信号在临界点附近抖动时，输出不会反复跳变。
- **ADC**把电压变成数字码。12-bit ADC 有 4096 个码，但分辨率不等于绝对准确度。
- **UART + CRC**把数据送到电脑；CRC 用于发现传输损坏，不用于加密或纠错。
- **Python 验证工具**负责记录、拟合、排除饱和点和生成报告。合成数据只验证软件逻辑，不能代替实测。

本项目是独立个人项目。它可以通过公开的 3.3 V UART/I2C/SPI/GPIO 接口与 MSP430 Equipment Health Controller 配合，但代码、接线、BOM 和结论都保持独立；不得并入 OSU Lab Bench Monitor Capstone。

## 2. 当前真实状态

Phase 0 已建立仓库、理论计算、理想化 LTspice 网表、通信协议、合成数据工具和 Python 测试。它证明了设计与软件骨架可以继续推进，**没有证明任何真实硬件已经工作**。

进入 Phase 1 前，需要同时满足四个条件：

1. 明确实际拥有的板卡和零件完整型号；
2. 至少有一台可用万用表；
3. 明确 3.3 V 供电、公共地和面包板接线；
4. 我们共同检查首次上电接线照片和断电测量结果。

## 3. 分阶段路线图

| 阶段 | 做什么 | 为什么这样安排 | 需要看到的证据 |
|---|---|---|---|
| Phase 0，已完成 | 理论、理想仿真、协议和软件测试 | 在花钱、接线前发现架构错误 | 计算文档、仿真日志、pytest 结果；不是硬件证据 |
| Phase 1 | 3.3 V/VBIAS、保护、MCP6004 缓冲、x1/x2/x5/x10、手动 DC sweep | 先用低频直流和万用表验证最基础的放大关系 | 清晰接线照片、DMM 型号、供电限流值、原始输入/输出表 |
| Phase 2 | 两档以上 RC 滤波、MCP6544 Schmitt Trigger、GPIO 事件 | 学会频率响应与迟滞；开始需要示波器/波形源 | 截止频率曲线、上下阈值实测、示波器截图 |
| Phase 3 | 参考验证控制器的ADC/DAC或PWM、UART、自动DC sweep、Python实时图；另做MSP430兼容profile | 把人工读数变为可重复自动测试，同时不绑定某一块板 | 参考控制器固件版本、原始UART/CSV、自动sweep结果、独立兼容报告 |
| Phase 4 | ADS1115 对照、增益/偏置校准、重复性分析 | 区分“码数更多”和“系统真的更准” | 两种 ADC 的同一信号对照及校准前后误差 |
| Phase 5 | 自动扫频、故障注入、PASS/FAIL 报告 | 验证系统面对开路、短路、饱和和噪声时的行为 | 至少 50 条有来源标签的测试记录 |
| Phase 6 | KiCad 原理图/PCB、ERC/DRC、生产和 bring-up | 只有面包板电路稳定后才值得固化，避免返板 | PCB 制造文件、BOM、首板上电记录、与面包板对照 |

预计时间是学习和实验时间，不含缺货、运输、实验室排队和返工。第一次做项目时，以每个阶段真正留下可复查证据为目标，不追求赶进度。

## 4. 软件准备和安装顺序

### 4.1 现在安装

1. **Git for Windows**：保存每一步变化，出错时可以比较，而不是靠文件副本猜版本。本机已安装 2.55.0。
2. **Python 3.12 64-bit**：项目支持 Python 3.10+；本机已安装并验证 python.org 的 3.12.10。选择 3.12 是为了与当前测试基线保持一致。
3. **Visual Studio Code**：不是软件运行依赖，但便于初学者查看代码、运行 pytest 和理解错误。本机已安装 1.135.0 及 Python、Pylance、Ruff 扩展。
4. **LTspice**：做未来器件模型和电路行为检查。本机已能运行 26.0.1，但 Software Phase 1 不依赖它。

安装后在 PowerShell 中检查：

```powershell
git --version
python --version
python -m pip --version
```

项目环境：

```powershell
cd <项目目录>
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

若 PowerShell 阻止激活，可以直接使用 `.\.venv\Scripts\python.exe -m pytest`，不需要为了这个项目降低整台电脑的脚本安全策略。

### 4.2 暂缓安装

- **Code Composer Studio**：只用于未来 MSP430 兼容 profile；软件产品核心不依赖 CCS。
- **串口终端和 pyserial**：Software Phase 4 开始真实串口适配时再安装。
- **KiCad 10**：Phase 6 再安装；现在画 PCB 会把尚未验证的接线固化。
- **MSP430 GCC 独立工具链**：CCS 路线无法满足需求时再评估。
- **Labrador 软件/驱动**：只有确认购买并确认 Windows 11 兼容性后安装。
- **AD9833 库**：明确模块电压、幅度和偏置接口之后再选；不同廉价模块并不等价。

官方入口：

- Git for Windows：https://git-scm.com/install/windows
- Python：https://www.python.org/downloads/windows/
- Visual Studio Code：https://code.visualstudio.com/
- Code Composer Studio：https://www.ti.com/tool/download/CCSTUDIO
- LTspice：https://www.analog.com/en/resources/design-tools-and-calculators/ltspice-simulator.html
- KiCad：https://www.kicad.org/download/windows/

## 5. 实验台和安全准备

最低工作区应有：明亮桌面、防滚落的小零件盒、可打印/查看的数据手册、万用表、面包板、固芯线、跳线、测试夹和 USB 数据线。饮料、金属碎屑和风扇叶片应远离通电面包板。

首次通电流程固定如下：

1. 断电核对 IC 缺口、1 脚和电源脚；
2. 每个 IC 的电源脚旁放 100 nF 去耦；
3. 断电测 3.3 V 对 GND，排除近似短路；
4. 暂不插 IC，先测电源轨；
5. 设置电源限流，插入一个功能块；
6. 先测 VBIAS，再接信号源，最后接 MCU/ADC；
7. 信号源、AFE、LaunchPad 和仪器必须共地；
8. 出现发热、异味、电压异常或电源限流立即断电。

5 V 墙插电源不能直接接任何3.3 V控制器GPIO/ADC、ADS1115模拟输入或本项目0-3.3 V节点。若以后独立使用它，必须先经过验证的3.3 V稳压和去耦方案。Phase 1初期电源方案必须独立记录；不能让AFE产品只能依靠LaunchPad供电。

## 6. 我们如何跟进和对齐

每个阶段都按同一个小循环推进：

1. 我先给出本次只搭哪一个小电路、原理、元件值、预期电压和停止条件；
2. 你发回零件完整型号、清晰俯视照片和 DMM/仪器读数；
3. 我们在上电前逐线核对，在上电后先核对电源和 VBIAS；
4. 保存原始数据，不手工“修漂亮”；
5. 把理论、仿真、实测并排比较，并记录偏差原因；
6. 验收通过后才进入下一个功能块。

为了使照片可核对，建议红线只用于正电源、黑/蓝线只用于地、其他颜色用于信号；IC 缺口朝同一方向，并在照片中标出面包板电源轨是否中间断开。

## 7. 下一次对齐需要你的回答

已确认：截图购物车未下单、只有一块 LaunchPad、电脑有 USB-A、计划在项目预算外购买 Klein Tools MM420、OSU 仪器不保证可用、暂时没有焊接设备且通风满足；AFE 项目另有独立的 $200 器件预算。无 OSU 仪器时的详细软件主导备用路线见 `BUDGET_AND_FALLBACK_DECISION.md`。

下一次请只确认：

```text
1. Windows 的具体版本：
2. MSP-EXP430FR6989 板上 revision/丝印（方便时拍正反面照片即可）：
```

当前采购源是 `../hardware/bom/INDEPENDENT_PRODUCT_PROCUREMENT.md` 和带链接/公式的 `../hardware/bom/independent-product-purchase.xlsx`。其中 `BUY_NOW` 表示建议进入购物车，不表示已经授权、下单或收货；`CONFIRM_TOOLCHAIN` 表示先完成控制器/工具链决策。结账前必须再次核对完整料号、封装、库存、税运和 AFE 归属总额不超过 $200。
