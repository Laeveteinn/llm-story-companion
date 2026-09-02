from __future__ import annotations

import argparse
from hashlib import sha256
import json
import sys
import yaml
from pathlib import Path

from .canon import CanonLibrary, build_canon_database
from .contracts import (
    validate_rewrite_response, parse_gap_response, validate_plan_response,
)
from .external_tools import doctor
from .execution import make_call_manifest, normalize_context_mode, verify_prompt_manifest
from .toolchain import expected_version_report, verify_lock, write_lock
from .prose import ProseAnalyzer, load_profile, calibrate
from .quality import QualityGate, load_policy
from .reinjection import compile_directives, make_repair_packet, render_rewrite_prompt, redact_unrevealed_canon
from .repair import apply_gap_response, make_salvage_plan, repair_state_transition, salvage_plan_from_dict, salvage_prompt
from .story_state import build_state_database, StoryStateLibrary
from .semantic import audit_semantic_state
from .planning import (
    ChapterPlan, PlanGate, apply_plan_salvage, load_plan, make_plan_salvage, plan_generation_prompt,
    plan_repair_transition, plan_rewrite_prompt, plan_salvage_prompt, plan_schema, scene_draft_prompt, validate_scene_draft,
    writer_plan_surface, compile_disclosure_epochs, epoch_draft_prompt, validate_epoch_draft, assemble_epoch_drafts, DraftEpoch,
)

ROOT = Path(__file__).parents[1]


def read_text(path): return Path(path).read_text(encoding='utf-8') if path else sys.stdin.read()

def dump(data, as_json=False):
    if as_json: print(json.dumps(data, indent=2, ensure_ascii=False))
    else: print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

def _load_yaml(path: str | Path) -> dict:
    data=yaml.safe_load(Path(path).read_text(encoding='utf-8')) or {}
    if not isinstance(data,dict): raise ValueError(f'{path}: expected mapping')
    return data

def _add_quality_args(p):
    p.add_argument('text'); p.add_argument('--policy', default=str(ROOT/'config'/'gate_policy.yaml'))
    p.add_argument('--library', default='canon/canon.sqlite3'); p.add_argument('--viewpoint'); p.add_argument('--at'); p.add_argument('--branch',default='main')
    p.add_argument('--profile'); p.add_argument('--chapter-plan'); p.add_argument('--provenance'); p.add_argument('--no-external', action='store_true'); p.add_argument('--no-advanced-nlp', action='store_true')
    p.add_argument('--json', action='store_true')

def _quality(args):
    policy=load_policy(args.policy); gate=QualityGate(root=ROOT,policy=policy)
    library=args.library if args.library and Path(args.library).exists() else None
    chapter_plan = getattr(args,'chapter_plan',None) or getattr(args,'writer_plan',None)
    if chapter_plan is None and getattr(args,'cmd',None) == 'rewrite-prompt':
        chapter_plan = getattr(args,'plan',None)
    report=gate.analyze(read_text(args.text),source_path=args.text,canon_library=library,viewpoint=args.viewpoint,at=args.at,branch=getattr(args,'branch','main'),
                        profile_path=args.profile,chapter_plan=chapter_plan,provenance_path=getattr(args,'provenance',None),
                        external=not args.no_external,advanced_nlp=not args.no_advanced_nlp)
    return report,policy

def _constraints_from_report(report) -> str:
    # Raw tool messages are intentionally excluded from model reinjection.
    lines=[f'- [{d.code}] {d.instruction}' for d in compile_directives(report)]
    lines.append('- Do not optimize for the suspicion score; repair the underlying situation and preserve unaffected logic.')
    return '\n'.join(lines)

def _plan_policy(path: str | Path) -> dict: return _load_yaml(path)

