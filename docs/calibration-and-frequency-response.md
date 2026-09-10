# 校准与离线频率响应

**软件 schema：** `calibration-analysis.v1`、`calibration-criteria.v1`、
`calibration-evaluation.v1`、`calibration-coefficients.v1`、
`frequency-response-analysis.v1`、`frequency-response-criteria.v1`、
`frequency-response-evaluation.v1`
**证据状态：** HOST_TEST / SYNTHETIC  
**硬件校准或带宽验证：** 未进行

## 1. 这一步解决什么

Step 6 增加两种纯离线数学能力：

1. 用一组“被测读数”和一组“参考读数”拟合线性校准系数，并把系数应用为新记录；
2. 用已经提供的频率、输入幅值和输出幅值计算增益曲线与一个可解释的截止频率。

“纯离线”表示函数只接收内存中的 Measurement，不打开串口、不控制仪器、不产生真实电压，也不从波形估计频率。因此，这一步验证的是软件公式、输入边界和证据追踪，不是模拟硬件性能。

## 2. 初学者先理解校准

理想传感器或 ADC 的读数应等于参考值，但真实系统常有两类系统误差：

- 比例误差：每增加 1 个单位，读数变化得太多或太少；
- 偏置误差：输入为零时仍有固定偏差。

本项目用线性模型描述它们：

```text
reference = scale × observed + offset
```

例如被测读数为 `0, 50, 100 mV`，参考读数为 `10, 110, 210 mV`，拟合得到 `scale=2`、`offset=10 mV`。新的 `25 mV` 被测读数会得到 `60 mV` 校准值。

这里使用普通最小二乘法。它选择一组 scale/offset，使全部参与点的“校准值与参考值之差的平方和”最小。至少需要两个不同的被测值；默认要求至少三个可用点，以避免仅靠两个点产生看似完美但没有冗余的信息。

### 2.1 为什么不能覆盖原始读数

原始记录是证据。若直接把 `25 mV` 改写为 `60 mV`，之后无法区分仪器实际报告了什么、软件后来做了什么。正式实现因此：

- 冻结系数 ID 和版本；
- 保存每个参与拟合的 observed/reference `record_id` 和 `raw_record_id`；
- 保存两个数据源，允许未来用 `BENCH_DMM` 作为参考、用 `BENCH_CONTROLLER` 作为被测来源；
- 报告校准前后 RMSE、平均绝对误差和最大绝对误差；
- 应用系数时创建新的 Measurement；
- 新记录保留原始 `raw_record_id`、时间、来源、状态和质量标记。

系数本身不能提升证据等级。用 SYNTHETIC 数据拟合出的系数仍是 SYNTHETIC/HOST_TEST 软件证据，不能写成“仪器校准完成”。

### 2.2 最小调用示例

```python
from analog_validation.analysis import (
    CalibrationApplicationConfig,
    CalibrationFitConfig,
    apply_linear_calibration,
    fit_linear_calibration,
)

fit = fit_linear_calibration(
    observed_batch,
    reference_batch,
    CalibrationFitConfig(
        observed_channel="adc.raw",
        reference_channel="dmm.reference",
        coefficient_id="adc-linear",
        coefficient_version="1",
    ),
)

if fit.is_complete and fit.coefficients is not None:
    applied = apply_linear_calibration(
        new_observed_batch,
        fit.coefficients,
        CalibrationApplicationConfig(
            input_channel="adc.raw",
            output_channel="adc.calibrated",
            output_record_prefix="adc-cal-v1",
        ),
    )
```

### 2.3 已落地的产品工作流

校准不再只是可由 Python 调用的数学函数。Simulator 和 CSV Replay 现在
都能通过同一个产品编译器、worker 和 service 完成以下闭环：

```text
两路成对 Measurement
  -> 质量/单位检查
  -> 线性拟合
  -> 校准前后误差与验收准则
  -> TestRun PASS/FAIL/INCOMPLETE
  -> result-export.v1
  -> JSON/CSV、Dashboard、文字/HTML/SVG 报告
  -> 独立 calibration-coefficients.v1 文件
```

命令行示例：

```powershell
analog-validation simulate calibration `
  --points 8 `
  --output .\calibration-result.json `
  --coefficients-output .\calibration-coefficients.json `
  --json

analog-validation coefficients inspect `
  --input .\calibration-coefficients.json `
  --json
```

结果文件和系数文件均默认拒绝覆盖。系数检查只做有界 schema、数值、
来源与 lineage 验证，明确返回“未应用”；当前版本不会自动修改之后的
Measurement，也不会写入控制器或固件。Dashboard 提供同样的选择路径、
保存新文件和加载检查按钮。

底层校准算法可以比较两个不同 EvidenceSource 的批次；当前产品 v1
TestRun 只有一个 evidence source 字段，因此 Simulator/Replay 产品工作流
要求 observed 与 reference 来自同一次运行或同一个 replay 数据集。未来
若要组合 ADC 与独立 DMM 的 BENCH 证据，必须先版本化扩展多来源 TestRun，
不能把两种来源压缩成一个标签。

## 3. 初学者先理解频率响应

对一个正弦信号，幅值比定义为：

```text
ratio = output amplitude / input amplitude
gain_dB = 20 × log10(ratio)
```

幅值相等时 ratio 为 1、增益为 0 dB；输出幅值约为输入的 `0.7071` 倍时，增益约为 `-3.0103 dB`。

