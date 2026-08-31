# 开发环境

**验证日期：** 2026-08-31<br>
**当前阶段：** Software Phase 4 已完成（8/8）<br>
**硬件要求：** 默认软件门禁无需硬件；Step 7 已单独完成一次 MSP430 receive-only HIL

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
- 可选 pyserial 3.5（只在安装 `[serial]` extra 后使用）。

VS Code 已推荐并安装 Python、Pylance 和 Ruff 扩展。工作区设置会自动选择 `.venv` 并启用 pytest 测试发现。

## 首次建立环境

在仓库根目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

不要求激活虚拟环境；直接调用 `.venv` 中的 Python 可以避免 PowerShell 执行策略问题。

只有需要真实串口时才安装可选 extra：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,serial]"
```

## 日常验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest --cov=analog_validation --cov=analog_validation_pyserial --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src dashboard tools tests
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m build
```

pytest、formal-package coverage、全仓库 Ruff、mypy、依赖检查、构建和仓库外 wheel 安装是当前质量门禁。Software Phase 3 已完成正式记录追溯、质量 policy、DC sweep 与方向性迟滞数学、版本化 criteria/TestRun 映射、安全门控 runners、不可变线性校准、离线幅值频响分析，以及严格 `result-export.v1` JSON/CSV。Software Phase 4 已完成 8/8：除 bounded stream、sequence、envelope、channel mapping、serial lifecycle/raw events、独立 profiles、receive-only `SerialAdapter`、可选 pyserial backend 和窄范围 COM4 HIL 外，Step 8 又冻结 121 个 Phase 4 exports、3 个 schemas、12 组 enums/flags、21 个 signatures、17 个 errors、5 个 fixture hashes 及两个 exact external-backend composites。当前完整门禁为 1,526 tests、7,325/7,325 正式+可选 package statements、全仓库 Ruff、148-file mypy、依赖检查、sdist/wheel 和两种仓库外安装。Step 8 未打开端口；Step 7 HIL 仍只证明窄范围 `BENCH_CONTROLLER` UART 兼容，其他结果继续按各自 `HOST_TEST/SYNTHETIC/CSV_REPLAY` 标签。旧 `dashboard/reporting/csv_export.py` 仅为指向正式 package 的 legacy placeholder。

## 当前边界

- 正式核心仍不要求 `pyserial`；可选 backend 已完成，但 owning worker、取消/长时间运行和真实断线恢复尚未实现；
- 不需要 CCS、MSP430 GCC、KiCad 或实验室仪器；
- 软件测试结果不代表任何模拟电路、控制器、接线或仪器已经验证；
- Git 提交身份已配置为 GitHub 账号 `Carlos-0798` 及其 noreply 邮箱。

## 本机备份

重建独立环境前的 Codex 运行时虚拟环境已移动到 `.venv-codex-backup-20260829`。新环境验证稳定后可以再决定是否移除；当前不删除该备份。
