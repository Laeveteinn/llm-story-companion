# Single-model execution contract

The runtime assumes one model may perform every generative phase. Use **phase**, not **role**, when reasoning about trust.

## Preferred invocation pattern

```text
phase plan_generate
  fresh model context
  -> typed plan response
  discard context

mechanical plan gate

phase draft_generate
  fresh model context
  -> scene/beat response
  discard context

mechanical prose gate

phase prose_rewrite / prose_salvage
  fresh model context per attempt
  -> bounded candidate
  discard context
```

The model file, quantization, sampler profile, and runtime process may all be identical between calls. Only conversational/KV state must be fresh.

## Call manifests

Prompt-producing commands write manifests that record:

- `call_id`;
- `phase`;
- `context_mode`;
- prompt SHA-256;
- request contract ID when relevant;
- whether a fresh context is required;
- whether context must be discarded after response;
- whether author-only information was permitted;
- isolation grade;
- upstream artifact hashes.

Use:

```powershell
python write_runtime.py call-manifest-verify `
  --prompt .runtime/draft.prompt.txt `
  --manifest .runtime/draft.manifest.json
```

This proves the prompt and manifest still correspond. It cannot prove an external inference client actually reset its hidden context; that remains an executor obligation.

## Persistent fallback

If Hermes is operating as one continuing conversation and cannot spawn fresh inference sessions, invoke prompt-producing commands with:

```text
--context-mode persistent_safe
```

Do not use a persistent conversation that has already been exposed to author-only canon and then switch to `persistent_safe`. Once exposed, that conversation is contaminated for disclosure-sensitive writing and should be abandoned.

## Within-chapter knowledge changes

If `draft-prompt` reports that a plan requires disclosure epochs, do not bypass the refusal. Use `draft-epochs`. Every `E###.prompt.txt` is a separate model invocation with an empty context, even though the model weights/runtime are identical.

`persistent_safe` is intentionally rejected for multi-epoch drafting. Once a later epoch unlocks a secret, a continuing conversation would retain it during any subsequent repair of earlier prose. The runtime cannot make that context forget.

See `DISCLOSURE_EPOCHS.md`.
