# CRC 与 Framing 核心

**当前实现：** Software Phase 1 Step 5  
**证据等级：** HOST_TEST  
**硬件验证：** 无

本文解释 `analog_validation.protocol` 为什么被拆成 CRC 和 framing 两层，以及每层负责什么。

## 1. 用邮寄包裹理解协议分层

一条 UART 记录可以类比为一个包裹：

- **业务字段**是包裹里的物品，例如时间、电压、命令；
- **framing** 是包装规则，例如必须写 `AFE`、字段用逗号分隔、总长度不能超过 128 bytes；
- **CRC** 是封条编号，用于发现传输过程中是否有字节发生变化。

CRC 只能发现“收到的 bytes 和发送时不一样”，不能证明数据真实、合理或安全。一个内容错误但 CRC 正确的帧仍然可能被 framing 接受，后续 profile 必须继续验证字段含义和范围。

## 2. 唯一 CRC 实现

正式实现位于 `src/analog_validation/protocol/crc.py`。项目中不再维护第二份 CRC 算法；旧 `dashboard.protocol` 只是重新导出同一个函数。

参数固定为 CRC-16/CCITT-FALSE：

| 参数 | 值 |
|---|---|
| Width | 16 |
| Polynomial | `0x1021` |
| Initial | `0xFFFF` |
| RefIn / RefOut | false / false |
| XorOut | `0x0000` |
| `123456789` 检查值 | `0x29B1` |

函数只接受 `bytes`、`bytearray` 或 `memoryview`。文本必须先明确选择 ASCII 等编码，避免函数暗中猜测编码。

固定向量保存在 `test-data/golden/crc16_ccitt_false.json`。黄金向量是“输入和正确输出已经冻结的样本”，可以在重构后快速发现算法参数或位运算是否被意外改变。

## 3. Framing 负责的规则

正式实现位于 `src/analog_validation/protocol/framing.py`，负责：

- `AFE` namespace；
- 至少包含 namespace、消息类型和序号；
- 受限 CSV，不支持引号或转义；
- 字段只能包含 `0x21–0x7E` 范围的可打印 ASCII，不能含空白或逗号；
- 发送统一使用 LF；接收允许 LF 或 CRLF；
- 单记录 API 也允许调用者传入已经去掉 terminator 的完整记录；
- 裸 CR 和嵌入式 CR/LF 被拒绝；
- CRC 必须是四位大写十六进制；
- 整条序列化记录最多 128 bytes，包含 terminator；
- CRC 覆盖最后一个数据字段之前的所有 ASCII payload bytes，不覆盖 CRC 前逗号、CRC 字符和行结束。

Framing 不解释 `TEL`、`CMD`、电压、增益或 capability 的业务意义。它们将在 Step 6 的 AFE v1 profile 中定义。

## 4. 精确错误分类

| 异常 | 含义 | 典型处理 |
|---|---|---|
| `FramingError` | 非 ASCII、namespace/字段/token/CRC 格式或行结束错误 | 丢弃记录并记录原因 |
| `FrameTooLong` | 超过 128-byte 上限 | 停止增长缓冲区并丢弃到下一个 LF |
| `CrcMismatch` | 格式合法但计算 CRC 不一致 | 记录通信损坏，可按策略有限重试 |

三者都属于公开 `ProtocolError` 家族，因此上层既可以统一捕获协议错误，也可以针对特定错误采取不同恢复方式。

## 5. 为什么长度限制必须在解析前检查

真实 UART 可能持续收到没有换行的损坏数据。如果软件无限等待并扩大缓冲区，会造成内存和可用性问题。当前单记录 decoder 对输入 bytes 先检查 128-byte 上限，再进行 ASCII 和 CSV 解析。

真正处理串口分段、粘包和“超长后丢弃到下一个 LF”的流式状态机属于 Software Phase 4；Step 5 没有假装单记录函数已经解决真实串口接收问题。

## 6. 当前兼容层

Phase 0 的 `dashboard.protocol` 暂时保留 telemetry/command 业务函数，但其 `crc16_ccitt_false`、`encode_frame` 和 `decode_frame` 都直接引用正式包。这样现有工具继续工作，同时 CRC 和 framing 已经只有一个实现来源。

Step 6 会把 AFE 业务消息移入 `analog_validation.protocol.afe_v1`；Step 8 再清理不再需要的旧入口。

## 7. 证据边界

本步验证的是 Python bytes 和字符串处理，不是 UART 电气链路。没有验证波特率误差、电平、接地、线缆、EMI、控制器固件、丢包率或真实 CRC 错误恢复。
