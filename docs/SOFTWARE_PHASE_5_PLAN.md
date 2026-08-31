# Software Phase 5 文件级实施计划

**阶段名称：** 产品工作流、CLI、Dashboard 与证据可见报告<br>
**规划状态：** 已完成；实现进度 0/8<br>
**预计时间：** 5–8 个有效开发日；初学者兼职约 2–3 周<br>
**前置：** Software Phase 1–4 的领域、分析、runner、导出、transport、profile 和 adapter 兼容基线完成<br>
**默认硬件要求：** 无<br>
**AFE 硬件验证：** 0

## 当前进度

- [ ] Step 1：产品层契约、catalog、错误映射与 CLI 骨架；
- [ ] Step 2：owning/cancellable job worker；
- [ ] Step 3：稳定 CLI 工作流；
- [ ] Step 4：证据可见的人类报告与确定性图表；
- [ ] Step 5：Dashboard 状态模型、presenter 与桌面外壳；
- [ ] Step 6：初学者向导、worker 接线与只读串口入口；
- [ ] Step 7：可复现演示、性能/可访问性/隐私验收；
- [ ] Step 8：公共兼容性冻结、构建、外部安装和阶段收口。

本规划检查点只定义边界、文件和验收标准。它没有新增 CLI、worker、
Dashboard、报告或硬件行为，也没有打开串口。完成规划不等于 Phase 5 功能完成。

## 1. 初学者先理解这一阶段解决什么

Software Phase 1–4 已经解决“数据怎样表示、怎样验证、怎样分析、怎样通过不同
设备来源进入同一核心”。但普通用户目前仍需要自己写 Python 才能组合这些能力。
Phase 5 要解决的是产品使用问题：

1. 用户怎样选择 Simulator、CSV Replay 或明确的只读串口 profile；
2. 一个长任务怎样启动、显示进度、取消，并且一定释放 adapter/串口；
3. 用户怎样从终端或 Dashboard 运行同一套应用服务；
4. PASS、FAIL、INCOMPLETE、来源和限制怎样被普通人看懂；
5. 怎样用一个完全可复现、无需硬件的流程展示产品。

核心原则是“界面不拥有工程真相”。CLI 和 Dashboard 只负责收集用户意图、调用
应用服务并显示结果；CRC、profile 字段、Measurement、分析公式、PASS/FAIL 和
导出 schema 继续只由 `analog_validation` 核心拥有。

## 2. 阶段范围

### 2.1 本阶段必须完成

- 一个安装后可运行的 `analog-validation` 命令；
- profile/source catalog、Simulator、CSV Replay 和显式只读串口入口；
- 只允许一个 owner 管理一个 job 的可取消 worker；
- 终端与 Dashboard 共用的 product request/result/event 模型；
- DC、迟滞和读取结果的证据可见摘要；
- 自包含 HTML 报告和确定性 SVG 图表；
- 本地 Windows `Tkinter/ttk` Dashboard；
- 初学者向导、错误解释和安全下一步；
- 至少一个无需硬件的确定性端到端 demo；
- 公共接口、CLI 行为、报告 schema 和 demo 结果的黄金兼容冻结。

### 2.2 明确不属于本阶段

- 不实现真实 AFE 输出 adapter、DAC、PWM 或任意串口写命令；
- 不主动 flash MSP430，不修改 FRAM，不控制风扇；
- 不建立云服务、账号、遥测上传、数据库或远程 API；
- 不声称实时操作系统级 deadline；
- 不把校准/频响的纯分析对象临时伪装成完整 TestRun；
- 不生成 PDF；HTML/JSON/CSV 是 Phase 5 的可验证交付格式；
- 不完成 v1.0 发布、CI 或跨平台 release matrix，它们属于 Phase 6；
- 不进行或推断任何 AFE 实物性能验证。

## 3. 目标架构和依赖方向

