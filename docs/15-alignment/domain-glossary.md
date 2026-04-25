# Domain Glossary

This glossary is reserved for coordination language that helps humans and agents route work consistently across layers.

It does not own product vocabulary, cross-unit architecture truth, or framework text.

## Coordination Terms

- Durable owner: the local layer that should hold a stable truth once it is ready to be promoted.
- Task packet: the active workspace under `tasks/<task-slug>/` that holds volatile reasoning, evidence, plans, and temporary artifacts.
- Local seam guidance: the nearest local `AGENTS.md` that protects a fragile code boundary with fast-moving tripwires and editing constraints.
- Promotion candidate: a task-level finding that may become durable only if it is stable, expensive to rediscover, and not better enforced mechanically.

## Routing Notes

- Product terms belong in `docs/10-prd/glossary.md`.
- Cross-unit architecture and technical boundary terms belong in `docs/20-product-tdd/`.
- Runtime and operational vocabulary belongs in `docs/40-deployment/`.
- Repository-wide routing posture belongs in the root `AGENTS.md` and `docs/00-meta/`.
