# 开发环境

**最近验证：** 2026-09-01<br>
**代码基线：** `95cd471`（PR #6 manifest 完整性修复）<br>
**硬件要求：** 完整软件质量门禁不需要 AFE、MSP430 或实验室仪器

## 当前已就绪

| 组件 | 本机状态 | 项目中的角色 |
|---|---|---|
| Python | 3.12.10，64-bit，python.org | 推荐的本地开发和发布验证解释器 |
| 项目虚拟环境 | `C:\avs-dev\afe-validation-py312` | 短路径，避免 Windows `WinError 206` |
| Python 工具 | pip 26.2.1、setuptools 84.0.0、wheel 0.48.0、build 1.6.0 | 安装与构建 |
| 质量工具 | pytest 8.4.2、pytest-cov 7.1.0、Ruff 0.16.5、mypy 2.3.1 | 测试、覆盖率、lint 和类型检查 |
| 可选串口 | pyserial 3.5 | 仅用于经过单独批准的真实端口工作 |
| 可选桌面 | Tk/Tcl 8.6 | 本地 Dashboard；CLI 不依赖显示器 |
| Git / GitHub CLI | Git 2.55.0、GitHub CLI 2.98.0 | 本地版本控制和明确授权后的远程操作 |
| VS Code | 1.135.0 | Python、Pylance、Ruff 扩展均已安装 |
| LTspice | 26.0.1 | 可选 `SPICE_IDEAL`/器件模型仿真，不构成硬件证据 |
| MSP430 GCC | 9.3.1 | 独立控制器工具链；本软件核心不依赖 |

LTspice 和 MSP430 GCC 可从已知安装位置调用，但没有写入全局 `PATH`。这避免不同
项目或未来工具链版本互相覆盖。Code Composer Studio 和 UniFlash 当前未检测到；软件
Beta、模拟器、回放、报告、Dashboard 和 hosted CI 均不需要它们。

本机只安装 Python 3.12。Python 3.10 和 3.14 由 GitHub hosted CI 在 Windows/Ubuntu
上覆盖，不要求初学者为了日常开发额外安装两套解释器。

## 一次性建立短路径环境

在最新、干净的项目工作树根目录打开 PowerShell：

```powershell
$DevRoot = "C:\avs-dev"
$Venv = Join-Path $DevRoot "afe-validation-py312"

New-Item -ItemType Directory -Path $DevRoot -Force | Out-Null
py -3.12 -m venv $Venv
& "$Venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
& "$Venv\Scripts\python.exe" -m pip install -e ".[dev,serial]"
& "$Venv\Scripts\python.exe" -m pip check
```

为了让 VS Code 继续使用通用的 `${workspaceFolder}\.venv` 设置，可在确认 `.venv`
不存在后建立目录联接：

```powershell
New-Item -ItemType Junction -Path ".venv" -Target $Venv
```

不要删除或覆盖一个已有但来源不明的 `.venv`。先检查其解释器和安装目标，或为本次
工作选择新的短路径。无需激活虚拟环境，也不需要改变 PowerShell execution policy。

一个 editable install 只应对应一个活动 Git worktree。多个 worktree 共用同一虚拟
环境时，`.pth`/editable metadata 可能仍指向先前的源码目录，从而“测试当前分支却
导入旧代码”。正式门禁前应为当前 worktree 建立独立环境，或至少执行：

~~~powershell
.\.venv\Scripts\python.exe -c "import analog_validation_app; print(analog_validation_app.__file__)"
~~~

输出路径必须位于当前 worktree。临时设置 `PYTHONPATH=<当前工作树>\src` 只适合
定位问题；发布证据仍应使用隔离构建和 fresh install。

