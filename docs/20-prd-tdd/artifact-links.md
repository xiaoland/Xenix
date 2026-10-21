# Artifact Link Contract

## Admission

Producing services, Agent Harness, Chatbot UI, LinkRouter, and ArtifactService must
share one result identity and activation contract. Losing it can expose local paths
or make dataset and artifact identities interchangeable.

## Identity

Artifact links use one authority:

```text
artifact://<artifact_id>
```

`artifact_id` is the Artifact's persistent integer ID written in decimal, for example `artifact://42`. It is the same ID returned by services and Tools, with no separate short-name mapping.

Dataset ids identify registered data for later service or tool input. They are not
link authorities. A derived dataset intended for user download must also have a
ready export artifact.

A Chatbot source attachment is not an Artifact link. Harness may project the
original import's bounded label and an in-process local opening target from
Dataset provenance for the desktop UI. That target is neither persisted
conversation content nor provider input, and it must not be converted into an
Artifact identity merely to reopen a Thread.

Generic Chatbot-event diagnostic serialization and logging must redact that
opening target. The desktop bubble keeps it only in its short-lived local
activation map.

Legacy `view` query hints are accepted for compatibility but ignored. Artifact kind,
MIME type, and markdown syntax determine current presentation.

## Authority Flow

```text
producing service
  -> ArtifactService registers a ready local result
  -> tool or service result exposes artifact_id
  -> assistant markdown may reference artifact://<artifact_id>
  -> Chatbot passes activation to LinkRouter
  -> ArtifactService resolves and opens the registered local artifact
```

Markdown image syntax requests an inline image preview; an ordinary markdown link
requests a normal openable artifact. Both retain the same artifact id authority.

桌面 Markdown 在把 HTML 交给 Qt 前，将整数 authority 转为 `artifact:/42` 路径形式，避免 `QUrl` 把较小的整数改写为 IPv4 地址。
这是 ArtifactService 已支持的界面传输形式；持久化内容和工具结果继续使用规范身份 `artifact://42`。

## Invariants

- ArtifactService owns registration, readiness, URI resolution, and local file
  activation. LinkRouter owns UI link dispatch.
- UI and provider-facing content do not construct, expose, or activate raw local
  paths as artifact identities. An ephemeral Chatbot source presentation may
  carry a local opening target only inside the desktop UI boundary; it is not an
  artifact URI, Markdown target, provider value, or canonical Message field.
- Remote worker paths are never artifact links. Remote outputs become linkable only
  after local finalization and registration.
- A missing registration or registered file is a service error and activation
  fails.
- Tool results expose integer identities and may include the canonical Artifact URI; conversation presentation owns Markdown construction.

## Verification

URI parsing and registration are covered by `tests/storage/test_storage_artifacts.py`; producing ML service paths and end-to-end Agent artifact links are covered under `tests/ml/` and `tests/e2e/agent_harness/`.
`tests/ui/test_markdown_renderer.py` 和 `tests/ui/test_chatbot_contract.py` 验证经过 Qt 的身份保持、已注册文件的点击打开，以及用户与助手消息的图片尺寸和屏幕密度适配。
