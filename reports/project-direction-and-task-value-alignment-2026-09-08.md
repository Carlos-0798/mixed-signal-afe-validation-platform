# 项目方向与任务收益规划调整记录

日期：2026-09-08<br>
状态：规划调整完成；TD-048 实际任务收益验证尚未完成<br>
验证范围：本地主机文档检查，不新增算法、GUI、设备或硬件验证证据

## 调整原因与结论

用户明确以可展示、可解释、可复查的工程价值为主要目标，不以商业化为主。
现有分析、质量检查、预设/批次、取消、结果与报告能力支持这一方向；
需要修正的是任务收益缺少人工基线、软件与未来硬件定位混杂，以及部分宽泛能力表述。

已将首个任务收紧为：对已有模拟信号链数据重复进行 DC 增益、偏置与线性验证，
记录异常处理、验收条件、结果及两次运行比较，并完成可读报告交接。
收益必须由同任务对照支持，不以测试数、覆盖率或机器解析速度替代。

## 已落实的规划变化

- PRODUCT_PLAN 更新为 v1.3，主任务、当前优先级和 UC-008 明确；
- 架构入口以独立软件为中心，保留第 1–8 节未来 AFE 路线并限定其适用范围；
- 原始数据引用与完整归档分开，批次结果发布与人类报告生成分开；
- 新增任务收益协议，记录首次成本、格式转换、人工介入、等待、恢复及交付检查；
- 新增 SW-VAL-001–003，均为 ACCEPTED，实际测试未冒充已完成；
- 新增 TD-048 P1；TD-040C 保留汇总并拆成数据归档、曲线叠加、签名三项；
- TD-047A 后续显示层建议暂不排期，运行时迁移继续暂缓；
- Phase 6 的 7/8 发布治理状态保留，与当前工程价值验收分开。

任务协议要求独立参考答案、公平的 Excel/既有脚本基线和真实操作者记录；
失败、无收益及作者自测限制必须保留。软件预演可以先行，但不能替代人工计时。
当前没有制作或执行该协议的案例包，不存在新的效率百分比、人工错误率或现场结论。

## 本次修改范围

修改九份现有文档：

- README.md
- docs/PRODUCT_PLAN.md
- docs/PRODUCT_ARCHITECTURE.md
- docs/PROJECT_STATUS.md
- docs/REQUIREMENTS_TRACEABILITY.md
- docs/TECHNICAL_DEBT.md
- docs/USER_TESTING_GUIDE.md
- docs/SOFTWARE_PHASE_6_PLAN.md
- reports/README.md

新增两份文档：

- docs/TASK_VALUE_VALIDATION_PLAN.md
- 本记录

不修改运行时代码、测试代码、公共 API、golden、历史报告、原始
DEVELOPMENT_SPEC、manifest 或既有测试产物。

## 验证记录

- 开始前确认分支 codex/calibration-workflow、HEAD
  bf8c4c6f59ba9063524aea7db01df87d35170483、Python 导入位置和 79 个未提交文件；
- 记录 460 个现有 Git tracked/untracked 文件的 SHA-256，用于本阶段范围核对；
- 文档相关既有测试：5 passed in 0.03 s；
- 九份规划/入口文档的 UTF-8、78 个本地链接和需求统计检查通过；
- 既有功能/非功能需求实际为 62 项：47 VERIFIED_HOST、2 VERIFIED_BENCH、
  1 PARTIAL_HOST、12 DEFERRED；修正原汇总漏计的 PARTIAL_HOST；
- 新的三项任务收益要求单列，合计 65 项；没有增加已验证功能数量；
- git diff --check 通过。

最终哈希核对：仅上述九份现有文档变化，新增两份文档；其余 451 个基线文件
字节不变，无删除。运行时代码、测试、golden、原始规格与历史报告均保持原哈希。
最终 Git 为 50 个已修改、33 个未跟踪，共 83 个未提交文件，暂存 0；
分支与 HEAD 未改变。

首次文档测试通过，无测试失败修复；需求数量修正来自审查发现。
本轮仅改文档，不重复执行完整 pytest/coverage、Ruff/mypy、GUI 或包构建。
TD-046B 的 2,696 项测试与 100% statement coverage 仍是上一实现阶段的
历史记录，不声称是本轮新执行结果。

## 下一步及保留边界

下一实施阶段是 TD-048 案例与独立参考准备，再开展实际操作者对照；
只有测得具体阻塞后才安排最小实现和复测。TD-048 继续未关闭。

证据标签 SYNTHETIC、CSV_REPLAY、HOST_TEST、SPICE_IDEAL、BENCH_CONTROLLER
和 BENCH 不变；没有新增硬件验证。未提交、推送、修改 PR、发布、改许可证、
改可见性、重写历史、reset、checkout、clean、删除旧产物或访问硬件。