def _canon_inventory(path: str | Path) -> list[dict]:
    with CanonLibrary.load(path) as lib:
        rows=lib.con.execute("SELECT id,title,disclosure_state FROM canon_entry WHERE status='active' ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def main(argv=None):
    p=argparse.ArgumentParser(prog='write-runtime',description='Deterministic bounded writing runtime')
    sp=p.add_subparsers(dest='cmd',required=True)

    b=sp.add_parser('canon-build'); b.add_argument('source'); b.add_argument('--out',default='canon/canon.sqlite3')
    c=sp.add_parser('canon'); c.add_argument('text',nargs='?'); c.add_argument('--library',default='canon/canon.sqlite3'); c.add_argument('--viewpoint'); c.add_argument('--at'); c.add_argument('--branch',default='main'); c.add_argument('--scope',choices=['writer','pov'],default='writer'); c.add_argument('--json',action='store_true')
    s=sp.add_parser('canon-search'); s.add_argument('query'); s.add_argument('--library',default='canon/canon.sqlite3'); s.add_argument('--limit',type=int,default=20)
    sh=sp.add_parser('canon-show'); sh.add_argument('id'); sh.add_argument('--library',default='canon/canon.sqlite3'); sh.add_argument('--viewpoint'); sh.add_argument('--at'); sh.add_argument('--branch',default='main'); sh.add_argument('--scope',choices=['writer','pov'],default='writer')
    cs=sp.add_parser('canon-spell-dict'); cs.add_argument('--library',default='canon/canon.sqlite3'); cs.add_argument('--out',default='config/canon-terms.txt')

    sb=sp.add_parser('state-build',help='compile replayable narrative state/invariants into SQLite'); sb.add_argument('source'); sb.add_argument('--library',default='canon/canon.sqlite3'); sb.add_argument('--out',default='state/story_state.sqlite3')
    ss=sp.add_parser('state-show',help='show deterministic state at a canon timeline point'); ss.add_argument('--state-library',default='state/story_state.sqlite3'); ss.add_argument('--library',default='canon/canon.sqlite3'); ss.add_argument('--at',required=True); ss.add_argument('--branch',default='main'); ss.add_argument('--writer-safe',action='store_true'); ss.add_argument('--json',action='store_true')
    sa=sp.add_parser('state-audit',help='run cross-record semantic consistency checks at a canon timeline point'); sa.add_argument('--state-library',default='state/story_state.sqlite3'); sa.add_argument('--library',default='canon/canon.sqlite3'); sa.add_argument('--at',required=True); sa.add_argument('--branch',default='main'); sa.add_argument('--json',action='store_true')
    sbr=sp.add_parser('state-branches',help='list temporal branches'); sbr.add_argument('--state-library',default='state/story_state.sqlite3'); sbr.add_argument('--json',action='store_true')
    shi=sp.add_parser('state-history',help='show visible event history on a branch'); shi.add_argument('--state-library',default='state/story_state.sqlite3'); shi.add_argument('--library',default='canon/canon.sqlite3'); shi.add_argument('--at',required=True); shi.add_argument('--branch',default='main'); shi.add_argument('--subject'); shi.add_argument('--writer-safe',action='store_true'); shi.add_argument('--json',action='store_true')
    sdf=sp.add_parser('state-diff',help='diff deterministic state between two branches'); sdf.add_argument('--state-library',default='state/story_state.sqlite3'); sdf.add_argument('--library',default='canon/canon.sqlite3'); sdf.add_argument('--at',required=True); sdf.add_argument('--left',required=True); sdf.add_argument('--right',required=True); sdf.add_argument('--json',action='store_true')
    cb=sp.add_parser('chronobreak',help='create a non-destructive timeline-branch YAML overlay'); cb.add_argument('--id',required=True); cb.add_argument('--at',required=True); cb.add_argument('--parent',default='main'); cb.add_argument('--kind',choices=['retcon','alternate','simulation','time_travel'],default='retcon'); cb.add_argument('--label'); cb.add_argument('--library',default='canon/canon.sqlite3'); cb.add_argument('--out',required=True); cb.add_argument('--force',action='store_true'); cb.add_argument('--json',action='store_true')

    ps=sp.add_parser('plan-schema',help='emit the strict plan JSON schema'); ps.add_argument('--json',action='store_true')
    pc=sp.add_parser('plan-check',help='mechanically validate plan schema, canon, causality and narrative state'); pc.add_argument('plan'); pc.add_argument('--library',default='canon/canon.sqlite3'); pc.add_argument('--state-library',default='state/story_state.sqlite3'); pc.add_argument('--policy',default=str(ROOT/'config'/'planning_policy.yaml')); pc.add_argument('--json',action='store_true')
    pp=sp.add_parser('plan-prompt',help='create strict architect prompt from an author brief'); pp.add_argument('brief'); pp.add_argument('--plan-id',required=True); pp.add_argument('--chapter-key',required=True); pp.add_argument('--at',required=True); pp.add_argument('--branch',default='main'); pp.add_argument('--viewpoint',required=True); pp.add_argument('--library',default='canon/canon.sqlite3'); pp.add_argument('--state-library',default='state/story_state.sqlite3'); pp.add_argument('--out',required=True); pp.add_argument('--manifest-out'); pp.add_argument('--context-mode',choices=['fresh_call','persistent_safe'],default='fresh_call')
    pa=sp.add_parser('plan-apply',help='validate request-bound plan JSON response'); pa.add_argument('--response',required=True); pa.add_argument('--manifest',required=True); pa.add_argument('--out',required=True); pa.add_argument('--json',action='store_true')
    prn=sp.add_parser('plan-repair-next',help='bounded localized plan-repair router'); prn.add_argument('plan'); prn.add_argument('--state',required=True); prn.add_argument('--library',default='canon/canon.sqlite3'); prn.add_argument('--state-library',default='state/story_state.sqlite3'); prn.add_argument('--policy',default=str(ROOT/'config'/'planning_policy.yaml')); prn.add_argument('--salvage-out'); prn.add_argument('--prompt-out'); prn.add_argument('--manifest-out'); prn.add_argument('--context-mode',choices=['fresh_call','persistent_safe'],default='fresh_call'); prn.add_argument('--json',action='store_true')
    psa=sp.add_parser('plan-salvage-apply',help='apply strict beat-cluster replacements to a plan'); psa.add_argument('--plan',required=True); psa.add_argument('--salvage',required=True); psa.add_argument('--response',required=True); psa.add_argument('--out',required=True); psa.add_argument('--json',action='store_true')
    dp=sp.add_parser('draft-prompt',help='compile an accepted plan to a writer-safe scene prompt'); dp.add_argument('plan'); dp.add_argument('--library',default='canon/canon.sqlite3'); dp.add_argument('--state-library',default='state/story_state.sqlite3'); dp.add_argument('--policy',default=str(ROOT/'config'/'planning_policy.yaml')); dp.add_argument('--out',required=True); dp.add_argument('--manifest-out',required=True); dp.add_argument('--context-mode',choices=['fresh_call','persistent_safe'],default='fresh_call')
    da=sp.add_parser('draft-apply',help='validate scene-block response and strip transport markers'); da.add_argument('--plan',required=True); da.add_argument('--manifest',required=True); da.add_argument('--response',required=True); da.add_argument('--library',default='canon/canon.sqlite3'); da.add_argument('--out',required=True); da.add_argument('--provenance-out'); da.add_argument('--json',action='store_true')
    dep=sp.add_parser('draft-epochs',help='compile a plan into disclosure epoch prompts'); dep.add_argument('plan'); dep.add_argument('--library',default='canon/canon.sqlite3'); dep.add_argument('--state-library',default='state/story_state.sqlite3'); dep.add_argument('--policy',default=str(ROOT/'config/planning_policy.yaml')); dep.add_argument('--out-dir',required=True); dep.add_argument('--manifest-out',required=True); dep.add_argument('--context-mode',choices=['fresh_call','persistent_safe'],default='fresh_call'); dep.add_argument('--json',action='store_true')
    dea=sp.add_parser('draft-epochs-apply',help='validate and assemble E###.response.txt disclosure epoch outputs'); dea.add_argument('--plan',required=True); dea.add_argument('--manifest',required=True); dea.add_argument('--responses-dir',required=True); dea.add_argument('--library',default='canon/canon.sqlite3'); dea.add_argument('--out',required=True); dea.add_argument('--provenance-out'); dea.add_argument('--json',action='store_true')

    a=sp.add_parser('analyze'); a.add_argument('text',nargs='?'); a.add_argument('--profile'); a.add_argument('--json',action='store_true')
    g=sp.add_parser('gate'); g.add_argument('text'); g.add_argument('--profile',required=True); g.add_argument('--max-warnings',type=int,default=0)
    k=sp.add_parser('calibrate'); k.add_argument('inputs',nargs='+'); k.add_argument('--name',default='custom'); k.add_argument('--out',required=True); k.add_argument('--lower',type=float,default=.10); k.add_argument('--upper',type=float,default=.90)
    d=sp.add_parser('doctor'); d.add_argument('--json',action='store_true')
    tl=sp.add_parser('tool-lock'); tl.add_argument('--out',default='config/toolchain.lock.json'); tl.add_argument('--json',action='store_true')
    tv=sp.add_parser('tool-verify'); tv.add_argument('--lock',default='config/toolchain.lock.json'); tv.add_argument('--json',action='store_true')
    te=sp.add_parser('tool-expected'); te.add_argument('--json',action='store_true')
    mv=sp.add_parser('call-manifest-verify',help='verify a prompt still matches its model-call context manifest'); mv.add_argument('--prompt',required=True); mv.add_argument('--manifest',required=True); mv.add_argument('--json',action='store_true')
    q=sp.add_parser('quality'); _add_quality_args(q)

    cc=sp.add_parser('contract-check'); cc.add_argument('kind',choices=['rewrite','gaps','plan']); cc.add_argument('response'); cc.add_argument('--source'); cc.add_argument('--gap-id',action='append',default=[]); cc.add_argument('--contract-id'); cc.add_argument('--min-word-ratio',type=float,default=.60); cc.add_argument('--max-word-ratio',type=float,default=1.80); cc.add_argument('--json',action='store_true')
    ra=sp.add_parser('rewrite-apply'); ra.add_argument('--response',required=True); ra.add_argument('--source',required=True); ra.add_argument('--manifest'); ra.add_argument('--out',required=True); ra.add_argument('--min-word-ratio',type=float,default=.60); ra.add_argument('--max-word-ratio',type=float,default=1.80); ra.add_argument('--json',action='store_true')
    rp=sp.add_parser('rewrite-prompt'); _add_quality_args(rp); rp.add_argument('--task',default='Rewrite this chapter so it passes the diagnosed deterministic constraints without damaging unaffected material.'); rp.add_argument('--plan'); rp.add_argument('--state-library',default='state/story_state.sqlite3'); rp.add_argument('--out'); rp.add_argument('--manifest-out'); rp.add_argument('--context-mode',choices=['fresh_call','persistent_safe'],default='fresh_call')
    sv=sp.add_parser('salvage-plan'); _add_quality_args(sv); sv.add_argument('--plan-out',required=True); sv.add_argument('--prompt-out',required=True); sv.add_argument('--manifest-out'); sv.add_argument('--context-mode',choices=['fresh_call','persistent_safe'],default='fresh_call')
    sa=sp.add_parser('salvage-apply'); sa.add_argument('--plan',required=True); sa.add_argument('--source',required=True); sa.add_argument('--response',required=True); sa.add_argument('--out',required=True); sa.add_argument('--json',action='store_true')
    rn=sp.add_parser('repair-next'); _add_quality_args(rn); rn.add_argument('--state',required=True); rn.add_argument('--prompt-out'); rn.add_argument('--plan-out'); rn.add_argument('--writer-plan'); rn.add_argument('--state-library',default='state/story_state.sqlite3'); rn.add_argument('--manifest-out'); rn.add_argument('--context-mode',choices=['fresh_call','persistent_safe'],default='fresh_call'); rn.add_argument('--task',default='Repair this chapter based only on the deterministic evidence below.')

    args=p.parse_args(argv)

    if args.cmd=='canon-build': print(build_canon_database(args.source,args.out)); return 0
    if args.cmd=='canon':
        with CanonLibrary.load(args.library) as lib:
            hits=lib.trigger(read_text(args.text),viewpoint=args.viewpoint,at=args.at,scope=args.scope,branch=args.branch); print(lib.to_json(hits) if args.json else lib.render(hits))
        return 0
    if args.cmd=='canon-search':
        with CanonLibrary.load(args.library) as lib: dump(lib.search(args.query,args.limit))
        return 0
    if args.cmd=='canon-show':
        with CanonLibrary.load(args.library) as lib: dump(lib.show(args.id,viewpoint=args.viewpoint,at=args.at,scope=args.scope,branch=args.branch))
        return 0
    if args.cmd=='canon-spell-dict':
        with CanonLibrary.load(args.library) as lib: terms=lib.export_spelling_terms()
        out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text('\n'.join(terms)+('\n' if terms else ''),encoding='utf-8'); print(out); return 0

    if args.cmd=='state-build': print(build_state_database(args.source,args.library,args.out)); return 0
    if args.cmd=='state-show':
        with CanonLibrary.load(args.library) as canon: ordinal=canon.timeline_ordinal(args.at)
        with StoryStateLibrary.load(args.state_library) as state: data=state.state_at(ordinal,branch=args.branch,writer_safe_only=args.writer_safe)
        dump(data,args.json); return 0
    if args.cmd=='state-audit':
        with CanonLibrary.load(args.library) as canon: ordinal=canon.timeline_ordinal(args.at)
        with StoryStateLibrary.load(args.state_library) as lib:
            data=lib.state_at(ordinal,branch=args.branch); registry=lib.subject_registry(); issues=audit_semantic_state(data,registry=registry); inv=lib.check_invariants(data,ordinal,branch=args.branch)
        result={'pass':not any(x.hard for x in issues) and not any(x.severity in {'hard','error'} for x in inv),
                'semantic_issues':[x.as_dict() for x in issues],'invariant_issues':[x.as_dict() for x in inv],
                'subjects':registry}
        dump(result,args.json); return 0 if result['pass'] else 2
    if args.cmd=='state-branches':
        with StoryStateLibrary.load(args.state_library) as lib: dump(lib.branches(),args.json)
        return 0
    if args.cmd=='state-history':
        with CanonLibrary.load(args.library) as canon: ordinal=canon.timeline_ordinal(args.at)
        with StoryStateLibrary.load(args.state_library) as lib: data=lib.history(branch=args.branch,through_ordinal=ordinal,subject=args.subject,writer_safe_only=args.writer_safe)
        dump(data,args.json); return 0
    if args.cmd=='state-diff':
        with CanonLibrary.load(args.library) as canon: ordinal=canon.timeline_ordinal(args.at)
        with StoryStateLibrary.load(args.state_library) as lib: data=lib.diff(left_branch=args.left,right_branch=args.right,ordinal=ordinal)
        dump(data,args.json); return 0

    if args.cmd=='chronobreak':
        out=Path(args.out)
        if out.exists() and not args.force:
            dump({'valid':False,'errors':[f'refusing to overwrite existing chronobreak overlay: {out}']},args.json); return 2
        with CanonLibrary.load(args.library) as canon:
            try: fork_ordinal=canon.timeline_ordinal(args.at)
            except Exception as exc:
                dump({'valid':False,'errors':[str(exc)]},args.json); return 2
            if not canon.branch_exists(args.parent):
                dump({'valid':False,'errors':[f'unknown parent branch: {args.parent}']},args.json); return 2
            if canon.branch_exists(args.id):
                dump({'valid':False,'errors':[f'branch already exists in compiled canon: {args.id}']},args.json); return 2
            parent=canon.branch_info(args.parent); parent_fork=parent.get('fork_ordinal')
            if parent_fork is not None and int(fork_ordinal) < int(parent_fork):
                dump({'valid':False,'errors':[f'chronobreak {args.id} forks before parent {args.parent} exists']},args.json); return 2
        payload={'timeline_branches':[{'id':args.id,'parent':args.parent,'fork_at':args.at,'kind':args.kind,'label':args.label or f'{args.kind} branch from {args.parent} at {args.at}','writer_safe':True}]}
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(yaml.safe_dump(payload,sort_keys=False,allow_unicode=True),encoding='utf-8')
        dump({'valid':True,'out':str(out),'branch_id':args.id,'parent':args.parent,'fork_at':args.at,'fork_ordinal':fork_ordinal,'next':['canon-build','state-build']},args.json); return 0

    if args.cmd=='plan-schema': dump(plan_schema(),args.json); return 0
    if args.cmd=='plan-check':
        gate=PlanGate(_plan_policy(args.policy)); _plan,report=gate.validate_file(args.plan,canon_library=args.library,state_library=args.state_library)
        dump(report.as_dict(),args.json); return 0 if report.passed else 2
    if args.cmd=='plan-prompt':
        mode=normalize_context_mode(args.context_mode)
        brief=read_text(args.brief); seed={'brief_sha256':sha256(brief.encode()).hexdigest(),'plan_id':args.plan_id,'chapter_key':args.chapter_key,'at':args.at,'timeline_branch':args.branch,'viewpoint':args.viewpoint}
        canon_context=[]; planning_state={}; inventory=[]
        with CanonLibrary.load(args.library) as canon:
            ordinal=canon.timeline_ordinal(args.at)
            scope='writer' if mode=='fresh_call' else 'pov'
            hits=canon.trigger(brief,viewpoint=args.viewpoint,at=args.at,scope=scope,branch=args.branch)
            canon_context=[{'id':h.id,'matched':list(h.matched),'payload':h.payload} for h in hits]
            if mode=='fresh_call':
                inventory=_canon_inventory(args.library)
        if args.state_library and Path(args.state_library).exists():
            with StoryStateLibrary.load(args.state_library) as state:
                planning_state=state.state_at(ordinal,branch=args.branch,writer_safe_only=(mode=='persistent_safe'))
        seed['planning_context_sha256']=sha256(json.dumps({'canon':canon_context,'state':planning_state,'mode':mode},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        cid=sha256(json.dumps(seed,sort_keys=True).encode()).hexdigest()[:20]
        prompt=plan_generation_prompt(brief=brief,plan_id=args.plan_id,chapter_key=args.chapter_key,timeline_key=args.at,timeline_branch=args.branch,viewpoint=args.viewpoint,contract_id=cid,canon_inventory=inventory,author_canon_context=canon_context,author_state=planning_state,context_mode=mode)
        Path(args.out).write_text(prompt,encoding='utf-8')
        call=make_call_manifest(phase='plan_generate',prompt=prompt,context_mode=mode,contract_id=cid,contains_author_only=(mode=='fresh_call'),upstream={'brief_sha256':seed['brief_sha256'],'planning_context_sha256':seed['planning_context_sha256']})
        manifest={**call.as_dict(),**seed}
        mpath=Path(args.manifest_out or (str(args.out)+'.manifest.json')); mpath.write_text(json.dumps(manifest,indent=2),encoding='utf-8'); print(args.out); return 0
    if args.cmd=='plan-apply':
        manifest=json.loads(Path(args.manifest).read_text(encoding='utf-8')); result=validate_plan_response(read_text(args.response),contract_id=manifest['contract_id'])
        if not result.valid or result.payload is None: dump(result.as_dict(),args.json); return 2
        try: plan=ChapterPlan.model_validate(json.loads(result.payload))
        except Exception as exc: dump({'valid':False,'errors':[str(exc)]},args.json); return 2
        fixed={'plan_id':manifest['plan_id'],'chapter_key':manifest['chapter_key'],'timeline_key':manifest['at'],'timeline_branch':manifest.get('timeline_branch','main'),'viewpoint':manifest['viewpoint']}
        for key,val in fixed.items():
            if getattr(plan,key)!=val: dump({'valid':False,'errors':[f'{key} changed from fixed manifest value']},args.json); return 2
        Path(args.out).write_text(json.dumps(plan.model_dump(mode='json'),indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); dump({'valid':True,'out':args.out},args.json); return 0
    if args.cmd=='plan-repair-next':
        mode=normalize_context_mode(args.context_mode)
        policy=_plan_policy(args.policy); plan=load_plan(args.plan); report=PlanGate(policy).validate(plan,canon_library=args.library,state_library=args.state_library)
        spath=Path(args.state); state=json.loads(spath.read_text()) if spath.exists() else None; state=plan_repair_transition(state,report,plan,policy,context_mode=mode); spath.parent.mkdir(parents=True,exist_ok=True); spath.write_text(json.dumps(state,indent=2),encoding='utf-8')
        out={'action':state['action'],'state':str(spath),'gate':report.as_dict(),'context_mode':mode}
        if state['action']=='repair_beats':
            salvage=make_plan_salvage(plan,report,policy)
            if salvage.abort: out['action']='human_review'; out['salvage_abort']=salvage.abort_reason; state.update(action='human_review',done=True,reason=salvage.abort_reason); spath.write_text(json.dumps(state,indent=2),encoding='utf-8')
            else:
                if args.salvage_out: Path(args.salvage_out).write_text(json.dumps(salvage.as_dict(),indent=2,ensure_ascii=False),encoding='utf-8'); out['salvage']=args.salvage_out
                if args.prompt_out:
                    prompt=plan_salvage_prompt(salvage,report=report,context_mode=mode); Path(args.prompt_out).write_text(prompt,encoding='utf-8'); out['prompt']=args.prompt_out
                    call=make_call_manifest(phase='plan_salvage',prompt=prompt,context_mode=mode,contract_id=salvage.contract_id,contains_author_only=(mode=='fresh_call'),upstream={'source_plan_sha256':salvage.source_sha256})
                    mpath=args.manifest_out or (str(args.prompt_out)+'.manifest.json'); Path(mpath).write_text(json.dumps(call.as_dict(),indent=2),encoding='utf-8'); out['manifest']=mpath
        elif state['action']=='rewrite_plan':
            plan_hash=sha256(json.dumps(plan.model_dump(mode='json'),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            cid=sha256((plan_hash+json.dumps({'history':state.get('history',[]),'action':'rewrite_plan'},sort_keys=True)).encode()).hexdigest()[:20]
            if args.prompt_out:
                prompt=plan_rewrite_prompt(plan,report,contract_id=cid,context_mode=mode); Path(args.prompt_out).write_text(prompt,encoding='utf-8'); out['prompt']=args.prompt_out
                call=make_call_manifest(phase='plan_rewrite',prompt=prompt,context_mode=mode,contract_id=cid,contains_author_only=(mode=='fresh_call'),upstream={'source_plan_sha256':plan_hash})
                manifest={**call.as_dict(),'plan_id':plan.plan_id,'chapter_key':plan.chapter_key,'at':plan.timeline_key,'timeline_branch':plan.timeline_branch,'viewpoint':plan.viewpoint,'source_plan_sha256':plan_hash}
                mpath=args.manifest_out or (str(args.prompt_out)+'.manifest.json'); Path(mpath).write_text(json.dumps(manifest,indent=2),encoding='utf-8'); out['manifest']=mpath
        dump(out,args.json); return 3 if out['action']=='human_review' else 0
    if args.cmd=='plan-salvage-apply':
        plan=load_plan(args.plan); data=json.loads(Path(args.salvage).read_text(encoding='utf-8'))
        from .planning import PlanGap, PlanSalvage
        salvage=PlanSalvage(data['source_sha256'],data['contract_id'],[PlanGap(g['id'],g['scene_id'],tuple(g['beat_ids']),g.get('before_beat'),tuple(g.get('removed_beats',[])),g.get('after_beat'),tuple(g.get('directives',[]))) for g in data['gaps']],float(data['cull_fraction']),bool(data.get('abort',False)),data.get('abort_reason'))
        source_hash=sha256(json.dumps(plan.model_dump(mode='json'),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if source_hash!=salvage.source_sha256: dump({'valid':False,'errors':['plan salvage is stale']},args.json); return 2
        rebuilt,result=apply_plan_salvage(plan,salvage,read_text(args.response))
        if rebuilt is None: dump(result,args.json); return 2
        Path(args.out).write_text(json.dumps(rebuilt.model_dump(mode='json'),indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); dump({'valid':True,'out':args.out},args.json); return 0
    if args.cmd=='draft-prompt':
        mode=normalize_context_mode(args.context_mode)
        policy=_plan_policy(args.policy); plan=load_plan(args.plan); report=PlanGate(policy).validate(plan,canon_library=args.library,state_library=args.state_library)
        if not report.passed: dump({'valid':False,'errors':['plan does not pass deterministic gate'],'gate':report.as_dict()},True); return 2
        epochs=compile_disclosure_epochs(plan,canon_library=args.library,state_library=args.state_library)
        if len(epochs)>1:
            dump({'valid':False,'errors':['plan contains an intra-chapter disclosure boundary; monolithic drafting is refused. Use draft-epochs with fresh_call.'],'epoch_count':len(epochs)},True); return 2
        surface=epochs[0].writer_surface; plan_hash=sha256(json.dumps(plan.model_dump(mode='json'),sort_keys=True,ensure_ascii=False).encode()).hexdigest(); cid=sha256((plan_hash+json.dumps(surface,sort_keys=True,ensure_ascii=False)).encode()).hexdigest()[:20]
        prompt=scene_draft_prompt(plan,surface,contract_id=cid); Path(args.out).write_text(prompt,encoding='utf-8')
        call=make_call_manifest(phase='draft_generate',prompt=prompt,context_mode=mode,contract_id=cid,contains_author_only=False,upstream={'plan_sha256':plan_hash})
        manifest={**call.as_dict(),'plan_sha256':plan_hash,'plan_id':plan.plan_id}; Path(args.manifest_out).write_text(json.dumps(manifest,indent=2),encoding='utf-8'); print(args.out); return 0
    if args.cmd=='draft-epochs':
        mode=normalize_context_mode(args.context_mode)
        policy=_plan_policy(args.policy); plan=load_plan(args.plan); report=PlanGate(policy).validate(plan,canon_library=args.library,state_library=args.state_library)
        if not report.passed: dump({'valid':False,'errors':['plan does not pass deterministic gate'],'gate':report.as_dict()},args.json); return 2
        epochs=compile_disclosure_epochs(plan,canon_library=args.library,state_library=args.state_library)
        if len(epochs)>1 and mode!='fresh_call':
            dump({'valid':False,'errors':['multi-epoch disclosure isolation requires fresh_call; a persistent context cannot forget later-unlocked facts during backward repair.'],'epoch_count':len(epochs)},args.json); return 2
        out_dir=Path(args.out_dir); out_dir.mkdir(parents=True,exist_ok=True)
        plan_hash=sha256(json.dumps(plan.model_dump(mode='json'),sort_keys=True,ensure_ascii=False).encode()).hexdigest(); rows=[]
        for epoch in epochs:
            seed=json.dumps({'plan_sha256':plan_hash,'epoch':epoch.as_dict()},sort_keys=True,ensure_ascii=False)
            cid=sha256(seed.encode()).hexdigest()[:20]; prompt=epoch_draft_prompt(epoch,contract_id=cid)
            prompt_file=out_dir/f'{epoch.id}.prompt.txt'; prompt_file.write_text(prompt,encoding='utf-8')
            call=make_call_manifest(phase='draft_epoch',prompt=prompt,context_mode=mode,contract_id=cid,contains_author_only=False,upstream={'plan_sha256':plan_hash,'epoch_id':epoch.id})
            rows.append({'epoch':epoch.as_dict(),'contract_id':cid,'prompt_file':prompt_file.name,'call_manifest':call.as_dict()})
        manifest={'version':1,'plan_sha256':plan_hash,'plan_id':plan.plan_id,'context_mode':mode,'epoch_count':len(rows),'epochs':rows}
        Path(args.manifest_out).write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
        dump({'valid':True,'epoch_count':len(rows),'out_dir':str(out_dir),'manifest':args.manifest_out},args.json); return 0

    if args.cmd=='draft-epochs-apply':
        plan=load_plan(args.plan); manifest=json.loads(Path(args.manifest).read_text(encoding='utf-8')); plan_hash=sha256(json.dumps(plan.model_dump(mode='json'),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if plan_hash!=manifest.get('plan_sha256'): dump({'valid':False,'errors':['draft epoch manifest is stale']},args.json); return 2
        results=[]; response_dir=Path(args.responses_dir); errors=[]
        for row in manifest.get('epochs',[]):
            e=row['epoch']; epoch=DraftEpoch(e['id'],int(e['index']),tuple((x['scene_id'],tuple(x['beat_ids'])) for x in e['scene_beats']),tuple(e.get('unlocked_facts',[])),tuple(e.get('locked_facts',[])),tuple(e.get('locked_phrases',[])),e['writer_surface'])
            response_path=response_dir/f'{epoch.id}.response.txt'
            if not response_path.exists(): errors.append(f'missing response file {response_path.name}'); continue
            beats,result=validate_epoch_draft(plan,epoch,response_path.read_text(encoding='utf-8'),contract_id=row['contract_id'],canon_library=args.library)
            if beats is None: errors.extend(result['errors']); continue
            results.append(beats)
        if errors: dump({'valid':False,'errors':errors},args.json); return 2
        chapter,result=assemble_epoch_drafts(plan,results)
        if chapter is None: dump(result,args.json); return 2
        Path(args.out).write_text(chapter,encoding='utf-8'); prov=args.provenance_out or (str(args.out)+'.provenance.json'); Path(prov).write_text(json.dumps(result['provenance'],indent=2,ensure_ascii=False),encoding='utf-8')
        dump({'valid':True,'out':args.out,'provenance_out':prov,'epoch_count':manifest.get('epoch_count'),'beat_count':result.get('beat_count')},args.json); return 0

    if args.cmd=='draft-apply':
        plan=load_plan(args.plan); manifest=json.loads(Path(args.manifest).read_text()); plan_hash=sha256(json.dumps(plan.model_dump(mode='json'),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if plan_hash!=manifest['plan_sha256']: dump({'valid':False,'errors':['draft manifest is stale']},args.json); return 2
        chapter,result=validate_scene_draft(plan,read_text(args.response),contract_id=manifest['contract_id'],canon_library=args.library)
        if chapter is None: dump(result,args.json); return 2
        Path(args.out).write_text(chapter,encoding='utf-8')
        prov_path=args.provenance_out or (str(args.out)+'.provenance.json')
        Path(prov_path).write_text(json.dumps(result.get('provenance',{}),indent=2,ensure_ascii=False),encoding='utf-8')
        out_result={k:v for k,v in result.items() if k!='provenance'}
        dump({'valid':True,'out':args.out,'provenance_out':prov_path,**out_result},args.json); return 0

    if args.cmd=='analyze':
        prof=load_profile(args.profile) if args.profile else None; r=ProseAnalyzer().analyze(read_text(args.text),prof); dump(r.as_dict(),args.json); return 0
    if args.cmd=='gate':
        prof=load_profile(args.profile); r=ProseAnalyzer().analyze(read_text(args.text),prof); warnings=[x for x in r.flags if x['severity']=='warn']; passed=bool(r.profile_fit and r.profile_fit['pass']) and len(warnings)<=args.max_warnings; dump({'pass':passed,'warning_count':len(warnings),'profile_fit':r.profile_fit,'flags':r.flags}); return 0 if passed else 2
    if args.cmd=='calibrate':
        texts=[]
        for item in args.inputs:
            pth=Path(item); texts.extend(x.read_text(encoding='utf-8') for x in sorted(pth.glob('*.txt'))) if pth.is_dir() else texts.append(pth.read_text(encoding='utf-8'))
        profile=calibrate(texts,args.name,args.lower,args.upper); Path(args.out).write_text(yaml.safe_dump(profile,sort_keys=False),encoding='utf-8'); print(args.out); return 0
    if args.cmd=='doctor': dump([x.as_dict() for x in doctor(ROOT)],args.json); return 0
    if args.cmd=='tool-lock': data=write_lock(ROOT,args.out); dump({'written':args.out,'snapshot':data},args.json); return 0
    if args.cmd=='tool-verify': result=verify_lock(ROOT,args.lock); dump(result,args.json); return 0 if result['ok'] else 2
    if args.cmd=='tool-expected': result=expected_version_report(ROOT); dump(result,args.json); return 0 if result['ok'] else 2
    if args.cmd=='call-manifest-verify': result=verify_prompt_manifest(read_text(args.prompt),json.loads(Path(args.manifest).read_text(encoding='utf-8'))); dump(result,args.json); return 0 if result['ok'] else 2
    if args.cmd=='quality': report,_=_quality(args); dump(report.as_dict(),args.json); return 0 if report.passed else 2

    if args.cmd=='contract-check':
        response=read_text(args.response)
        if args.kind=='rewrite': result=validate_rewrite_response(response,source_text=read_text(args.source) if args.source else None,min_word_ratio=args.min_word_ratio,max_word_ratio=args.max_word_ratio,contract_id=args.contract_id)
        elif args.kind=='plan': result=validate_plan_response(response,contract_id=args.contract_id)
        else: result=parse_gap_response(response,args.gap_id)
        dump(result.as_dict(),args.json); return 0 if result.valid else 2
    if args.cmd=='rewrite-apply':
        cid=None
        if args.manifest:
            manifest=json.loads(Path(args.manifest).read_text()); actual=sha256(Path(args.source).read_bytes()).hexdigest()
            if actual!=manifest['source_sha256']: dump({'valid':False,'errors':['rewrite manifest is stale']},args.json); return 2
            cid=manifest['contract_id']
        result=validate_rewrite_response(read_text(args.response),source_text=read_text(args.source),min_word_ratio=args.min_word_ratio,max_word_ratio=args.max_word_ratio,contract_id=cid)
        if not result.valid or result.payload is None: dump(result.as_dict(),args.json); return 2
        Path(args.out).write_text(result.payload.rstrip()+'\n',encoding='utf-8'); dump({'valid':True,'out':args.out,'contract':result.as_dict()},args.json); return 0
    if args.cmd=='rewrite-prompt':
        report,_=_quality(args); plan_surface=None
        if args.plan:
            plan=load_plan(args.plan); ppol=_plan_policy(ROOT/'config'/'planning_policy.yaml'); preport=PlanGate(ppol).validate(plan,canon_library=args.library,state_library=args.state_library)
            if not preport.passed: dump({'valid':False,'errors':['writer plan is invalid'],'plan_gate':preport.as_dict()},True); return 2
            plan_surface=writer_plan_surface(plan,canon_library=args.library,state_library=args.state_library)
        packet=make_repair_packet(read_text(args.text),report,action='rewrite',writer_plan=plan_surface,metadata={'viewpoint':args.viewpoint,'at':args.at})
        source=read_text(args.text); shown=redact_unrevealed_canon(source,report); prompt=render_rewrite_prompt(packet,source,task=args.task,redacted_source_text=shown)
        if args.out: Path(args.out).write_text(prompt,encoding='utf-8')
        else: print(prompt)
        if args.manifest_out:
            call=make_call_manifest(phase='prose_rewrite',prompt=prompt,context_mode=args.context_mode,contract_id=packet.contract_id,contains_author_only=False,upstream={'source_sha256':packet.source_sha256})
            Path(args.manifest_out).write_text(json.dumps({**packet.public_dict(),'call':call.as_dict()},indent=2,ensure_ascii=False),encoding='utf-8')
        return 0
    if args.cmd=='salvage-plan':
        report,policy=_quality(args); plan=make_salvage_plan(read_text(args.text),report,policy); Path(args.plan_out).write_text(json.dumps(plan.as_dict(),indent=2,ensure_ascii=False),encoding='utf-8')
        if plan.abort: Path(args.prompt_out).write_text(f'SALVAGE ABORTED: {plan.abort_reason}\n',encoding='utf-8'); dump(plan.as_dict(),args.json); return 3
        prompt=salvage_prompt(plan,global_constraints=_constraints_from_report(report)); Path(args.prompt_out).write_text(prompt,encoding='utf-8')
        if args.manifest_out:
            call=make_call_manifest(phase='prose_salvage',prompt=prompt,context_mode=args.context_mode,contains_author_only=False,upstream={'source_sha256':plan.source_sha256})
            Path(args.manifest_out).write_text(json.dumps(call.as_dict(),indent=2),encoding='utf-8')
        dump(plan.as_dict(),args.json); return 0
    if args.cmd=='salvage-apply':
        plan=salvage_plan_from_dict(json.loads(Path(args.plan).read_text(encoding='utf-8'))); actual=sha256(Path(args.source).read_bytes()).hexdigest()
        if actual!=plan.source_sha256: dump({'valid':False,'errors':[f'salvage plan is stale: expected {plan.source_sha256}, got {actual}']},args.json); return 2
        rebuilt,result=apply_gap_response(plan,read_text(args.response))
        if rebuilt is None: dump(result,args.json); return 2
        Path(args.out).write_text(rebuilt,encoding='utf-8'); dump({'valid':True,'out':args.out,'contract':result},args.json); return 0
    if args.cmd=='repair-next':
        report,policy=_quality(args); source=read_text(args.text); spath=Path(args.state); state=json.loads(spath.read_text()) if spath.exists() else None; state=repair_state_transition(state,report=report,candidate_text=source,policy=policy,context_mode=args.context_mode); spath.parent.mkdir(parents=True,exist_ok=True); spath.write_text(json.dumps(state,indent=2,ensure_ascii=False),encoding='utf-8'); action=state['action']; out={'action':action,'state':str(spath),'gate':report.as_dict()}
        plan_surface=None
        if args.writer_plan:
            wplan=load_plan(args.writer_plan); ppol=_plan_policy(ROOT/'config'/'planning_policy.yaml'); preport=PlanGate(ppol).validate(wplan,canon_library=args.library,state_library=args.state_library)
            if not preport.passed: out={'action':'human_review','state':str(spath),'reason':'writer plan failed deterministic gate','plan_gate':preport.as_dict()}; dump(out,args.json); return 3
            plan_surface=writer_plan_surface(wplan,canon_library=args.library,state_library=args.state_library)
        if action=='rewrite' and args.prompt_out:
            packet=make_repair_packet(source,report,action='rewrite',writer_plan=plan_surface,metadata={'viewpoint':args.viewpoint,'at':args.at}); shown=redact_unrevealed_canon(source,report); Path(args.prompt_out).write_text(render_rewrite_prompt(packet,source,task=args.task,redacted_source_text=shown),encoding='utf-8'); out['prompt']=args.prompt_out
            mpath=args.manifest_out or (str(args.prompt_out)+'.manifest.json'); call=make_call_manifest(phase='prose_rewrite',prompt=Path(args.prompt_out).read_text(encoding='utf-8'),context_mode=args.context_mode,contract_id=packet.contract_id,contains_author_only=False,upstream={'source_sha256':packet.source_sha256}); Path(mpath).write_text(json.dumps({**packet.public_dict(),'call':call.as_dict()},indent=2,ensure_ascii=False),encoding='utf-8'); out['manifest']=mpath
        elif action=='salvage':
            plan=make_salvage_plan(source,report,policy)
            if args.plan_out: Path(args.plan_out).write_text(json.dumps(plan.as_dict(),indent=2,ensure_ascii=False),encoding='utf-8'); out['plan']=args.plan_out
            if args.prompt_out and not plan.abort:
                prompt=salvage_prompt(plan,global_constraints=_constraints_from_report(report)); Path(args.prompt_out).write_text(prompt,encoding='utf-8'); out['prompt']=args.prompt_out
                mpath=args.manifest_out or (str(args.prompt_out)+'.manifest.json'); call=make_call_manifest(phase='prose_salvage',prompt=prompt,context_mode=args.context_mode,contains_author_only=False,upstream={'source_sha256':plan.source_sha256}); Path(mpath).write_text(json.dumps(call.as_dict(),indent=2),encoding='utf-8'); out['manifest']=mpath
            if plan.abort: out['salvage_abort']=plan.abort_reason
        dump(out,args.json); return 3 if action=='human_review' else 0

    return 1

if __name__=='__main__': raise SystemExit(main())
