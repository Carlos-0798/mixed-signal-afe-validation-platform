# 本地测试优先，云端仅手动触发

**所有者决定：** 2026-09-09。日常开发、上传代码和求职展示以本地验证为主。
GitHub Actions 仅用于明确选择的云端复验，不因普通 push 或 PR 更新自动运行。

## 日常本地验证

在正确工作树、使用其独立虚拟环境运行。先核对导入路径，再按实际改动执行有意义的测试：

```powershell
.venv\Scripts\python.exe -c "import analog_validation_app; print(analog_validation_app.__file__)"
.venv\Scripts\python.exe -m pytest -q --cov=analog_validation --cov=analog_validation_app --cov=analog_validation_pyserial --cov-report=term-missing --cov-fail-under=100
.venv\Scripts\python.exe -m ruff check src tools tests examples/public_adapter
.venv\Scripts\python.exe -m mypy src tools tests examples/public_adapter
.venv\Scripts\python.exe -m pip check
git diff --check
```

业务代码变动应完成相关回归及完整质量门禁。纯文档或 CI 启动方式调整，运行对应的
架构/配置检查即可，不为相同运行代码重复完整软件验收。新证据应注明实际命令、提交、
主机环境和结果；不能把未重跑的旧数字称为当前提交的新结果。

本地测试不向 GitHub 请求 runner。软件的数据导入、分析、绘图和报告仍在本地完成。

## 云端复验的选择

`.github/workflows/ci.yml` 的事件入口仅保留 `workflow_dispatch`。
八项既有测试任务、操作系统/Python 矩阵、覆盖门槛、只读权限和受限产物保留规则不变。
没有降低测试要求，只把“何时使用 GitHub 计算资源”交给所有者。

确有跨平台或干净环境验证需要时，先确认账户可用额度和待测分支/提交，再到 GitHub
**Actions → CI → Run workflow**，选择要验证的分支后手动启动。
这仍可能使用 Actions 额度；“手动”不等于无限免费。手动触发的使用说明见
[GitHub 官方文档](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)。

后续维护者及自动化工具不得因 push、PR 更新、账户限制解除或旧失败记录而自动 dispatch/re-run；
需要所有者针对该次云端运行的明确指示。本地命令与只读查询 Actions 状态不受此限制。
不擅自添加定时、push、PR 或其他自动触发入口，不更改账单、付费计划或消费额度。

## 分支与证据边界

默认 `main` 沿用仅 `workflow_dispatch` 的 CI 配置；PR #10 的产品功能已合并。
其它历史分支保留其原始记录。如果将来从历史分支恢复工作，先带入并核对
当前策略，不能直接推送旧的自动触发配置。

原同步 run `34425224783` 因账户限制而未启动任何测试，是保留的历史记录。
本策略实施后，云端复验是显式选择的附加证据，不是日常代码同步或求职展示的前提。
未执行的云端矩阵记为 NOT_RUN，不写成 PASS；本地测试不冒充原生 Linux 或硬件证明。

所有者批准的 PR #10 合并、源码公开和匿名克隆/安装/示例验证已于 2026-09-10 完成。
本次公开未触发云端测试，核对时 Actions 仍为原有 41 次运行。
后续 PR、tag、Release、包发布、许可证/历史变更、社交发布及硬件操作
仍按各自授权边界执行。