Windows 还可能在很深的仓库、工作树和虚拟环境组合下触发传统路径长度限制。若
`pip` 报错并提示 `Windows Long Path support`，不要把它误判为 wheel 损坏，也不要
覆盖现有环境。应在明确的新短路径（例如 `C:\avs-gates\<candidate>`）创建隔离
虚拟环境，再重复相同的 wheel 安装和验证；或者由用户/管理员单独决定是否启用
系统长路径策略。短路径重试的结果和原始失败原因都应记录。

## 无硬件环境自检

仓库提供一个标准库实现的开发环境审计入口：

```powershell
.\.venv\Scripts\python.exe -m tools.dev_environment_audit
.\.venv\Scripts\python.exe -m tools.dev_environment_audit --json
```

审计区分必需项和可选项，并检测：

- 当前 Python 是否满足项目要求及 hosted matrix 状态；
- 项目包、pytest、coverage、Ruff、mypy、build 和 `pip check`；
- 可选 pyserial、Tk、GitHub CLI、VS Code、LTspice 和 MSP430 GCC；
- VS Code 的 Python、Pylance 和 Ruff 推荐扩展。

它不会访问网络、枚举或打开串口、发送设备字节、读取 USB 序列号，也不会形成任何
硬件验证结论。输出不包含解释器、工具或用户目录的绝对路径。

## 日常质量门禁

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  --cov=analog_validation `
  --cov=analog_validation_app `
  --cov=analog_validation_pyserial `
  --cov-report=term-missing `
  --cov-fail-under=100
.\.venv\Scripts\python.exe -m ruff check src tools tests examples/public_adapter
.\.venv\Scripts\python.exe -m mypy src tools tests examples/public_adapter
.\.venv\Scripts\python.exe -m pip check
```

发布候选门禁还会完成两次隔离构建、sdist/wheel 内容检查、fresh base/`[serial]`
安装、普通/Unicode demo 和 manifest/audit：

```powershell
.\.venv\Scripts\python.exe tools\release_candidate_check.py `
  --output C:\avs-dev\candidate-new
```

目标目录必须不存在；工具使用 create-new 语义，不覆盖旧证据。

## 已记录的 `95cd471` 基线

在 `95cd471` 上重建短路径环境后：

- 开发环境审计：22 PASS、0 WARN、0 FAIL；
- 完整 pytest：2,252 passed；
- package coverage：11,470/11,470 statements，100%；
- Ruff：PASS；
- mypy：204 files，PASS；
- `pip check`：PASS；
- 四个 LTspice 理想网表：进程退出码均为 0，结果与既有 `SPICE_IDEAL` 记录一致。

## 最新本地分支快照

2026-09-03 的 Dashboard UX 功能门禁在未访问串口或 MSP430 的条件下完成：

- 完整 pytest：2,275 passed；
- package coverage：11,911/11,911 statements，100%；
- Ruff：PASS；
- mypy：204 files，PASS；
- build、fresh base 和 `[serial]` 安装：PASS；
- Windows Simulator/CSV 交互、滚动、保存路径、结果导航、首帧和焦点检查：PASS。

随后加入的 README、截图、当前状态同步和治理文件属于展示/发布准备，
仍需在最终精确提交上重跑完整门禁；不能把此前功能门禁的数字当成对尚未提交
候选的 hosted CI 证明。

## 环境与证据边界

- 可发现 COM4/COM5 只说明 Windows 驱动呈现了端口，不说明固件、协议或接线正确；
- 安装 pyserial 不等于批准打开物理端口；打开端口仍可能影响 RTS/DTR；
- LTspice 理想网表不是 MCP6004/MCP6544 器件模型，更不是台架测量；
- MSP430 GCC 存在不等于目标固件已经构建、烧录或验证；
- CCS/UniFlash、Python 3.10/3.14、本地多机 HIL、VISA 后端和实验室仪器均不是当前
  软件交付的隐藏依赖；
- 不需要额外 Codex 插件才能开发或测试本项目。

开源框架和未来仪器插件边界见
[Open-source reference review](OPEN_SOURCE_REFERENCE_REVIEW.md)。
