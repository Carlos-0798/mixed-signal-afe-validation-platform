# Architecture Decision Records

Architecture Decision Records（ADR）记录影响产品边界、公共接口、安全、兼容性或长期维护的重要决定。

## 状态

- `Proposed`：正在讨论；
- `Accepted`：当前必须遵守；
- `Superseded`：被新 ADR 替代，但保留历史；
- `Rejected`：评估后不采用。

## 命名

```text
NNNN-short-decision-title.md
```

## 模板

```markdown
# ADR-NNNN：标题

Status: Proposed
Date: YYYY-MM-DD

## Context

为什么需要决定。

## Decision

采用什么方案。

## Consequences

正面、负面和后续影响。

## Alternatives considered

评估过但未采用的方案。
```

已接受 ADR：

- `0001-software-first-ports-and-adapters.md`
- `0002-evidence-provenance-is-part-of-the-domain.md`
- `0003-versioned-profiles-for-controller-compatibility.md`