```text
Tkinter Dashboard        analog-validation CLI
         |                        |
         +-----------+------------+
                     v
          analog_validation_app
        request / catalog / service
        worker / issue / view model
                     |
          +----------+-----------+
          |                      |
          v                      v
 analog_validation        analog_validation_pyserial
 frozen core APIs          optional receive-only backend
          |
          v
 Simulator / CSV Replay / explicit SerialAdapter
```

依赖方向只能向下：

- `analog_validation` 不得导入产品层、Tk、pyserial、GUI 或 tools；
- `analog_validation_pyserial` 继续只实现底层 backend，不导入产品工作流；
- `analog_validation_app` 可以组合两个下层包，但不能复制 profile、CRC、分析或
  PASS/FAIL 逻辑；
- Dashboard widgets 不直接创建 adapter、打开 COM、读取文件或计算分析结果；
- CLI 和 Dashboard 必须通过同一 application service 和 worker；
- 未来 Web/Qt UI 可以替换 Tk 界面而不改变核心或产品 request/result contract。

## 4. 已冻结的规划决策

### 4.1 新建独立产品层包

正式核心保持在 `src/analog_validation/`。Phase 5 新增
`src/analog_validation_app/`，承担用户入口和应用编排。Phase 0 的根目录
`dashboard/` 只是未发布占位和旧分析迁移对照；Step 1 会在已有正式分析回归确认后
删除这些占位及其 legacy-only tests，不把旧实现复制到新产品层。

### 4.2 只有一个命令入口

`pyproject.toml` 计划新增：

```toml
[project.scripts]
analog-validation = "analog_validation_app.cli:main"
```

Dashboard 通过 `analog-validation dashboard` 启动，而不是维护第二套参数解析和
service wiring。CLI 的人类输出写 stdout/stderr；`--json` 使用版本化机器结果，
默认不显示 Python traceback，显式 `--debug` 才显示开发信息。

### 4.3 Dashboard 采用本地 Tkinter/ttk

第一目标平台是 Windows 11。Tkinter 属于 Python 标准库、默认离线、不启动本地
HTTP server，也不引入云端或前端构建链。`tkinter` 只能在 Dashboard 入口延迟
导入，不能让基础 CLI、核心或无界面测试依赖显示器。

规划时已确认当前项目虚拟环境可导入 Tk/Tcl 8.6；尚未创建窗口，因此这不是 UI
运行通过的证据。Step 5/6 必须把 widget 之外的 state/presenter 全部做成 headless
可测试代码，实际 Windows 窗口 smoke 另行记录。

### 4.4 worker 拥有资源，界面只拥有意图

每个 worker 同一时间最多运行一个 job。job 创建 adapter 后独占它，负责连接、
执行、取消检查、安全清理和终态发布。CLI/Dashboard 不能保留可被另一线程直接调用
的 adapter 或 serial session。

取消是协作式而不是强制杀线程：每次有界 read、settle 或步骤之间检查 cancellation
token；底层 I/O 必须有 timeout；结束后执行既有 runner/workflow cleanup。若 cleanup
失败，不能把结果显示成 PASS。

### 4.5 默认模式永远是 Simulator

- 不提供自动选择 COM 或根据 VID/PID 猜 profile；
- CSV Replay 必须显式选择文件和 channel mapping；
- Serial 必须显式选择 port、profile、只读确认和有限记录/时间边界；
- 产品层不提供 arbitrary command、write、terminal 或 raw escape hatch；
- Phase 5 的默认 demo 不执行自动输出：它通过只读 Simulator/ReadWorkflow 取得
  确定性合成输入、输出和状态记录，再调用正式离线分析/criteria/export；
- `run_dc_sweep`/hysteresis output runners 对现有只读 Simulator、Replay 和 MSP430
  继续返回 `UNSUPPORTED`，不能为了演示引入 test-only output adapter；
- MSP430 v1 继续是 receive-only peer profile。

### 4.6 报告只呈现既有结论

人类报告和图表从 `ResultExportBundle` 或明确的 product result view 构建，不重新拟合、
重算 threshold 或改变 TestRun outcome。报告必须显示 EvidenceSource、软件/schema
版本、输入标识、限制、未验证项和生成时间。原始串口 bytes 默认不嵌入报告，只保留
有界摘要/哈希；显式导出也必须经过隐私提示。

