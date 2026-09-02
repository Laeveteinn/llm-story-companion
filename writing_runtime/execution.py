from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any, Literal
import json

ContextMode = Literal['fresh_call', 'persistent_safe']


@dataclass(frozen=True)
class CallManifest:
    """Machine-readable context contract for one model invocation.

    Model identity is deliberately NOT a trust boundary. The same model may execute every
    phase. `fresh_call` means the inference/conversation context must be empty at call start;
    `persistent_safe` supports a continuing context only by forbidding author-only payloads.
    """

    version: int
    call_id: str
    phase: str
    context_mode: ContextMode
    prompt_sha256: str
    contract_id: str | None = None
    requires_fresh_context: bool = False
    discard_context_after_response: bool = False
    author_only_allowed: bool = False
    prior_model_output_forwarding: Literal['forbidden'] = 'forbidden'
    model_identity_may_repeat: bool = True
    isolation_grade: Literal['strong', 'degraded'] = 'strong'
    upstream: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_context_mode(value: str | None) -> ContextMode:
    mode = (value or 'fresh_call').strip().lower().replace('-', '_')
    aliases = {
        'fresh': 'fresh_call',
        'fresh_calls': 'fresh_call',
        'stateless': 'fresh_call',
        'single_session': 'persistent_safe',
        'persistent': 'persistent_safe',
        'same_context': 'persistent_safe',
    }
    mode = aliases.get(mode, mode)
    if mode not in {'fresh_call', 'persistent_safe'}:
        raise ValueError(f'unknown context mode {value!r}; expected fresh_call or persistent_safe')
    return mode  # type: ignore[return-value]


def make_call_manifest(
    *,
    phase: str,
    prompt: str,
    context_mode: str | None,
    contract_id: str | None = None,
    contains_author_only: bool = False,
    upstream: dict[str, str] | None = None,
) -> CallManifest:
    mode = normalize_context_mode(context_mode)
    if mode == 'persistent_safe' and contains_author_only:
        raise ValueError('persistent_safe context may not receive author-only/hidden information')
    prompt_hash = sha256(prompt.encode('utf-8')).hexdigest()
    seed = {
        'v': 1,
        'phase': phase,
        'context_mode': mode,
        'prompt_sha256': prompt_hash,
        'contract_id': contract_id,
        'upstream': upstream or {},
    }
    call_id = sha256(json.dumps(seed, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
    fresh = mode == 'fresh_call'
    return CallManifest(
        version=1,
        call_id=call_id,
        phase=phase,
        context_mode=mode,
        prompt_sha256=prompt_hash,
        contract_id=contract_id,
        requires_fresh_context=fresh,
        discard_context_after_response=fresh,
        author_only_allowed=fresh,
        isolation_grade='strong' if fresh else 'degraded',
        upstream=upstream or {},
    )


def verify_prompt_manifest(prompt: str, manifest: dict[str, Any]) -> dict[str, Any]:
    actual = sha256(prompt.encode('utf-8')).hexdigest()
    expected = str(manifest.get('prompt_sha256') or '')
    return {
        'ok': bool(expected and actual == expected),
        'expected_prompt_sha256': expected,
        'actual_prompt_sha256': actual,
        'call_id': manifest.get('call_id'),
        'phase': manifest.get('phase'),
        'context_mode': manifest.get('context_mode'),
    }