正式分析需要三组等长数据：

- 频率，单位必须明确为 Hz；
- 输入幅值，单位为 V 或 mV；
- 输出幅值，单位为 V 或 mV。

三组数据必须来自同一个 EvidenceSource，并使用互不重复的记录 ID。V/mV 会先规范到同一单位，所以单位写法不同不会改变 ratio。

### 3.1 截止频率怎样得到

v1 把第一个可用频率点的增益作为参考增益，并将目标设为：

```text
cutoff target = first-point gain - cutoff_drop_db
```

默认 `cutoff_drop_db = 3.0102999566 dB`。用户必须保证第一个点确实代表所需的低频/通带基准；软件不会猜测平台区或自动选择最高增益。

当相邻两点跨过目标时，软件在“dB 对 log10(Hz)”坐标上做线性插值。这比直接在 Hz 上插值更符合常用对数频率图的表达，也把算法写进结果的 `interpolation_method` 中。

- 没有交点：返回 `cutoff-crossing` 缺口，不发布截止值；
- 恰好一个交点：发布截止频率；
- 多个交点：视为曲线有歧义，明确拒绝，不擅自选择第一个或最后一个。

### 3.2 为什么输入/输出幅值必须大于零

输入为零会导致除零；负幅值不符合这里使用的“正幅值大小”语义；ratio 小于等于零时对数不存在。因此 v1 明确拒绝零/负输入和零/负输出，而不是生成 `inf`、`nan` 或误导性的 dB。

### 3.3 最小调用示例

```python
from analog_validation.analysis import (
    FrequencyResponseAnalysisConfig,
    analyze_frequency_response,
)

result = analyze_frequency_response(
    frequency_batch,
    input_amplitude_batch,
    output_amplitude_batch,
    FrequencyResponseAnalysisConfig(
        frequency_channel="stimulus.frequency",
        input_amplitude_channel="afe.input.amplitude",
        output_amplitude_channel="afe.output.amplitude",
    ),
)
```

### 3.4 已落地的频响产品工作流

频率响应现已从纯 Python 数学函数接入与 DC、迟滞、校准相同的产品链：

```text
显式 Hz / 输入幅值 / 输出幅值三路 Measurement
  -> 单位、质量、顺序与 lineage 检查
  -> 幅值比与 dB 曲线
  -> -3 dB 截止频率插值
  -> 目标截止频率容差与最小点数准则
  -> TestRun PASS/FAIL/INCOMPLETE
  -> result-export.v1
  -> JSON/CSV、Dashboard、文字/HTML/SVG 幅频报告
```

Simulator 使用确定性单极点幅值模型。`simulated cutoff` 是合成数据模型
的参数，`target cutoff` 是独立的验收目标；把两者分开可以有意识地构造
PASS 或 FAIL，而不会让模拟器为了迎合标准而自动改变结果。默认使用 21 个
对数分布点、10 Hz–100 kHz、1000 Hz 模型截止和 15% 目标容差。

```powershell
analog-validation simulate frequency `
  --points 21 `
  --simulated-cutoff-hz 1000 `
  --target-cutoff-hz 1000 `
  --output .\frequency-result.json `
  --json

analog-validation report `
  --input .\frequency-result.json `
  --output .\frequency-report `
  --json
```

CSV Replay 使用同一分析、准则、结果和报告代码，但要求文件显式提供三路
等长记录。当前产品没有输出型频响 runner，也没有 Serial 频响任务：它不会
产生扫频信号、控制仪器或把接收到的任意串口值解释成物理带宽。

## 4. 质量与 incomplete 语义

两个分析都复用默认拒绝的质量策略：VALID 且有限的点可使用；SUSPECT 点只有在调用者显式允许其具体质量 flag 时才可使用；INVALID、缺失和非有限点不能被提升。

校准点保留 observed/reference 各自的决定。频响点保留 frequency/input/output 三个决定。频响 v1 采用有意保守的完整性规则：至少需要 10 个请求点，而且每个请求点都必须可用、频率必须严格递增，才会发布截止频率；任何被排除的点都会产生 `usable-points:n/total` 缺口。数据不足或不完整时结果仍保留全部逐点证据和 `missing_requirements`，但不发布看似完整的系数或截止频率。

## 5. 当前验证和明确未验证内容

已经由主机测试验证：

- 精确线性拟合、混合 V/mV、系数应用和原始记录不变；
- 系数身份、版本、双来源和参与记录链；
- 校准前后误差指标；
- ratio、dB、唯一交点和对数频率插值；
- 频响 criteria/TestRun、三引用逐点导出、Simulator/Replay 产品链、
  CLI/Dashboard 与确定性幅频 SVG；
- 质量排除、点数不足、相同被测值；
- 零/负幅值、非正频率、频率乱序、无交点和多交点。

尚未验证：

- 任何 ADC、运放、比较器或滤波器的真实精度；
- 任何 DMM、示波器或信号源的校准状态；
- AFE 的真实截止频率、噪声或带宽；
- 实时采样、FFT、串口吞吐或仪器控制；
- MSP430 或其他控制器的实物连接。

未来接入硬件时，adapter 负责取得 Measurements；本文件中的数学核心不需要因控制器品牌而重写。物理结论仍必须附带硬件版本、接线、仪器、环境和 BENCH evidence。
