# Work carried on `local` that is not in Blaizzy/mlx-vlm

`local` = upstream release tag + the commits below. `main` mirrors `Blaizzy/mlx-vlm` `main`
(fast-forward only; reset once on 2026-10-16, old tip tagged `archive/main-pre-sync-b39e1df`).

| What | Branch | Upstream status |
|---|---|---|
| Serve tekken checkpoints (Devstral-Small-2, Ministral-3): processor kwargs, detokenizer fallback, tokenizer.json control tokens, parallel tool calls | `topic/tekken-devstral-server` (on `main`); on `local` it is applied to v0.7.4 | not submitted; still needed on v0.7.8 and `main` |
| Do not add a second BOS to chat prompts whose template already emits it (Llama 3: 238/195/91 instead of 237/194/90 prompt tokens): server `_cpu_preprocess`, `generate`/`stream_generate` and batch generation | `topic/chat-template-no-double-bos` (based on `local`; the same call sites are unchanged on upstream `main`, read not run) | not submitted; nothing is posted upstream before the quantbench + agentbench soak (ADR-0008); eejd/py-mlx-vlm#2 |
| MiniCPM5 tool parser: a parameter value holding `<` or `&` without CDATA no longer makes the call invalid (it was parsed with `xml.etree`; 4 of 20 `tool_arg` cases of MiniCPM5-2B-4bit came back as plain text, no `tool_calls`); the call is scanned, a value is the text up to `</param>`, CDATA stays exact, well-formed character references are still decoded | `topic/minicpm5-tolerant-param-values` (based on `local`; `mlx_vlm/tools/parsers/minicpm5.py` is byte-identical on upstream `main` 2026-10-19, API read) | not submitted; nothing is posted upstream before the quantbench + agentbench soak (ADR-0008); eejd/py-mlx-vlm#6 |
| `mlx_vlm.server` honours the OpenAI-compatible `chat_template_kwargs` request field (`enable_thinking` resolved like the top-level one, other keys passed to the chat template; before, only a top-level `enable_thinking` reached the template and `qualify`'s form rendered the non-thinking prompt: Qwen3.5-4B-4bit and MiniCPM5-2B-4bit `reasoning` 0/20), and `--reasoning-parser qwen3` (reads only `<think>`/`</think>`, one state machine for stream and whole reply: every leading block is reasoning, a leading closer is dropped, the content after the leading blocks is verbatim; absent: no change) | `topic/reasoning-parser-chat-template-kwargs` (based on `local`; upstream `main` has no `chat_template_kwargs` in `mlx_vlm/server` by code search 2026-10-22, its gemma4 README documents the form; the closed Blaizzy/mlx-vlm#784 forwarded `extra_body` only; the open Blaizzy/mlx-vlm#2200 edits `GenerationArguments.to_template_kwargs`, `_build_gen_args` and `schemas.py` too: expect a textual conflict in those three files when either lands) | not submitted; nothing is posted upstream before the quantbench + agentbench soak (ADR-0008); eejd/py-mlx-vlm#5 |

Retired: `fix(utils): always run LanguageModel.sanitize for mlx-format checkpoints` (b39e1dfc,
old fork `main`, closed fork PR #1). Upstream's `load_model` sanitizes unconditionally since the
loader refactor, so it is superseded (checked against v0.7.8); the commit survives under
`archive/main-pre-sync-b39e1df`.

`local` is based on v0.7.4 (the version the port shipped); newer upstream releases up to v0.7.8
add dependencies (`datasets>=4`, `cryptography`) and `mlx>=0.32.3`, so the base was not moved.
