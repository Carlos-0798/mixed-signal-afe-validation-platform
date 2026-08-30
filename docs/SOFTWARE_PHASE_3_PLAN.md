# Software Phase 3 文件级实施计划

**阶段名称：** 测试执行、质量感知分析与结构化结果<br>
**规划状态：** 实施中，进度 6/8<br>
**预计时间：** 7–10 个初学者开发日<br>
**前置：** Software Phase 2 的 adapter、Replay、共用读取工作流和兼容基线完成<br>
**硬件要求：** 无<br>
**硬件验证：** 0

## 当前进度

- [x] Step 1：分析公共语义与质量 policy；
- [x] Step 2：正式 DC sweep 分析；
- [x] Step 3：DC sweep criteria 与结论映射；
- [x] Step 4：控制器无关 DC sweep runner；
- [x] Step 5：正式迟滞分析与 runner；
- [x] Step 6：校准与离线频率响应；
- [ ] Step 7：版本化 CSV/JSON 结果导出；
- [ ] Step 8：黄金兼容、构建和阶段收口。

Step 6 已通过 48 项专门测试、992 项完整回归和 100% 正式 package 覆盖。正式校准路径保存两个来源、系数版本、拟合输入引用和校准前后误差，并只创建派生 Measurement；离线频响路径计算 ratio/dB，并只对唯一交点做对数频率插值。证据见 `reports/software-phase3-step6.md`。这不表示系数来自标准器、真实 AFE 带宽已测量、Step 7–8 或任何硬件功能已经完成。

## 1. 初学者先理解这一阶段解决什么

Phase 2 回答的是“软件能否从不同来源取得结构一致的数据”。Phase 3 回答的是另外三个问题：

1. 这些数据是否足够、有效并适合计算；
2. 增益、偏置、饱和点和迟滞等结果如何计算；
3. 按明确标准，本次测试应当是 `PASS`、`FAIL`、`INCOMPLETE` 还是 `UNSUPPORTED`。

这三个问题必须分开。采满规定数量的记录只代表 acquisition `COMPLETED`，并不代表工程结论 `PASS`。同样，拟合出一条直线也不代表真实硬件通过，因为输入可能来自 `SYNTHETIC` 或 `CSV_REPLAY`。

## 2. 阶段目标

建立不依赖具体控制器、串口、GUI 或实验室仪器的正式分析与 runner 层：

- 每个数值结论能够追溯到输入 `Measurement.record_id`；
- 原始点永远保留，被排除点必须保存逐点原因；
- 缺失、非有限、错误单位、错误方向和质量异常不能被静默忽略；
- 分析结果和 PASS/FAIL 标准分别版本化；
- `INCOMPLETE`、`UNSUPPORTED`、`ABORTED` 和 `ERROR` 不能变成 PASS；
- Simulator、CSV Replay 和未来硬件 adapter 使用同一分析和 runner 入口；
- 自动输出只能通过现有 `DeviceAdapter` 安全门执行；
- 所有主机测试继续明确标为 `HOST_TEST`、`SYNTHETIC` 或 `CSV_REPLAY`。

## 3. 架构边界

```text
DeviceAdapter / ReadWorkflowResult
              |
              v
       runners/          负责能力预检、生命周期、等待和 TestRun 映射
              |
              v
       analysis/         负责纯计算、质量规则、逐点解释和可追溯结果
              |
              v
       TestRunResult     只在证据完整且标准明确时产生 PASS/FAIL
              |
              v
       exports/          负责稳定 CSV/JSON，不改变计算或证据来源
```

依赖方向只能向下：分析函数不能导入 adapter、串口、GUI、`dashboard` 或 `tools`。导出函数不能重新计算结果。runner 不能根据板卡名称猜能力或安全范围。

## 4. 已冻结的关键决策

### 4.1 Phase 2 公共接口保持兼容

- 不修改 `read-workflow.v1` 的既有含义；
- 不把只读 `SimulatorAdapter` 或 `CsvReplayAdapter` 变成可输出设备；
- Phase 3 通过新增模块和组合已有接口扩展功能；
- 如果后续确需改变 Phase 2 行为，必须升级对应 schema、黄金数据和迁移说明。

