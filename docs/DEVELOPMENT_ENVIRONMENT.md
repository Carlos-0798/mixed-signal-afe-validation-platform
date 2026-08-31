# 开发环境

**验证日期：** 2026-08-31<br>
**当前阶段：** Software Phase 5 Step 2 已完成（2/8）<br>
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
.\.venv\Scripts\python.exe -m pytest --cov=analog_validation --cov=analog_validation_pyserial --cov=analog_validation_app --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy src tools tests
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m build
```

pytest、三项 package coverage、全仓库 Ruff、mypy、依赖检查、构建和仓库外 wheel 安装是当前质量门禁。Software Phase 3 已完成正式分析、runner 和导出，Software Phase 4 已完成 transport、profiles、receive-only serial adapter、可选 pyserial backend、兼容冻结和窄范围 COM4 HIL。Software Phase 5 Steps 1–2 新增独立 `analog_validation_app` 产品层、不可变 job/result/event contract、受控 catalog、面向用户的 issue 映射、`analog-validation version/profiles` 安装入口，以及 single-owner/cooperative-cancel worker。当前完整门禁为 1,725 tests、8,098/8,098 正式+可选+产品 package statements、全仓库 Ruff、149-file mypy、依赖检查、sdist/wheel 和仓库外无 pyserial 基础安装/内存 worker smoke。

当前 CLI 只提供产品身份和 reviewed profiles，并不执行测量或分析。Step 2 没有创建 Tk 窗口、没有访问串口；下一检查点是 Phase 5 Step 3 稳定 CLI 工作流。

安装后可验证最小产品入口：

```powershell
analog-validation --help
analog-validation version
analog-validation profiles
python -m analog_validation_app profiles
```

## 当前边界

- 正式核心和产品 CLI 骨架仍不要求 `pyserial`；可选 backend 已完成，但 owning worker、取消/长时间运行和真实断线恢复尚未实现；
- 不需要 CCS、MSP430 GCC、KiCad 或实验室仪器；
- 软件测试结果不代表任何模拟电路、控制器、接线或仪器已经验证；
- Git 提交身份已配置为 GitHub 账号 `Carlos-0798` 及其 noreply 邮箱。

## 本机备份

重建独立环境前的 Codex 运行时虚拟环境已移动到 `.venv-codex-backup-20260829`。新环境验证稳定后可以再决定是否移除；当前不删除该备份。