## 5. 目标文件结构

```text
src/
├── analog_validation/                 frozen engineering core
├── analog_validation_pyserial/        optional receive-only OS backend
└── analog_validation_app/
    ├── __init__.py
    ├── __main__.py
    ├── py.typed
    ├── catalog.py                     source/profile/job descriptors
    ├── errors.py                      product-layer expected failures
    ├── issues.py                      user-facing what/why/next-step mapping
    ├── models.py                      immutable product request/result/event
    ├── factories.py                   explicit adapter/profile construction
    ├── services.py                    core workflow/report orchestration
    ├── worker.py                      single-owner cancellable worker
    ├── cli.py                         one stable command entrypoint
    ├── reports/
    │   ├── __init__.py
    │   ├── models.py                  presentation-only report view models
    │   ├── summary.py                 human-readable text/Markdown
    │   ├── charts.py                  deterministic chart series + SVG
    │   └── html.py                    self-contained local HTML
    └── dashboard/
        ├── __init__.py
        ├── state.py                   immutable UI state and actions
        ├── presenter.py               product event -> UI state
        ├── widgets.py                 ttk rendering only
        └── app.py                     Tk lifecycle and main-thread polling

tests/
├── unit/
│   ├── test_product_catalog.py
│   ├── test_product_models.py
│   ├── test_product_issues.py
│   ├── test_product_factories.py
│   ├── test_product_services.py
│   ├── test_product_worker.py
│   ├── test_product_cli.py
│   ├── test_human_reports.py
│   ├── test_report_charts.py
│   ├── test_dashboard_state.py
│   └── test_dashboard_presenter.py
├── integration/
│   ├── test_phase5_simulator_product_chain.py
│   ├── test_phase5_replay_product_chain.py
│   ├── test_phase5_serial_read_only_product_chain.py
│   ├── test_phase5_cli_installed.py
│   └── test_phase5_dashboard_controller.py
├── golden/
│   ├── test_phase5_cli_golden.py
│   ├── test_phase5_report_golden.py
│   ├── test_phase5_demo_golden.py
│   └── test_phase5_public_api_golden.py
└── architecture/
    └── test_product_dependencies.py

test-data/golden/
├── phase5_cli_v1.json
├── phase5_human_report_v1.json
├── phase5_demo_v1.json
└── phase5_public_api.json

examples/software-demo/
├── README.md
├── demo-config.json
└── expected-manifest.json
```

文件可以在实现中按职责继续细分，但不能绕过这里规定的层级。若需要改变公开命令、
schema 或依赖方向，必须先更新本计划和验收测试，而不是在 widget 中临时解决。

## 6. 产品层数据与状态合同

计划新增并版本化以下语义；具体字段在对应 Step 完成时冻结：

| 合同 | 作用 | 最低要求 |
|---|---|---|
| `product-job.v1` | 描述一次用户请求 | job ID、source、profile、test type、bounded options、output policy |
| `product-job-event.v1` | worker 进度 | monotonic index、UTC、state、completed/total、text status、issue |
| `product-result.v1` | CLI/UI 共用终态 | outcome、evidence、artifacts、limitations、error/abort semantics |
| `human-report.v1` | 可阅读报告 | objective、environment、source、result、limits、not-verified、artifact hashes |

计划状态机：

```text
IDLE -> STARTING -> RUNNING -> SUCCEEDED
                    |   |
                    |   +-> FAILED
                    +-----> CANCELLING -> CANCELLED
```

所有终态都必须释放资源。`CANCELLED`、`FAILED`、`INCOMPLETE` 和 `UNSUPPORTED`
不能被 presenter 转换成 PASS。进度队列同时有事件数量和消息长度上限；慢 UI 不能让
内存无限增长。

## 7. 八个实施检查点

### Step 1：产品层契约、catalog、错误映射与 CLI 骨架