### 4.2 分析和判定分离

`DCSweepAnalysisResult` 可以描述 gain、offset、残差和排除点，但它本身不等于 PASS。只有带版本的 acceptance criteria 才能形成 `TestRunResult.PASS` 或 `FAIL`。

### 4.3 结构错误与测量质量分开处理

- 错误类型、单位、来源组合、重复记录 ID 或无法配对属于结构错误，必须明确拒绝；
- 缺失值、非有限值、饱和、超范围或设备/通信质量问题保留为逐点排除原因；
- 默认不使用 `SUSPECT`/`INVALID` 点拟合；未来若允许，必须由显式版本化 policy 开启。

### 4.4 自动输出仍然是受控能力

自动 DC sweep runner 只有在以下条件同时满足时才能调用 `set_stimulus`：

1. adapter 明确声明输出命令和通道；
2. 配置明确 `allow_output=true`；
3. 每个 setpoint 在已声明的安全范围内且单位一致；
4. adapter 明确声明 `SAFE_SHUTDOWN`；
5. runner 对成功、失败和异常路径都执行安全关闭/断开。

Phase 3 只用测试专用 reference adapter 验证这套主机逻辑。不会连接真实 DAC、PWM、MSP430、AFE 或仪器。

## 5. 目标目录

```text
src/analog_validation/
├── analysis/
│   ├── __init__.py
│   ├── common.py
│   ├── dc_sweep.py
│   ├── hysteresis.py
│   ├── calibration.py
│   └── frequency_response.py
├── runners/
│   ├── __init__.py
│   ├── common.py
│   ├── dc_sweep.py
│   └── hysteresis.py
└── exports/
    ├── __init__.py
    ├── csv_v1.py
    └── json_v1.py

tests/
├── unit/
│   ├── test_analysis_common.py
│   ├── test_dc_sweep_analysis.py
│   ├── test_hysteresis_analysis.py
│   ├── test_calibration.py
│   ├── test_frequency_response.py
│   ├── test_dc_sweep_runner.py
│   ├── test_hysteresis_runner.py
│   └── test_result_exports.py
├── integration/
│   └── test_phase3_analysis_workflow.py
└── golden/
    └── test_phase3_results_golden.py

test-data/golden/
├── phase3_dc_sweep_input_v1.json
├── phase3_dc_sweep_result_v1.json
├── phase3_hysteresis_result_v1.json
└── phase3_public_api.json
```

实际文件可以在实施时按职责细分，但不能改变上述层级和依赖方向。

## 6. 版本化数据和计算规则

### 6.1 共用分析语义

Step 1 将冻结：

- point disposition：`INCLUDED`、`EXCLUDED`、`INVALID`；
- 明确的逐点排除原因；
- 输入记录 ID、输出记录 ID、预测值、残差和质量说明；
- V 与 mV 的唯一规范化路径；
- 重复 ID、混合 evidence source、通道/单位不匹配的错误规则；
- 有限值、状态和质量标志的默认使用 policy。

### 6.2 DC sweep 结果

正式结果至少保存：

- gain、offset、R²、RMSE 和最大绝对残差；
- 总点数、使用点数和排除点数；
- 每个点的输入/输出记录引用；
- 每个使用点的预测值和残差；
- 每个排除点的一个或多个明确原因；
- 分析配置/schema 版本；
- acceptance criteria 的版本和逐项判定结果。

数学上两点可以确定一条直线，但默认工程分析至少需要 3 个有效、不同输入点，因为两点无法提供有意义的线性度检查。最少点数必须可配置且受边界验证。

### 6.3 饱和排除

上下边界必须有限且 `low < high`。位于或超出边界的点默认排除，并区分 `LOW_SATURATION` 与 `HIGH_SATURATION`。如果原记录已有 `SATURATED` flag，即使数值刚好落在内部，也不能被静默当作正常点。

### 6.4 迟滞结果

正式迟滞分析必须：

