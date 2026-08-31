# 开发环境

**验证日期：** 2026-08-30<br>
**当前阶段：** Software Phase 4 进行中（6/8）<br>
**硬件要求：** 已完成 Steps 1–6 无；Step 7 仅在单独确认后可选使用已连接 MSP430

## 已验证环境

- Windows 11 Home 64-bit，build 26200；
- Python 3.12.10 64-bit，来自 python.org 独立安装；
- Git for Windows 2.55.0；
- Visual Studio Code 1.135.0；
- LTspice 26.0.1（未来模拟电路仿真使用，当前 Software Phase 4 不依赖）；
- 项目虚拟环境：`.venv`；
- pytest 8.4.2；
- Ruff 0.16.5；
- mypy 2.3.1；
- build 1.6.0。

VS Code 已推荐并安装 Python、Pylance 和 Ruff 扩展。工作区设置会自动选择 `.venv` 并启用 pytest 测试发现。

## 首次建立环境

在仓库根目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

不要求激活虚拟环境；直接调用 `.venv` 中的 Python 可以避免 PowerShell 执行策略问题。

## 日常验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest --cov=analog_validation --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src dashboard tools tests
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m build
```

pytest、formal-package coverage、全仓库 Ruff、mypy、依赖检查、构建和仓库外 wheel 安装是当前质量门禁。Software Phase 3 已完成正式记录追溯、质量 policy、DC sweep 与方向性迟滞数学、版本化 criteria/TestRun 映射、安全门控 runners、不可变线性校准、离线幅值频响分析，以及严格 `result-export.v1` JSON/CSV。Phase 4 Steps 1–6 已增加 profile-neutral bounded stream、modular sequence tracker、token/CRC envelope、AFE compatibility wrapper、显式 channel mapping、driver-neutral serial lifecycle、bounded memory-only raw events、通用 serial-profile port、独立 AFE/MSP430 profiles，以及 receive-only `SerialAdapter` 对共用 adapter/workflow 的组合；当前完整门禁为 1,472 tests、7,198/7,198 正式 package statements、全仓库 Ruff、140-file mypy、依赖检查、sdist/wheel 和仓库外无 pyserial 的 installed SerialAdapter→ReadWorkflow smoke（`HOST_TEST`、25.3 °C、1 raw event、0 writes）。它们仍是 HOST_TEST 证据。旧 `dashboard/reporting/csv_export.py` 仅为指向正式 package 的 legacy placeholder。

## 当前边界

- 当前正式核心仍不安装 `pyserial`；receive-only `SerialAdapter` 已完成，但可选 serial dependency、具体 OS backend 与 owning worker 尚未实现；
- 不需要 CCS、MSP430 GCC、KiCad 或实验室仪器；
- 软件测试结果不代表任何模拟电路、控制器、接线或仪器已经验证；
- Git 提交身份已配置为 GitHub 账号 `Carlos-0798` 及其 noreply 邮箱。

## 本机备份

重建独立环境前的 Codex 运行时虚拟环境已移动到 `.venv-codex-backup-20260829`。新环境验证稳定后可以再决定是否移除；当前不删除该备份。