新增 `analog_validation_app` 包、不可变 product models、受控 source/profile/job
catalog、expected-error 到 `UserIssue` 的映射、`__main__` 和
`analog-validation version/profiles`。删除已经被正式核心取代的根 `dashboard/`
占位和 legacy-only 分析 tests；用架构测试证明没有第二份算法或协议实现。

验收：基础 wheel 无 pyserial、无显示器也能运行 `--help`、`version` 和 `profiles`；
未知命令/配置得到稳定退出码与 what/why/next-step 文本；core public goldens 不变。

### Step 2：owning/cancellable job worker

实现 bounded event queue、single-job ownership、thread lifecycle、cooperative cancel、
join timeout、result/error capture 和 deterministic cleanup。用故障注入 service 覆盖
启动、正常完成、重复启动、取消竞态、worker 异常、cleanup 异常和进程退出。

验收：没有 orphan thread 或 adapter；cancel 不产生 PASS；事件 index 单调且队列
有界；worker 不包含 profile 字段解析、分析公式或 GUI import；不访问真实 COM。

### Step 3：稳定 CLI 工作流

实现 `profiles`、`ports`、`simulate`、`replay`、`observe`、`report`、`demo` 和
`dashboard` 的统一解析。Simulator/Replay 调用既有 read workflow、正式离线
analysis/criteria 和 exports；没有安全输出能力时不调用输出 runner；
`ports` 只发现；`observe` 只允许显式 port/profile 的 bounded receive-only job。

验收：人类输出、`--json` schema、stdout/stderr、退出码、默认不覆盖、Ctrl+C cancel、
无 traceback 默认行为有 subprocess 测试；未安装 serial extra 时给出安装指导；测试
中的 serial 使用内存 backend，不打开物理端口。

### Step 4：证据可见的人类报告与确定性图表

从冻结的 result bundle 建立 presentation-only view model，生成 Markdown/text 摘要、
自包含 UTF-8 HTML 和 SVG。DC 图显示 included/excluded 点、拟合线和文本图例；迟滞图
显示方向、转换区间和阈值。图表不能改变计算结果。

验收：HTML 无远程资源、脚本、上传或网络依赖；报告同时使用文本和视觉状态；
PASS/FAIL、来源、limitations、not verified、版本和 hash 始终可见；输出原子写入且
默认拒绝覆盖；golden 报告确定性通过。

### Step 5：Dashboard 状态模型、presenter 与桌面外壳

实现 headless state/actions/presenter，再实现延迟导入的 Tkinter/ttk widgets。第一版
布局包括 Source、Configuration、Progress、Plot、Result/Evidence 和 Artifacts 六个
区域；所有 UI 更新在 Tk 主线程通过 bounded queue polling 完成。

验收：state/presenter 无 Tk import 并完成单元测试；无显示器环境可导入基础产品包；
窗口关闭触发 cancel/join；状态不用颜色单独表达；Windows 实际窗口 smoke 单独记录，
不得称为硬件验证。

### Step 6：初学者向导、worker 接线与只读串口入口

向导固定为六步：选择来源 → 选择测试 → 配置 → 证据/安全复核 → 运行 → 查看/导出。
Simulator 默认选中。CSV 文件在运行前验证。Serial 页面只有发现、显式 profile、
bounded record/time 和只读确认；不提供发送文本框、command console 或写按钮。

验收：每步提供“我们在做什么、为什么、需要确认什么”；取消/返回不会遗留资源；
CLI 与 Dashboard 对同一请求生成等价 product result；serial host path 证明零 write
surface。若执行真实 controller smoke，必须另获授权并单独报告。

### Step 7：可复现演示、性能/可访问性/隐私验收

提供一个固定 synthetic DC observation demo：只读采集合成 input/output 后执行离线
分析，生成机器 JSON、CSV、人类 HTML、SVG 和 manifest，不声称执行了物理 stimulus；
另提供 replay/fault 示例。建立常见文件规模和 UI event volume 基准，验证 10k 记录
级别的交互目标与有界内存，而不是宣称硬实时。

