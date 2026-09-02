from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .story_state import apply_effect


class SemanticAction(BaseModel):
    """Typed narrative operations compiled into deterministic state mutations.

    These are deliberately small, common operations. Unusual world mechanics remain explicit
    StateCondition/StateEffect records instead of being forced into this vocabulary.
    """
    model_config = ConfigDict(extra='forbid')

    kind: Literal[
        'move','acquire','transfer','consume','injure','heal',
        'disable_capability','enable_capability',
        'spend_resource','gain_resource','learn_fact',
        'make_promise','resolve_promise','enter_scene','leave_scene',
    ]
    actor: str | None = None
    target: str | None = None
    item: str | None = None
    source: str | None = None
    destination: str | None = None
    location: str | None = None
    resource: str | None = None
    amount: float | None = None
    fact_ref: str | None = None
    promise_id: str | None = None
    injury: str | None = None
    capability: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    scene_id: str | None = None

    @model_validator(mode='after')
    def required_fields(self):
        req: dict[str, tuple[str, ...]] = {
            'move': ('actor','location'),
            'acquire': ('actor','item'),
            'transfer': ('source','destination','item'),
            'consume': ('actor','item'),
            'injure': ('target','injury'),
            'heal': ('target','injury'),
            'disable_capability': ('target','capability'),
            'enable_capability': ('target','capability'),
            'spend_resource': ('actor','resource','amount'),
            'gain_resource': ('actor','resource','amount'),
            'learn_fact': ('actor','fact_ref'),
            'make_promise': ('actor','promise_id'),
            'resolve_promise': ('actor','promise_id'),
            'enter_scene': ('actor',),
            'leave_scene': ('actor',),
        }
        missing = [name for name in req[self.kind] if getattr(self, name) is None]
        if missing:
            raise ValueError(f'{self.kind} requires {", ".join(missing)}')
        if self.kind in {'spend_resource','gain_resource'} and (self.amount is None or self.amount <= 0):
            raise ValueError(f'{self.kind} amount must be > 0')
        return self


@dataclass(frozen=True)
class SemanticIssue:
    code: str
    severity: str
    message: str
    hard: bool = True
    evidence: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _list(state: dict[str, dict[str, Any]], subject: str, key: str) -> list[Any]:
    value = state.get(subject, {}).get(key, [])
    return value if isinstance(value, list) else []


def _alive(state: dict[str, dict[str, Any]], actor: str) -> bool:
    return state.get(actor, {}).get('alive', True) is not False


def _blocked(state: dict[str, dict[str, Any]], actor: str, capability: str) -> bool:
    return capability in _list(state, actor, 'blocked_capabilities')


def actor_can_perform(state: dict[str, dict[str, Any]], actor: str, beat_kind: str) -> list[SemanticIssue]:
    issues: list[SemanticIssue] = []
    if not _alive(state, actor):
        issues.append(SemanticIssue('semantic.dead_actor','error',f'{actor} acts while marked dead',True,{'actor':actor}))
        return issues
    capability = {
        'dialogue':'speak', 'reflection':'think', 'decision':'think',
        'action':'act', 'conflict':'act', 'transition':'move',
    }.get(beat_kind)
    if capability and _blocked(state, actor, capability):
        issues.append(SemanticIssue('semantic.blocked_capability','error',
                                    f'{actor} performs {beat_kind} while capability {capability!r} is blocked',True,
                                    {'actor':actor,'capability':capability,'beat_kind':beat_kind}))
    return issues


def _kind(registry: dict[str, dict[str, Any]], subject: str) -> str | None:
    row = registry.get(subject) or {}
    return row.get('kind')


def _type_issue(registry: dict[str, dict[str, Any]], subject: str | None, expected: str, field: str) -> SemanticIssue | None:
    if not subject or subject not in registry:
        return None
    actual = _kind(registry, subject)
    if actual == expected:
        return None
    return SemanticIssue('semantic.subject_type','error',f'{field} {subject!r} is {actual!r}, expected {expected!r}',True,
                         {'subject':subject,'field':field,'expected':expected,'actual':actual})


