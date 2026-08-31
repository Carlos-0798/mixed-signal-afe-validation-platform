# CRC 与 Framing 核心

**当前实现：** Software Phase 4 Step 2 complete<br>
**证据等级：** HOST_TEST  
**硬件验证：** 无

本文解释 `analog_validation.protocol` 的 CRC/单记录 envelope，以及
`analog_validation.transport` 的真实字节流边界分别负责什么。

## 1. 用邮寄包裹理解协议分层

一条 UART 记录可以类比为一个包裹：

- **业务字段**是包裹里的物品，例如时间、电压、命令；
- **framing** 是包装规则，例如必须写 `AFE`、字段用逗号分隔、总长度不能超过 128 bytes；
- **CRC** 是封条编号，用于发现传输过程中是否有字节发生变化。

CRC 只能发现“收到的 bytes 和发送时不一样”，不能证明数据真实、合理或安全。一个内容错误但 CRC 正确的帧仍然可能被 framing 接受，后续 profile 必须继续验证字段含义和范围。

## 2. 唯一 CRC 实现

正式实现位于 `src/analog_validation/protocol/crc.py`。项目中不再维护第二份 CRC 算法，旧 `dashboard.protocol` 已在 Step 8 完成调用迁移后删除。

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

## 3. Profile-neutral CRC envelope

Software Phase 4 Step 2 把设备无关规则放入
`src/analog_validation/protocol/envelope.py`。它负责：

- 受限 CSV，不支持引号或转义；
- 字段只能包含 `0x21–0x7E` 范围的可打印 ASCII，不能含空白或逗号；
- 发送统一使用 LF；接收允许 LF 或 CRLF；
- 单记录 API 也允许调用者传入已经去掉 terminator 的完整记录；
- 裸 CR 和嵌入式 CR/LF 被拒绝；
- CRC 必须是四位大写十六进制；
- 整条序列化记录最多 128 bytes，包含 terminator；
- CRC 覆盖最后一个数据字段之前的所有 ASCII payload bytes，不覆盖 CRC 前逗号、CRC 字符和行结束。

`encode_crc_envelope()` 和 `decode_crc_envelope()` 不要求 `AFE` namespace，
也不解释 `TEL`、`STS`、电压、温度、状态或 capability。黄金 MSP430 形状
fixture 证明无 namespace 的 payload 可以通过同一 token/CRC 层，但不构成
MSP430 business parser、串口或硬件互操作证据。

## 4. AFE 兼容 wrapper

`src/analog_validation/protocol/framing.py` 现在是通用 envelope 上方的薄
AFE wrapper。它继续额外要求：

- `AFE` namespace；
- 至少包含 namespace、消息类型和序号；
- 保持原 `Frame`、`MAX_RECORD_BYTES`、`encode_frame()`、`decode_frame()`
  名称、签名、错误和 bytes 不变。

业务字段仍由 `protocol/afe_v1.py` 解释。旧 20 条合法和 9 条非法黄金记录
全部通过原入口，Phase 1–3 顶层及 `protocol.__all__` 没有增加或删除符号。

## 5. Profile-neutral 字节流负责的规则

正式实现位于 `src/analog_validation/transport/stream.py`。它接收任意大小的
bytes chunks，只识别 LF 和最大记录长度：

- 一条记录分多次到达时保留 incomplete bytes；
- 多条记录一次到达时按原顺序全部输出；
- 原样保留 CRLF、非 ASCII、空行和损坏记录，交给 profile 判断；
- 记录超过上限后停止增长有效 buffer，丢弃到下一个 LF；
- 输出结构化 `OVERLONG_RECORD` issue 和实际丢弃 byte 数；
- 同一 chunk 在超长记录 LF 后仍可恢复后续合法记录；
- disconnect/reset 只报告并丢弃 incomplete bytes，不把它们伪装成记录。

`transport/sequence.py` 由 profile 指定位宽，分别支持 AFE 16-bit 和 MSP430
32-bit sequence，记录首次、连续、缺帧、重复、乱序和 modular wrap。字节流与
sequence 层都不打开串口，也不包含设备字段、单位、capability 或业务逻辑。

## 6. 精确错误分类

| 异常 | 含义 | 典型处理 |
|---|---|---|
| `FramingError` | 非 ASCII、namespace/字段/token/CRC 格式或行结束错误 | 丢弃记录并记录原因 |
| `FrameTooLong` | 超过 128-byte 上限 | 停止增长缓冲区并丢弃到下一个 LF |
| `CrcMismatch` | 格式合法但计算 CRC 不一致 | 记录通信损坏，可按策略有限重试 |

三者都属于公开 `ProtocolError` 家族，因此上层既可以统一捕获协议错误，也可以针对特定错误采取不同恢复方式。

## 7. 为什么长度限制必须在解析前检查

真实 UART 可能持续收到没有换行的损坏数据。如果软件无限等待并扩大缓冲区，会造成内存和可用性问题。当前单记录 decoder 对输入 bytes 先检查 128-byte 上限，再进行 ASCII 和 CSV 解析。

Software Phase 4 Steps 1–4 已用复合集成测试把不规则 chunks 依次经过
driver-neutral session、bounded stream、raw event 和 neutral envelope，并保持
混合 AFE/MSP 形状记录的 bytes、顺序和 fields。timeout、断线清半帧和有限
reconnect 已由内存 backend 做 HOST_TEST；AFE records 现在继续经过独立
serial profile，形成 canonical Measurements、capability outcome 或 typed rejection。
真实 OS backend、COM timing 和 HIL 仍属于后续检查点。

## 8. 黄金兼容数据

Step 8 冻结了三类互补数据：

- `crc16_ccitt_false.json`：算法参数和检查值；
- `afe_v1_valid.csv` + `expected_frames.json`：wire record 与领域含义的双向兼容；
- `afe_v1_invalid.csv`：坏 CRC、坏版本、坏字段、非 ASCII 和超长记录对应的稳定错误类型。
- `profile_neutral_envelope_v1.json`：一个 AFE 形状和两个 MSP430 形状记录的
  profile-neutral CRC bytes/fields；只冻结 envelope 兼容。

合法记录必须能够解析为预期模型并重新编码为完全相同的 bytes。旧的无版本 AFE façade 不再是受支持入口。
Step 4 进一步要求全部 20 valid/9 invalid records 经过 serial-profile raw
outcome 路径，仍保持相同 bytes 和 error family。

## 9. 证据边界

当前验证的是 Python bytes、字符串处理和 host sequence 状态，不是 UART
电气链路。没有验证波特率误差、电平、接地、线缆、EMI、控制器固件、真实
timeout/reconnect、丢包率或真实 CRC 错误恢复。
