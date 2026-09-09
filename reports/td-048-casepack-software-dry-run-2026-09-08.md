# TD-048 案例包与软件预演 — 2026-09-08

状态：受控软件案例已核验；人工基线试做、效率与收益结论 NOT_RUN。
范围：重复 DC 数据验证；无运行时/UI/API 变更，无硬件操作，无外部发布。

## 目的与产物

将已接受的 [任务收益协议](../docs/TASK_VALUE_VALIDATION_PLAN.md) 落实为
5 个预先冻结的 SYNTHETIC 普通 CSV 案例、严格 CSV_REPLAY 输入、
独立有理数参考、两条操作路径说明和空白人工记录表。
独立参考不调用 AVS 分析/evaluator/报告代码。

本地案例目录：
`C:/Users/24046/Documents/Codex/2026-09-07/files-mentioned-by-the-user-agent/outputs/td048-dc-casepack-20260908-01`。
README.md 是操作入口；reference.json 与输入哈希在 cases 内。
正式产品代码仍位于 calibration-workflow 工作树。
这些外部案例产物没有被自动复制进产品运行时或历史产物目录。

## 冻结条件与实际结果

每例 9 对输入/输出，输入 90–810 mV，步长 90 mV。
输出 <=25 或 >=1800 mV 排除；最少 3 点；
增益 2 ±0.05（绝对容差），|偏置| <=25 mV，R² >=0.999，RMSE <=1 mV。
数值核对绝对容差 1e-9；标识、状态、点数精确一致。

| 案例 | 独立预期与 AVS 实际 | CLI 退出码 |
|---|---|---|
| A：y=2x+10 | 9 点；gain 2，offset 10 mV；PASS | 0 |
| B：y=2x+40 | 9 点；gain 2，offset 40 mV；FAIL，偏置超限 | 1 |
| C：p08 缺失，p09=1800 | p08 INVALID，p09 饱和排除；7 点；gain 2，offset 10 mV；PASS | 0 |
| D：p03–p09=1800 | 2 点；INCOMPLETE；没有拟合结果 | 3 |
| E：mVolt | 转换器拒绝；另行非法单位解析探针被 AVS 拒绝；没有结果产物 | 5 |

A/B/C 的 R²=1、RMSE=0、最大绝对残差=0，与独立参考一致。
A–D 均生成结果和 text/Markdown/HTML/SVG 报告，逐项核验报告哈希、大小、
证据类型、结论和点处理理由。B/D 的 report 返回 1/3，表示原工程结论，
不能据此误判报告没有生成。

三次单预设项目运行 A、B、B 使用相同 project/preset ID：
A→B 显示 offset +30 mV、PASS→FAIL，并显式标记输入路径造成的项目变化；
B→B 指标/结论无变化，项目配置无变化。
history 验证三份 manifest；重复指定已有输出目录返回 OUTPUT_EXISTS/5，
拒绝前后全部已发布文件哈希一致。此处单预设运行检查历史链，
不另称多预设压力/取消验收。

正常结果 JSON 在 stdout，进度在 stderr；启动/发布阶段错误 JSON
沿用既有 stderr 约定（例如 OUTPUT_EXISTS，stdout 为空）。
操作指南明确要求保留退出码与两个流；没有改变既有 CLI 契约。

## 检查结果与失败记录

首次组合检查：5 failed, 253 passed。4 项是新核验脚本未处理 Markdown
下划线转义，1 项错误地从 stdout 读取 stderr 错误 JSON。
查阅代码、既有测试和 CLI 文档后修正核验断言，没有修改产品实现。
修正时发生一次脚本缩进导致的 collection error，随后修复。

最终针对性检查：**258 passed in 2.02s**，
其中外部案例核验 12 项、既有 DC/criteria/project/CLI/文档测试 246 项。
完整输出在 targeted-tests-final.txt；失败过程在 verification-history.md。

命令：项目 .venv Python -m pytest <案例目录>/test_evidence.py
tests/unit/test_dc_sweep_analysis.py tests/unit/test_dc_sweep_criteria.py
tests/unit/test_product_projects.py tests/unit/test_product_projects_cli.py
tests/architecture/test_tester_documentation.py -q，缓存写入新案例目录。

人工 XLSX 的 48 行时间为空，状态 NOT_RUN；已做生成器检查、渲染和导出 XML
核验，未在原生 Excel 中交互验收。Excel 基线路径与实际人工时间仍待试做。
本轮没有重新运行完整 pytest/100% coverage/Ruff/mypy/pip check：
产品源代码、依赖和仓库测试未改，不能把旧 TD-046B 门禁数字称作本轮结果。
文档变更后另行复核：文档测试 5 passed in 0.03s；git diff --check 通过。

本轮仓库实际修改：docs/PROJECT_STATUS.md、docs/REQUIREMENTS_TRACEABILITY.md、
docs/TASK_VALUE_VALIDATION_PLAN.md、docs/TECHNICAL_DEBT.md、reports/README.md；
新增本报告。开始时 462 个既有受 Git 跟踪或未忽略文件中，
上述 5 份文档更新，其余 457 份哈希完全不变，无旧文件丢失。
当前 50 个已修改跟踪文件、34 个未跟踪文件，共 84 个；暂存 0。
分支 codex/calibration-workflow、HEAD bf8c4c6f59ba9063524aea7db01df87d35170483
未变。所有先前未提交成果保持原样；无提交、推送或发布。

## 对路线的影响

SW-VAL-001 推进到 IMPLEMENTED：案例、参考、映射、共同交付清单和初版
Excel/AVS 路径已准备，Excel 基线还需真人试做，不能标为完整 VERIFIED_HOST。
SW-VAL-002/003 保持 ACCEPTED，TD-048 P1 保持打开。
未新增产品缺陷或另立细碎技术债；后续在同一 TD-048 记录实际阻塞。

下一小阶段是实际操作者熟悉两条路径并完成一次配对试做；
正式三组计时前再冻结等难度变体与交替顺序，避免记住答案带来的学习偏差。
允许使用已有模板/脚本，记录首次准备与转换、配置、报告、恢复和复核成本。
不把机器耗时、覆盖率或注入异常检出称为人类效率或错误率改进。

本轮只证明受控案例的软件一致性，不证明生产收益、真实仪器兼容、
有噪声/非线性数据的一般精度，或任何硬件测量性能。
SYNTHETIC、CSV_REPLAY、HOST_TEST、SPICE_IDEAL、BENCH_CONTROLLER、BENCH
的边界保持不变。