验收：从干净安装执行一条命令即可在新目录生成完全一致的 demo；artifact hashes、
来源和限制冻结；无网络访问；路径/覆盖/恶意文本/Unicode/大输入有测试；完成键盘
导航、文本状态、缩放和敏感 raw-data 默认排除检查。

### Step 8：公共兼容性冻结、构建与阶段收口

冻结 product public exports、schemas、CLI 命令/退出码、report fields、worker states、
exact demo manifest 和 error/issue families。运行完整 pytest/coverage/Ruff/mypy、
隔离 sdist/wheel、基础/serial 两种外部安装、CLI/demo smoke 和 Windows Dashboard
启动/关闭 smoke，更新 GitHub 展示资料。

验收：Phase 1–4 goldens 不变；外部安装不在仓库路径执行；无 serial extra 的 CLI/
demo/report 正常；安装 serial extra 后只做 discovery/host substitute，除非另行授权；
软件 Beta 与硬件验证声明分开，AFE BENCH claims 仍为 0。

## 8. CLI 和用户体验最低合同

计划命令形状如下，Step 3 才会冻结具体参数：

```text
analog-validation version
analog-validation profiles
analog-validation ports
analog-validation simulate dc ...
analog-validation replay dc --input <file> ...
analog-validation replay hysteresis --input <file> ...
analog-validation observe --port <port> --profile <name> --max-records <n> ...
analog-validation report --input <result-export> --output <directory>
analog-validation demo --output <new-directory>
analog-validation dashboard
```

每个 expected error 都要回答：

1. **发生了什么：** 稳定的错误分类和简短说明；
2. **为什么可能发生：** 配置、能力、格式、设备或资源状态；
3. **安全下一步：** 修正参数、安装可选依赖、检查只读连接或停止操作。

意外 programming error 不能被伪装成用户错误；默认显示事件 ID 和简短停止消息，
`--debug` 才输出 traceback 供开发者诊断。

## 9. Dashboard 最低布局和初学者流程

```text
+------------------------------------------------------------------+
| Source/Profile | Connection | Evidence badge | Job state          |
+----------------+------------------------------+-------------------+
| Guided setup   | Current configuration        | Safe review       |
| 1 Source       | channels / points / file     | read-only/output  |
| 2 Test         | limits / repetitions         | source/limits     |
| 3 Configure    |                              |                   |
+----------------+------------------------------+-------------------+
| Progress text + count/total + Cancel                               |
+------------------------------------------------------------------+
| Plot / point table / quality and exclusion reasons                 |
+------------------------------------------------------------------+
| Outcome + limitations + not verified + exported artifacts          |
+------------------------------------------------------------------+
```

界面必须把 `SYNTHETIC`、`CSV_REPLAY`、`HOST_TEST` 和窄范围
`BENCH_CONTROLLER` 写成文本，不能只用颜色徽章。物理 AFE 尚不存在时，相关页面
显示 “NOT VERIFIED”，不能用 disabled 控件暗示已经验证。

## 10. 安全、隐私和停止条件

- 默认 Simulator，本阶段不存在自动物理输出路径；
- 不按 COM 号、USB 名称或板名猜 profile、固件、安全范围或 wiring；
- 未显式选择 profile、port、bounded duration/records 和只读确认，不打开 serial；
- serial worker/backend 不公开 write 方法；
- 原始帧、用户名、绝对路径和硬件 ID 不进入默认报告或 committed demo；
- 任何文件输出默认 create-new，显式 overwrite 必须可见且可审计；
- Dashboard 不启动网络 listener，不加载远程 JS/CSS/font；
- 配置和文件解析保持严格、有界、不可执行；
- worker 无法在 timeout 内取消、port 被占用、固件/profile 不匹配或 cleanup 失败时停止
  job，并保留结构化 issue；
- 出现未知 physical behavior 时不通过 UI 猜测恢复动作，关闭本项目拥有的资源并报告；
- 本阶段任何真实串口 smoke 都必须与 host regression 分栏，不能推广为 AFE、外设、
  长时间可靠性或电气安全证据。