- 验证 rising 输入单调不减、falling 输入单调不增；
- 验证数字状态只为 0/1 且方向匹配；
- 保存每次转换前后两条记录 ID；
- 使用转换区间中点作为 v1 阈值估计，并在结果中说明方法；
- 支持重复 cycle，保存每次 high/low/width 与汇总统计；
- 明确拒绝无转换、反向转换、多次抖动或 high < low；
- 只有 criteria 完整时才形成 PASS/FAIL。

### 6.5 校准边界

校准使用不可变、版本化线性系数。应用校准时创建派生记录，不修改原始 `Measurement`，并保留 `raw_record_id` 和系数版本。Phase 3 不声称系数来自标准器；合成/回放校准仍保持原证据边界。

### 6.6 频率响应边界

本阶段只做离线幅值点分析：频率、输入幅值和输出幅值由显式数据提供，计算 ratio、dB 和可解释的截止频率插值。不做 FFT、实时波形采集、示波器控制或物理带宽声明。

## 7. 八个实施检查点

### Step 1：分析公共语义与质量 policy

创建 `analysis/common.py`，冻结逐点状态、排除原因、记录引用、单位规范化和质量 policy。扩展架构测试，保证正式分析层只依赖标准库和正式 domain/errors。

验收：非法类型、NaN/Inf、错误单位、重复 ID、来源冲突和质量组合都有稳定测试；旧算法尚不迁移。

**状态：已完成。** `analysis-common.v1` 已实现 record lineage、单来源 batch、逐记录 disposition/reason、显式 suspect allowlist 和有限 V/mV 规范化；冻结的 Phase 2 顶层 API 未改变。

### Step 2：正式 DC sweep 分析

迁移并重写线性拟合和饱和排除。结果保留所有点、逐点原因、预测值、残差、R²、RMSE 和最大残差；旧 `dashboard.measurements.dc_sweep` 仅作为迁移对照，之后删除或变为薄兼容入口。

验收：精确直线、带噪数据、上下饱和、质量异常、点数不足、相同输入、混合单位和阈值边界均有测试。

**状态：已完成。** `dc-sweep-analysis.v1` 已实现双记录追溯、顺序配对、逐点质量/饱和原因、默认至少三个有效点、明确 incomplete 缺口，以及 gain、offset、R²、RMSE、最大残差和逐点预测/残差；不产生 PASS/FAIL，也不控制输出。

### Step 3：DC sweep criteria 与结论映射

增加版本化 acceptance criteria，包括目标 gain/容差、最大 offset、最小 R²、最大 RMSE 和最低有效点数。把分析结果映射到正式 `TestRunResult`，并保存每项规则的实际值、限制和通过状态。

验收：完整合格数据得到 PASS，完整超差数据得到 FAIL；没有 criteria、缺失数据或不足点数不能得到 PASS。

**状态：已完成。** `dc-sweep-criteria.v1` 和 `dc-sweep-evaluation.v1` 已实现五项逐规则记录、criteria/analysis 单位一致性、TestRun metadata/证据一致性，以及安全的 PASS/FAIL/INCOMPLETE 映射；示例阈值仅为 HOST_TEST fixture，不是硬件规格。

### Step 4：控制器无关 DC sweep runner

建立 `DCSweepPlan` 与 runner。支持 setpoint 序列、重复次数、可注入 settle/wait 函数、显式通道/单位和 TestRun metadata。先做全量能力/安全预检，再执行输出和读取；任一路径都安全关闭。

验收：测试专用 reference adapter 验证正常、能力不足、越界 setpoint、中止、读取失败和 shutdown 失败。只读 Simulator/CSV 请求返回 `UNSUPPORTED` 且不产生输出。

**状态：已完成。** `dc-sweep-runner.v1` 已实现版本化 plan/acquisition/result、全量写前预检、setpoint/repetition/settle/abort、部分证据保留、所有权明确的 disconnect/safe-shutdown，以及清理成功后才执行的 analysis/criteria 映射。测试专用输出 adapter 只存在于 tests；正式 Simulator/CSV 保持只读。

### Step 5：正式迟滞分析与 runner

