# Work carried on `local` that is not in Blaizzy/mlx-vlm

`local` = upstream release tag + the commits below. `main` mirrors `Blaizzy/mlx-vlm` `main`
(fast-forward only; reset once on 2026-10-16, old tip tagged `archive/main-pre-sync-b39e1df`).

| What | Branch | Upstream status |
|---|---|---|
| Serve tekken checkpoints (Devstral-Small-2, Ministral-3): processor kwargs, detokenizer fallback, tokenizer.json control tokens, parallel tool calls | `topic/tekken-devstral-server` (on `main`); on `local` it is applied to v0.7.4 | not submitted; still needed on v0.7.8 and `main` |

Retired: `fix(utils): always run LanguageModel.sanitize for mlx-format checkpoints` (b39e1dfc,
old fork `main`, closed fork PR #1). Upstream's `load_model` sanitizes unconditionally since the
loader refactor, so it is superseded (checked against v0.7.8); the commit survives under
`archive/main-pre-sync-b39e1df`.

`local` is based on v0.7.4 (the version the port shipped); newer upstream releases up to v0.7.8
add dependencies (`datasets>=4`, `cryptography`) and `mlx>=0.32.3`, so the base was not moved.
