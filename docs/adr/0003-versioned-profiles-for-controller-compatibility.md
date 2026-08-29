# ADR-0003：使用版本化 profile 维护控制器兼容性

**Status:** Accepted  
**Date:** 2026-08-29

## Context

AFE、MSP430 Equipment Health Controller、RP2040/STM32 和未来仪器具有不同字段、命令和能力。共享 CRC 和串口传输有价值，但把不同产品强制塞入同一消息结构会造成字段含义混乱和隐式耦合。

## Decision

- 保留 CRC-16/CCITT-FALSE 和有界 ASCII CSV 作为可共享传输约定；
- AFE 与 MSP430 使用独立、版本化 profile；
- profile 负责把设备原始消息映射到通用领域模型；
- 原始字段和原始帧可追溯保存；
- 板级引脚、寄存器和 SDK 名称不得进入公共主机协议；
- 可选能力通过 Capability 描述，不通过板名猜测；
- 不兼容版本或缺失能力返回明确错误/`UNSUPPORTED`。

## Consequences

- 两个项目可以共享经过验证的传输原则而不共享业务身份；
- 新控制器只需新增 profile/adapter；
- 需要维护 profile 版本和黄金消息；
- 某些设备只能提供只读或部分功能，这是被允许且必须显式表达的。

## Alternatives considered

1. **单一万能 CSV 消息：** 拒绝，字段会不断膨胀并产生空值和歧义。
2. **按设备复制整个应用：** 拒绝，分析和报告无法复用。
3. **根据 USB VID/PID 或板名推断能力：** 拒绝，板型不等于当前固件能力。

