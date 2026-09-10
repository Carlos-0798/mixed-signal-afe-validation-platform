# 私有 GitHub 同步：准备与本地门禁

**日期：** 2026-09-09<br>
**范围：** 当前软件成果归档、私有开发分支同步、现有 Draft PR 更新；未发布<br>
**证据：** HOST_TEST；示例 SYNTHETIC，导入预览 CSV_REPLAY；无新增硬件验证

## 为什么同步

TD-050/TD-051/TD-052 已完成本地交付，远程开发分支仍停在 `bf8c4c6`，
本地 HEAD 为 `aa1dd5b` 且有 75 项未提交成果。所有者要求先保存暂停点和后续路线，
再对齐 GitHub；功能扩展暂停，优先完成求职准备，之后再评估公开与下一输入来源。
恢复入口为 [项目接续文档](../docs/PROJECT_RESUME_CHECKPOINT_2026-09-09.md)。

## 保全与实际改动

- 同步前 506 个项目文件逐字节副本、SHA-256、Git 状态和 HEAD 可达历史 bundle
  已保存到工作树外的 `avs-github-sync-20260909-01`；全部哈希和 bundle 验证通过。
- 原有 37 项修改和 38 项未跟踪成果完整保留。Phase 3 golden 的一项状态没有净内容差异。
- 对齐 README、项目状态、冻结说明与技术债的当前入口，历史验收数字仍按阶段保留。
- 加入当前真实 Tk 的三主题导入预览，明确 SYNTHETIC 来源和 CSV_REPLAY 标签。
  图片未经编辑，旧两张截图保持原字节；审计只增加已查看图片的精确路径/哈希身份，
  不放宽隐私、二进制或发布规则。
- 两份报告中的个人绝对路径改用外部目录标识，本机完整路径另存恢复指南；原始报告
  副本和原始验收产物保留。没有更改历史测试数字、结果或 Git 历史。
- 所有 `src/` 运行文件与同步前快照逐字节一致；本次不增加产品功能。

## 发现与修复

同步前检查发现 Linux 路径使用原生 `renameat2`，旧导入包失败测试却只替换 `os.rename`。
模拟 Linux 路由时，旧测试明确出现 `DID NOT RAISE`；改为在正式目录发布边界注入失败，
并断言已准备的 Replay 文件、目标路径和失败后的清理。这样两种系统检验同一失败语义。

另补充一个可在 Linux 主机执行的 Windows 成功发布分支测试，验证实际移动、输入目录
消失和内容保留，使 Ubuntu 的全包 coverage 不依赖未执行的 Windows 分支。
两处均为测试修改，没有跳过、删除用例或改变覆盖门槛。

定向验证为 58 passed、相关两模块 226/226 语句覆盖，Ruff/mypy 通过。
模拟 Linux 路由不等于原生 Linux 实测；后者由同步后的 GitHub Actions 验证。

新文档首次暂存检查发现 Markdown 换行使用的行尾双空格触发 whitespace 门禁，
改为显式换行标记后重新检查；不影响运行代码或测试结果。

## 本次完整本地门禁

| 检查 | 结果 |
|---|---|
| 完整 pytest | **3,048 passed，96.40 秒，无失败或跳过**；比 TD-052 增加 1 项跨平台测试 |
| Package statement coverage | **17,567/17,567，100%**，0 missing；不是分支覆盖 |
| Ruff | src、tools、tests、examples/public_adapter 通过 |
| mypy | 252 个文件通过 |
| pip check | 无损坏依赖 |
| 产品质量验收 | 15/15 通过 |
| git diff --check | 通过；提交前另检查暂存差异 |

本次日志、coverage JSON、质量验收 JSON 和命令记录均在独立同步档案内。
TD-052 的 23 条独立安装 CLI 命令、真实 GUI 闭环和 100 个运行文件一致性仍引用原验收，
不伪装为本次全部重复执行。没有访问串口、控制器或仪器。

## 远程结果如何核对

本报告记录提交前的实际门禁，不预写自己的提交 SHA 或未来的 CI 成功。
同步完成后，以 [PR #10](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/pull/10)
当前 head 对应的 Actions 结果和外部 `SYNC_RECEIPT.md` / `sync-receipt.json` 为准。
需核对本地 HEAD 与远程开发分支完全相同、工作树干净、PR 仍为 Draft、仓库仍为 private。
如果 CI 失败，保存失败记录并修复具体阻塞；不得把本地成功当成远程通过。

main 保持原样，未经单独授权不 Ready、合并、tag、Release、发布包、修改可见性、
许可证或历史。公开评估仍需核对历史隐私记录与展示材料，不能引用旧审计当作当前结论。