def apply_semantic_action(state: dict[str, dict[str, Any]], action: SemanticAction, *,
                          registry: dict[str, dict[str, Any]] | None = None,
                          current_scene_id: str | None = None) -> list[SemanticIssue]:
    """Validate and apply one semantic operation atomically enough for plan replay.

    On hard precondition failure no mutation is performed. State is intentionally plain JSON-like
    data so it remains serializable, hashable, and easy to inspect.
    """
    registry = registry or {}
    issues: list[SemanticIssue] = []
    k = action.kind

    for subject, expected, field in (
        (action.actor,'character','actor'), (action.source,'character','source'),
        (action.destination,'character','destination'), (action.target,'character','target'),
        (action.item,'item','item'), (action.location,'location','location'),
    ):
        # target is not always a character in every imaginable story, but current typed actions use it that way.
        issue = _type_issue(registry, subject, expected, field)
        if issue: issues.append(issue)
    if any(i.hard for i in issues): return issues

    principal = action.actor or action.source or action.target
    if principal and k not in {'injure','heal','disable_capability','enable_capability'} and not _alive(state, principal):
        return [SemanticIssue('semantic.dead_actor','error',f'{principal} cannot perform {k} while dead',True,{'actor':principal,'kind':k})]

    if k == 'move':
        assert action.actor and action.location
        if _blocked(state, action.actor, 'move'):
            return [SemanticIssue('semantic.blocked_capability','error',f'{action.actor} cannot move',True,{'actor':action.actor,'capability':'move'})]
        if state.get(action.actor,{}).get('location') == action.location:
            issues.append(SemanticIssue('semantic.noop_move','warning',f'{action.actor} is already at {action.location}',False))
        apply_effect(state, action.actor, 'location', 'set', action.location)
        for subject, values in state.items():
            if values.get('owner') == action.actor and 'location' in values:
                apply_effect(state, subject, 'location', 'set', action.location)

    elif k == 'acquire':
        assert action.actor and action.item
        owner = state.get(action.item,{}).get('owner')
        if owner not in (None, action.actor):
            return [SemanticIssue('semantic.item_owned','error',f'{action.item} is owned by {owner}, not free to acquire',True,{'item':action.item,'owner':owner})]
        apply_effect(state, action.actor, 'inventory', 'add', action.item)
        apply_effect(state, action.item, 'owner', 'set', action.actor)
        if state.get(action.actor,{}).get('location') is not None:
            apply_effect(state, action.item, 'location', 'set', state[action.actor]['location'])

    elif k == 'transfer':
        assert action.source and action.destination and action.item
        source_has = action.item in _list(state, action.source, 'inventory')
        owner = state.get(action.item,{}).get('owner')
        if not source_has or (owner is not None and owner != action.source):
            return [SemanticIssue('semantic.transfer_without_possession','error',
                                  f'{action.source} cannot transfer {action.item} they do not possess',True,
                                  {'item':action.item,'source':action.source,'owner':owner,'source_inventory':source_has})]
        apply_effect(state, action.source, 'inventory', 'remove', action.item)
        apply_effect(state, action.destination, 'inventory', 'add', action.item)
        apply_effect(state, action.item, 'owner', 'set', action.destination)
        if state.get(action.destination,{}).get('location') is not None:
            apply_effect(state, action.item, 'location', 'set', state[action.destination]['location'])

    elif k == 'consume':
        assert action.actor and action.item
        if action.item not in _list(state, action.actor, 'inventory'):
            return [SemanticIssue('semantic.consume_without_possession','error',
                                  f'{action.actor} cannot consume/use {action.item} without possessing it',True,
                                  {'actor':action.actor,'item':action.item})]
        apply_effect(state, action.actor, 'inventory', 'remove', action.item)
        apply_effect(state, action.item, 'owner', 'unset')
        apply_effect(state, action.item, 'status', 'set', 'consumed')

    elif k == 'injure':
        assert action.target and action.injury
        apply_effect(state, action.target, 'injuries', 'add', action.injury)
        for cap in action.capabilities:
            apply_effect(state, action.target, 'blocked_capabilities', 'add', cap)

    elif k == 'heal':
        assert action.target and action.injury
        if action.injury not in _list(state, action.target, 'injuries'):
            issues.append(SemanticIssue('semantic.heal_missing_injury','warning',f'{action.target} does not have injury {action.injury}',False))
        apply_effect(state, action.target, 'injuries', 'remove', action.injury)
        for cap in action.capabilities:
            apply_effect(state, action.target, 'blocked_capabilities', 'remove', cap)

    elif k in {'disable_capability','enable_capability'}:
        assert action.target and action.capability
        apply_effect(state, action.target, 'blocked_capabilities', 'add' if k == 'disable_capability' else 'remove', action.capability)

    elif k in {'spend_resource','gain_resource'}:
        assert action.actor and action.resource and action.amount is not None
        key = f'resource:{action.resource}'
        current = state.get(action.actor,{}).get(key, 0)
        if not isinstance(current,(int,float)):
            return [SemanticIssue('semantic.resource_type','error',f'{action.actor}.{key} is not numeric',True,{'actual':current})]
        if k == 'spend_resource' and current < action.amount:
            return [SemanticIssue('semantic.resource_underflow','error',
                                  f'{action.actor} spends {action.amount} {action.resource} but has {current}',True,
                                  {'actor':action.actor,'resource':action.resource,'required':action.amount,'actual':current})]
        apply_effect(state, action.actor, key, 'dec' if k == 'spend_resource' else 'inc', action.amount)

    elif k == 'learn_fact':
        assert action.actor and action.fact_ref
        apply_effect(state, action.actor, 'knowledge', 'add', action.fact_ref)

    elif k == 'make_promise':
        assert action.actor and action.promise_id
        if action.promise_id in _list(state, action.actor, 'open_promises'):
            issues.append(SemanticIssue('semantic.promise_duplicate','warning',f'promise {action.promise_id} is already open',False))
        apply_effect(state, action.actor, 'open_promises', 'add', action.promise_id)
        apply_effect(state, action.actor, 'resolved_promises', 'remove', action.promise_id)

    elif k == 'resolve_promise':
        assert action.actor and action.promise_id
        if action.promise_id not in _list(state, action.actor, 'open_promises'):
            return [SemanticIssue('semantic.promise_not_open','error',f'cannot resolve unopened promise {action.promise_id}',True,
                                  {'actor':action.actor,'promise_id':action.promise_id})]
        apply_effect(state, action.actor, 'open_promises', 'remove', action.promise_id)
        apply_effect(state, action.actor, 'resolved_promises', 'add', action.promise_id)

    elif k in {'enter_scene','leave_scene'}:
        assert action.actor
        sid = action.scene_id or current_scene_id
        if not sid:
            return [SemanticIssue('semantic.scene_id_missing','error',f'{k} requires a scene id',True)]
        subject = f'scene:{sid}'
        present = _list(state, subject, 'participants')
        if k == 'enter_scene' and action.actor in present:
            issues.append(SemanticIssue('semantic.already_present','warning',f'{action.actor} is already present in {sid}',False))
        if k == 'leave_scene' and action.actor not in present:
            return [SemanticIssue('semantic.leave_when_absent','error',f'{action.actor} cannot leave {sid}; they are absent',True)]
        apply_effect(state, subject, 'participants', 'add' if k == 'enter_scene' else 'remove', action.actor)

    return issues


