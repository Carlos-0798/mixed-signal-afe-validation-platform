# Software Phase 6 文件级实施计划

**阶段名称：** 发布工程、外部测试与 v1.0 准备<br>
**规划状态：** 已完成；实现进度 5/8<br>
**首个交付目标：** 私有测试版 `0.1.0b1`（展示名 `v0.1.0-beta.1`）<br>
**最终阶段目标：** owner-approved Analog Validation Studio v1.0<br>
**预计时间：** 4–7 个有效开发日；初学者兼职约 1–2 周<br>
**默认硬件要求：** 无<br>
**AFE 硬件验证：** 0

## 当前进度

- [x] Step 1：发布合同、版本策略、支持范围和停止条件；
- [x] Step 2：GitHub Actions 持续集成；
- [x] Step 3：beta 版本与 package/release metadata；
- [x] Step 4：确定性构建、clean-install 和 release manifest；
- [x] Step 5：安装、测试、故障排查和反馈文档；
- [ ] Step 6：仅依赖公开 API 的第三方 adapter 示例；
- [ ] Step 7：隐私、许可证、历史、claims 和候选包审计；
- [ ] Step 8：owner review、合并、tag/Release 与 v1.0 决策。

Step 8 包含不可逆或对外可见的操作。本计划不会自动合并 PR、创建 tag、发布
GitHub Release、改变仓库可见性、选择许可证或关联 LinkedIn；这些动作必须先给出精确
预览并得到项目 owner 明确批准。

## 1. 初学者先理解“能运行”和“能交付”的区别

Phase 5 已证明软件在开发机和两个仓库外环境中能运行。Phase 6 解决的是别人能否在
不了解内部结构时可靠地获得同样结果：

1. 每次提交是否自动运行相同质量门；
2. 支持哪些 Python/操作系统组合，哪些没有证据；
3. wheel/sdist 是否来自可追溯提交，内容和 SHA-256 是否固定；
4. 新用户是否只按 Quick Start 就能安装、运行 demo 和提交反馈；
5. 第三方 adapter 是否真的只依赖公开 API；
6. 发布内容是否泄露路径、账号、原始串口、凭据或未经授权的项目材料；
7. 许可证和公开 claims 是否由 owner 审核。

CI、构建和 clean-install 都是软件证据，不会升级任何硬件声明。

## 2. 发布成熟度和版本策略

| 标识 | 含义 | 本阶段规则 |
|---|---|---|
| `0.1.0.dev0` | Phase 5 开发基线 | 已冻结为历史证据，不再作为测试交付版本 |
| `0.1.0b1` | 第一份受控 beta 候选 | 完成 Steps 1–7 后可交给受邀测试者 |
| `0.1.0rc1` | 功能与文档冻结的 release candidate | 只有 beta 反馈关闭或明确接受后才考虑 |
| `1.0.0` | owner-approved v1.0 | Step 8 审核、许可证和发布决策后才允许 |

版本号来自 `src/analog_validation/version.py`。构建产物、CLI `version`、Python import、
distribution metadata、release manifest 和文档必须一致。不能通过文件名临时改版本。

## 3. 支持与证据范围

### 3.1 beta 目标环境

- Python 3.10、3.12、3.14；
- Windows latest 和 Ubuntu latest 的无硬件 host tests；
- Windows/Python 3.12 的正式 coverage、build、base/serial clean-install 和 CLI demo；
- Tk Dashboard 的真实显示证据继续采用已完成的本地 Windows smoke；hosted runner 若
  无交互式 display，可跳过 display-only smoke，但不能把跳过写成通过。

三组 Python 版本代表最低声明、主要开发版本和当前上边界。只有 CI 实际通过后，文档
才可以写“tested”；中间版本或其他系统不得从版本范围自动推断为已验证。

### 3.2 明确不属于默认发布门

- 不打开真实 COM port，不 flash/reset MSP430；
- 不采购、搭建或测量 AFE；
- 不声称 macOS、Linux GUI、screen reader 或所有 Python minor version 已验证；
- 不做 PyPI 发布、代码签名、Windows installer 或自动升级；
- 不引入云账号、遥测、远程 listener 或在线报告资源；
- 不把 beta、CI 或模拟数据称为 production/field/bench evidence。

## 4. 八个实施步骤

### Step 1：发布合同与停止条件

创建本计划和 planning report；冻结 beta 名称、版本升级顺序、支持矩阵、产物、证据词汇、
隐私规则、owner-only 决策和 Phase 5 基线。验收时不改运行代码、不创建 Release。

### Step 2：GitHub Actions CI

新增只读、最小权限 workflow：

- Python/OS compatibility matrix；
- 100% statement coverage、Ruff、mypy 和 dependency check；
- isolated sdist/wheel build；
- wheel metadata/archive checks；
- repository-external base 与 `[serial]` install；
- installed CLI/demo smoke；
- workflow concurrency 和 artifact retention bounds。

第三方 actions 固定到评审过的 commit SHA，并在注释中记录 release tag。CI 不保存
token、路径、原始串口或测试硬件数据，也不授予 contents write 权限。

