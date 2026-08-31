# 开发环境

**验证日期：** 2026-08-31<br>
**当前阶段：** Software Phase 5 已完成（8/8，Software Beta）<br>
**硬件要求：** 默认软件门禁无需硬件；Phase 4 Step 7 已单独完成一次 MSP430 receive-only HIL

## 已验证环境

- Windows 11 Home 64-bit，build 26200；
- Python 3.12.10 64-bit，来自 python.org 独立安装；
- Git for Windows 2.55.0；
- Visual Studio Code 1.135.0；
- LTspice 26.0.1（未来模拟电路仿真使用，当前 Software Phase 5 不依赖）；
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
.\.venv\Scripts\python.exe -m ruff check src tools tests examples/public_adapter
.\.venv\Scripts\python.exe -m mypy src tools tests examples/public_adapter
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m build
```

pytest、三项 package coverage、全仓库 Ruff rule check、mypy、依赖检查、构建和仓库外 wheel 安装是当前质量门禁。Software Phase 3 已完成正式分析、runner 和导出，Software Phase 4 已完成 transport、profiles、receive-only serial adapter、可选 pyserial backend、兼容冻结和窄范围 COM4 HIL，Software Phase 5 已完成独立产品层、CLI/report/Dashboard/demo 和公共兼容冻结。Software Phase 6 Steps 1–6 又建立 release contract、hosted matrix、`0.1.0b1` metadata、同一本地/CI release verifier、beginner tester/feedback 闭环与 public-only adapter 扩展证明。当前完整门禁为 2,222 tests、0 skipped、11,470/11,470 package statements、全仓库 Ruff、199-file mypy、两次隔离构建、fresh base + `[serial]` 安装、普通/Unicode installed demo、hosted wheel tester journey，以及 external `python -I` adapter run。

当前 CLI 已执行正式的软件 read/DC/迟滞、`report` 和 `demo` 工作流；`dashboard` 已执行 reviewed 六步 Simulator/Replay/receive-only 工作流。最终 base wheel 在仓库外短路径环境完成 headless import，并在普通与 Unicode 目录生成逐字节一致的 12 个 demo artifacts；同一安装历史上已真实启动并安全关闭 Tk Dashboard。独立 `[serial]` 安装只使用注入式 host substitute，真实端口枚举/打开/写入均为 0。Step 5 用 hosted wheel 完成 beginner tester journey；Step 6 将 public adapter 单文件复制到仓库外，并以 fresh base wheel 的 isolated Python 完成 public import、capability、三次 read、cleanup 与 zero-write 验收。本地/hosted 三文件候选逐字节一致。10k Replay/event、键盘焦点、Tk 1.0/1.5/2.0 scaling、隐私和 no-network 验收继续有效。下一检查点是 Software Phase 6 Step 7 final candidate audit。

安装后可验证最小产品入口：

```powershell
analog-validation --help
analog-validation version
analog-validation profiles
analog-validation simulate read --samples 3
analog-validation simulate dc --points 6 --output work\dc-result.json --json
analog-validation report --input work\dc-result.json --output work\dc-report --json
analog-validation simulate hysteresis
analog-validation demo --output work\software-demo --json
analog-validation dashboard
```

当前 Ruff 0.16.5 的全仓 formatter 仍会建议重排历史文件；Step 7 只对本步骤文件进行
局部格式维护，全仓机械重排被单独保留为维护事项，避免掩盖功能 diff。

## 当前边界

- 正式核心和 Simulator/Replay CLI 仍不要求 `pyserial`；owning worker 与 interpreter-interrupt 取消已完成 HOST_TEST，但真实串口长时间运行、物理断线和交互式 Windows console smoke 尚未验证；
- Windows 默认旧式路径长度限制仍会影响用户手动选择的过深虚拟环境；Step 4 verifier 使用系统临时 venv/build、短同父 staging 和写前长度检查，Step 5 安装/故障排查文档要求短 beta root，且 hosted wheel 已在该路径完成外部测试者验收；
- 不需要 CCS、MSP430 GCC、KiCad 或实验室仪器；
- 软件测试结果不代表任何模拟电路、控制器、接线或仪器已经验证；
- Git 提交身份已配置为 GitHub 账号 `Carlos-0798` 及其 noreply 邮箱。

## 本机备份

重建独立环境前的 Codex 运行时虚拟环境已移动到 `.venv-codex-backup-20260829`。新环境验证稳定后可以再决定是否移除；当前不删除该备份。