## 11. 质量与出口门禁

每一步至少运行相应集中测试和完整回归。Phase 5 结束前必须同时满足：

- 所有 Phase 1–4 golden compatibility 继续通过；
- 正式 core 与产品层关键逻辑保持 100% statement coverage 的当前项目门禁；
- Ruff、mypy、依赖一致性通过；
- 架构测试证明 core 不导入 app，widgets 不拥有业务逻辑；
- CLI subprocess、取消、信号、路径、stdout/stderr 和退出码测试通过；
- report/HTML/SVG 无网络依赖、确定性、默认不覆盖；
- worker 的成功/取消/失败/cleanup 竞态和有界队列通过；
- wheel/sdist 包含 entry point、模板/资源和 `py.typed`；
- 仓库外 base install 和 `[serial]` install 分别通过；
- 至少一个安装后 deterministic demo 通过；
- Windows Dashboard 的启动、展示默认 Simulator、关闭/取消 smoke 被真实执行或明确
  标记 `NOT RUN`；
- GitHub README、status、traceability、risk、technical debt 和报告同步；
- AFE 硬件性能 claims 保持 0。

## 12. 主要风险与控制

| 风险 | 控制 |
|---|---|
| UI 复制协议或分析 | application service 只调用冻结 core；架构测试禁止 widget/profile/analysis 交叉依赖 |
| worker 取消后仍占用 COM | bounded I/O、cooperative token、single owner、finally cleanup、join timeout tests |
| GUI 阻塞或跨线程更新 | worker 只发布 immutable events；Tk 主线程轮询 bounded queue |
| FAIL 被显示成程序错误或 PASS | product result 保留 engineering outcome；issue 与 outcome 分离 |
| report 重算并漂移 | 只消费 ResultExportBundle/view model；golden exact output |
| raw evidence 泄露隐私 | 默认摘要/hash、无绝对路径/USB ID、显式 raw opt-in、local only |
| Tk 在其他平台缺失 | dashboard 延迟导入并给出指导；CLI/core/base install 不依赖 Tk window |
| 产品层和未来 EdgeLab 混合 | 本仓库只拥有本地验证工作流；不实现远程 scheduling、leases 或 cloud control plane |
| Phase 5 UI 被误认为硬件证据 | evidence badge、limitations、not-verified 区域和独立 HIL 报告 |

## 13. 阶段性成果和时间预期

| 检查点 | 用户可见成果 | 初学者重点 |
|---:|---|---|
| 1 | 可安装 CLI 骨架和 profiles 列表 | 理解 product layer 与 core 分层 |
| 2 | 可启动/取消且不泄露资源的 job | 理解线程、队列和资源 ownership |
| 3 | 从终端运行模拟、回放和只读观察 | 理解 CLI、退出码和可复现命令 |
| 4 | HTML/SVG 人类报告 | 理解结果、证据和展示分离 |
| 5 | 可启动的 Dashboard 外壳 | 理解 state、presenter、widget 分离 |
| 6 | 六步向导和运行进度 | 理解安全复核和取消路径 |
| 7 | 一条命令的完整 demo | 理解产品验收、性能和隐私检查 |
| 8 | 软件 Beta 兼容冻结 | 理解发布前质量门与 claims 边界 |

完成 Phase 5 后可以称为“软件 Beta”：非开发者能够通过终端或本地 Dashboard 完成
模拟/回放流程并理解报告。但在 Phase 6 的 CI、release candidate、安装矩阵和公开发布
审计完成前，不能称为 v1.0 或 production-ready。

## 14. 下一检查点

规划已完成，Phase 5 实现仍为 0/8。下一次继续时只实施 Step 1：建立
`analog_validation_app` 产品契约、catalog、错误解释和 CLI 骨架，并清理已经由正式
核心替代的 Phase 0 `dashboard/` 占位。Step 1 不实现 worker、报告、Dashboard 窗口，
也不打开任何物理端口。