### Step 3：beta 版本和 metadata

将单一版本源升级为 `0.1.0b1`，更新 compatibility expectation、README、CHANGELOG 和
package metadata。发行包仍保留 “All rights reserved” 状态，直到 owner 选择许可证；
不得擅自添加 MIT、Apache 或其他授权。

### Step 4：release verifier 和 clean install

新增可重复执行的本地验证入口，输出 machine-readable release manifest，至少包含：

- source commit、package version 和 Python/platform；
- test/static/dependency/build/install/demo gate 状态；
- wheel/sdist filename、size、SHA-256；
- base/serial dependency边界；
- demo canonical hashes；
- `HOST_TEST`、`NO_NEW_HARDWARE_VALIDATION` 和未运行项。

manifest 必须 create-new、无用户名/绝对路径/token/COM/raw bytes，失败时不得生成 PASS。

### Step 5：用户测试闭环

创建：

- `docs/INSTALLATION.md`；
- `docs/USER_TESTING_GUIDE.md`；
- `docs/TROUBLESHOOTING.md`；
- GitHub bug-report / test-feedback templates；
- beta checklist 和已知限制。

新手路径必须从创建短路径 venv、安装 wheel、运行 `version`、运行 demo、查看报告、启动
Dashboard、收集非敏感诊断到提交反馈全部可执行。真实 serial 为可选且默认不测试。

### Step 6：公开扩展接口证明

提供仓库外风格的最小 read-only adapter 示例，只 import 安装包的公开 API。测试从 wheel
安装环境运行该 adapter through shared workflow，验证 connect/capability/read/cleanup、
provenance、no-write 和不依赖 repository-private modules。

### Step 7：候选审计与私有 beta 交付准备

审计完整 Git history、tracked files、构建 archives、metadata、third-party notices、LICENSE、
claims、路径、账号、token、图片/二进制和团队项目边界；运行完整本地门和 hosted CI；
创建候选 SHA-256/manifest、release notes 草稿和 tester bundle 清单。许可证未选择时只能
进行私有、受控测试，不能声称开放源代码许可。

### Step 8：owner review 和发布决策

向 owner 提供精确预览：目标 commit、base/head branch、version/tag、artifact hashes、
release notes、visibility、license state、known limitations、CI URL 和硬件证据边界。只有
明确批准后才能合并、tag、创建 pre-release；v1.0 还要求 beta 反馈处置和许可证决策。

## 5. CI 与本地门禁

正式 beta 候选至少同时满足：

- Phase 1–5 full/golden compatibility 全部通过；
- package statement coverage 100%；
- Ruff、mypy、`pip check` 通过；
- matrix 每个已声明环境真实通过或明确记录不支持；
- isolated sdist/wheel 的 metadata 和内容通过；
- base wheel 不安装/加载 pyserial；
- `[serial]` wheel 只做 injected substitute，不发现或打开真实 port；
- installed normal/Unicode demo byte-identical；
- external public-only adapter path 通过；
- docs links、privacy patterns 和 archive contents 通过；
- GitHub checks 无 required failure；
- AFE BENCH claims 保持 0。

## 6. 安全、隐私和供应链规则

- GitHub workflow 默认 `contents: read`，不使用 pull-request write token；
- action 固定到完整 commit SHA，不只写浮动 major tag；
- PR CI 不执行来自 secret 的发布动作；
- build artifact 保留期有界，不上传 `.venv`、coverage database、raw serial 或本机证据；
- tester diagnostic 只包含版本、命令结果和受控错误，不要求用户名、USB ID 或原始 frame；
- 默认 demo 离线、本地、create-new；
- release manifest 不嵌入绝对路径；
- 未选择许可证前保持 `All rights reserved`，不允许他人推断可复制/再分发；
- OSU capstone 与独立 MSP430 项目不进入本仓库历史或 release artifact。

## 7. 阶段出口与可安全声明内容

Steps 1–7 通过后，可称：

> Analog Validation Studio `0.1.0b1` is a private software beta candidate with
> automated host CI, reproducible packages, clean-install evidence, a guided
> tester workflow, and a public adapter extension proof.

仍不能称：

- public open-source release；
- v1.0 或 production-ready；
- 真实 AFE、ADC/DAC、阈值、带宽、噪声、安全或可靠性验证；
- 长时间真实 COM 或物理 disconnect/reconnect 验证；
- MSP430 exact firmware/peripheral validation。

## 8. 下一检查点

Step 5 已完成：安装、用户测试、故障排查、已知限制、checklist 和两个结构化反馈表单均有
静态契约；完整本地门为 2,216 tests、11,470/11,470 statements、Ruff、196-file mypy
与 dependency check。Hosted run `33448157429` 对 commit `5dc10db` 全部通过，且其 wheel
在仓库外短路径 Python 3.12 环境完成 hash、base install、version、双份 byte-identical
demo、HTML limitation、create-new refusal 和可选 Replay 验收。Dashboard 本轮记为
`NOT_RUN`，Serial/硬件保持 `NOT_RUN`。下一次实施 Step 6 public-API-only adapter proof。
