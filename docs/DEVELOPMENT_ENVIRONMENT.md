# 开发环境

**验证日期：** 2026-08-29  
**当前阶段：** Software Phase 1 准备  
**硬件要求：** 无

## 已验证环境

- Windows 11 Home 64-bit，build 26200；
- Python 3.12.10 64-bit，来自 python.org 独立安装；
- Git for Windows 2.55.0；
- Visual Studio Code 1.135.0；
- LTspice 26.0.1（未来仿真使用，Software Phase 1 不依赖）；
- 项目虚拟环境：`.venv`；
- pytest 8.4.2。

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
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m build
```

Ruff 和 mypy 已安装，但在 Software Phase 1 建立正式 `src/analog_validation/` 包及规则前，它们不是当前 Phase 0 代码的通过门槛。

## 当前边界

- 不安装 `pyserial`，串口适配器后置到 Software Phase 4；
- 不需要 CCS、MSP430 GCC、KiCad 或实验室仪器；
- 软件测试结果不代表任何模拟电路、控制器、接线或仪器已经验证；
- Git 提交身份已配置为 GitHub 账号 `Carlos-0798` 及其 noreply 邮箱。

## 本机备份

重建独立环境前的 Codex 运行时虚拟环境已移动到 `.venv-codex-backup-20260829`。新环境验证稳定后可以再决定是否移除；当前不删除该备份。