迁移迟滞算法，增加方向、状态、重复 cycle、转换引用和统计；runner 使用同一安全输出原则组织 rising/falling sweep。

验收：正常转换、边界中点、多 cycle、无转换、反向序列、抖动、缺失点和 high < low 均有稳定结果。

**状态：已完成。** `hysteresis-analysis.v1` 保存逐点模拟/数字证据和转换前后四条引用，以明确的相邻输入区间中点估计阈值；`hysteresis-criteria.v1` 只对完整多 cycle 统计形成 PASS/FAIL；`hysteresis-runner.v1` 在输出前检查全部权限/能力/单位/范围/安全关闭，并在清理成功后分析。无转换/缺失保持 INCOMPLETE，反向、抖动、多转换、非二进制状态和 `high < low` 明确拒绝。

### Step 6：校准与离线频率响应

实现不可变校准系数、派生记录链和校准前后指标；实现离线幅频点、ratio/dB 与截止频率插值。二者都不导入串口或科学计算第三方库。

验收：系数边界、单位、零输入幅值、非正 ratio、频率顺序、无交点和多交点都有明确处理。

**状态：已完成。** `calibration-analysis.v1` 使用普通最小二乘拟合 `reference = scale × observed + offset`，保存参与拟合的 record/raw IDs、双来源和前后 RMSE/MAE/最大绝对误差；应用系数时生成新记录并保留原 `raw_record_id`、来源、时间、状态和质量。`frequency-response-analysis.v1` 只接收显式 Hz 与输入/输出幅值批次，使用 `20 log10(Vout/Vin)` 和 `linear-db-versus-log10-hz` 插值；无交点保持 incomplete，多交点拒绝为歧义。二者均为标准库纯函数，无 I/O、FFT 或硬件控制。

### Step 7：版本化 CSV/JSON 结果导出

导出 TestRun metadata、criteria、metrics、逐点状态、证据 ID、来源和限制说明。默认不覆盖现有文件，字段顺序稳定，JSON 拒绝 NaN/Inf，CSV/JSON 往返由测试验证。

验收：名义、失败、不完整、unsupported 和排除点结果均可导出；来源不会被提升为 `BENCH_*`；坏路径和已存在目标安全失败。

### Step 8：黄金兼容、构建和阶段收口

冻结 Phase 3 公开 API、schema、标准合成输入和 exact result；运行完整 pytest、coverage、Ruff、mypy、依赖、sdist/wheel、仓库外安装和公开 runner smoke；更新 README、状态、追踪矩阵、技术债和 closure report。

验收：所有阶段出口通过后才将 Phase 3 标记为完成。

## 8. 阶段出口条件

- 正式分析代码完全离开 `dashboard/measurements`；
- DC sweep 与迟滞结果逐点可解释、可追溯；
- 饱和和质量排除不删除原始数据；
- acquisition 状态与 TestRun outcome 的映射有自动测试；
- PASS/FAIL 必须来自完整数据、版本化 criteria 和证据 ID；
- read-only、越界、异常和用户中止路径不产生未授权输出；
- 校准不修改原始记录；
- 频率响应明确为离线分析；
- CSV/JSON 输出稳定、可验证且保留来源；
- 核心继续不依赖串口、GUI、板级 SDK 或真实硬件；
- 阶段报告明确 `VERIFIED_BENCH = 0`。

## 9. 本阶段明确不做

- 不安装或使用 pyserial；
- 不扫描 COM 端口；
- 不连接或刷写 MSP430、STM32、RP2040；
- 不控制真实 DAC、PWM、信号源或示波器；
- 不构建最终 CLI 或 Dashboard；
- 不进行 FFT 或实时频响采集；
- 不采购、接线、焊接或上电 AFE；
- 不把 synthetic/replay 结果称为硬件精度、带宽或安全验证。

## 10. 规划批准门

本文件完成的是“准备如何实现”的工程设计，不是 Phase 3 功能本身。实施从 Step 1 开始，并保持一次只推进一个可验证检查点。每一步都必须提交代码、测试、文档、真实命令结果和证据限制，用户继续下一步后再进入后续检查点。