def audit_semantic_state(state: dict[str, dict[str, Any]], *, registry: dict[str, dict[str, Any]] | None = None) -> list[SemanticIssue]:
    """Cross-record consistency checks that generic key/value invariants cannot express succinctly."""
    registry = registry or {}
    issues: list[SemanticIssue] = []

    holders: dict[str, list[str]] = {}
    for subject, values in state.items():
        inv = values.get('inventory')
        if isinstance(inv,list):
            for item in inv:
                holders.setdefault(str(item),[]).append(subject)
        for key,value in values.items():
            if key.startswith('resource:') and isinstance(value,(int,float)) and value < 0:
                issues.append(SemanticIssue('semantic.negative_resource','error',f'{subject}.{key} is negative',True,
                                            {'subject':subject,'key':key,'value':value}))
        op = values.get('open_promises'); rp = values.get('resolved_promises')
        if isinstance(op,list) and isinstance(rp,list):
            overlap = sorted(set(op) & set(rp))
            if overlap:
                issues.append(SemanticIssue('semantic.promise_state_conflict','error',
                                            f'{subject} has promises both open and resolved',True,{'promises':overlap}))

    for item, owners in sorted(holders.items()):
        if len(owners) > 1:
            issues.append(SemanticIssue('semantic.double_possession','error',f'{item} appears in multiple inventories',True,
                                        {'item':item,'holders':sorted(owners)}))
        declared = state.get(item,{}).get('owner')
        if declared is not None and declared not in owners:
            issues.append(SemanticIssue('semantic.owner_inventory_mismatch','error',
                                        f'{item}.owner={declared} but that inventory does not contain it',True,
                                        {'item':item,'owner':declared,'holders':owners}))
        if owners and declared is None:
            issues.append(SemanticIssue('semantic.inventory_owner_missing','warning',
                                        f'{item} is in an inventory but has no explicit owner record',False,
                                        {'item':item,'holders':owners}))

    for item, values in state.items():
        owner = values.get('owner')
        if owner is None: continue
        if item not in holders:
            issues.append(SemanticIssue('semantic.owner_inventory_mismatch','error',
                                        f'{item}.owner={owner} but item is not in any inventory',True,
                                        {'item':item,'owner':owner}))
        item_loc = values.get('location'); owner_loc = state.get(owner,{}).get('location')
        if item_loc is not None and owner_loc is not None and item_loc != owner_loc:
            issues.append(SemanticIssue('semantic.owned_item_location_mismatch','error',
                                        f'{item} is owned by {owner} but locations disagree',True,
                                        {'item':item,'item_location':item_loc,'owner':owner,'owner_location':owner_loc}))

    for subject, values in state.items():
        loc = values.get('location')
        if loc is not None and loc in registry and _kind(registry, loc) != 'location':
            issues.append(SemanticIssue('semantic.location_type','error',f'{subject}.location points to non-location {loc}',True,
                                        {'subject':subject,'location':loc,'actual_kind':_kind(registry,loc)}))
    return issues


def writer_semantic_action(action: SemanticAction) -> dict[str, Any] | None:
    """Return writer-safe structured obligation. Secret fact IDs stay out of normal writer packets."""
    if action.kind == 'learn_fact':
        return None
    return action.model_dump(mode='json', exclude_none=True)
