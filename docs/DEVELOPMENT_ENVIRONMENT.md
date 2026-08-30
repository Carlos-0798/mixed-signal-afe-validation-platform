# 开发环境

**验证日期：** 2026-08-29  
**当前阶段：** Software Phase 2 进行中（2/8）<br>
**硬件要求：** 无

## 已验证环境

- Windows 11 Home 64-bit，build 26200；
- Python 3.12.10 64-bit，来自 python.org 独立安装；
- Git for Windows 2.55.0；
- Visual Studio Code 1.135.0；
- LTspice 26.0.1（未来仿真使用，当前 Software Phase 2 不依赖）；
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

pytest、formal-package coverage、全仓库 Ruff、mypy、依赖检查、隔离构建和仓库外 wheel 安装是当前质量门禁。旧 `dashboard/measurements/` 分析模块仍将在 Software Phase 3 迁移；它们通过当前静态检查和回归测试，但这不表示其质量、来源和可追溯语义已经达到正式分析核心要求。

## 当前边界

- 不安装 `pyserial`，串口适配器后置到 Software Phase 4；
- 不需要 CCS、MSP430 GCC、KiCad 或实验室仪器；
- 软件测试结果不代表任何模拟电路、控制器、接线或仪器已经验证；
- Git 提交身份已配置为 GitHub 账号 `Carlos-0798` 及其 noreply 邮箱。

## 本机备份

重建独立环境前的 Codex 运行时虚拟环境已移动到 `.venv-codex-backup-20260829`。新环境验证稳定后可以再决定是否移除；当前不删除该备份。
