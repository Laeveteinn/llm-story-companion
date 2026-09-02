from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, asdict
import json, math, re, statistics, yaml
from pathlib import Path
from .textutil import words, sentences, paragraphs, syllables, msttr, shannon_entropy, mean, stdev

WEAK_VERBS={"is","are","was","were","be","been","being","seem","seems","seemed","feel","felt","look","looked","looks","get","got","gets"}
FILTER_PHRASES=("i saw","i heard","i felt","i noticed","i realized","i wondered","i knew","he saw","she saw","they saw","he felt","she felt","they felt")
SUBORDINATORS={"although","because","while","when","if","unless","until","since","though","whereas","before","after","once","whether"}

@dataclass
class ProseReport:
    metrics: dict
    flags: list[dict]
    profile_fit: dict|None = None
    def as_dict(self): return asdict(self)

class ProseAnalyzer:
    def analyze(self,text:str,profile:dict|None=None)->ProseReport:
        toks=words(text); lower=[x.lower() for x in toks]; sents=sentences(text); paras=paragraphs(text)
        sw=[len(words(s)) for s in sents if words(s)]; pw=[len(words(p)) for p in paras if words(p)]
        n=max(1,len(toks)); ns=max(1,len(sents)); syl=sum(syllables(w) for w in toks)
        starts=[]
        for s in sents:
            w=[x.lower() for x in words(s)]; starts.append(" ".join(w[:2]))
        start_rep=sum(v-1 for v in Counter(starts).values() if v>1)/ns
        bigrams=Counter(zip(lower,lower[1:])); repeated_bigrams=sum(v-1 for v in bigrams.values() if v>1)/max(1,len(lower)-1)
        dialogue_words=sum(len(words(x)) for x in re.findall(r'[“"]([^”"]+)[”"]',text))
        adverbs=sum(1 for w in lower if len(w)>4 and w.endswith("ly"))
        weak=sum(1 for w in lower if w in WEAK_VERBS)
        filter_count=sum(text.lower().count(x) for x in FILTER_PHRASES)
        sub=sum(1 for w in lower if w in SUBORDINATORS)
        emdash=text.count("—"); semicolon=text.count(";"); colon=text.count(":")
        sentence_cv=stdev(sw)/mean(sw) if mean(sw) else 0
        short=sum(x<=7 for x in sw)/ns; long=sum(x>=30 for x in sw)/ns
        reading_ease=206.835-1.015*(len(toks)/ns)-84.6*(syl/n)
        grade=.39*(len(toks)/ns)+11.8*(syl/n)-15.59
        metrics={
          "word_count":len(toks),"sentence_count":len(sents),"paragraph_count":len(paras),
          "sentence_words_mean":round(mean(sw),3),"sentence_words_stdev":round(stdev(sw),3),"sentence_length_cv":round(sentence_cv,3),
          "short_sentence_ratio":round(short,3),"long_sentence_ratio":round(long,3),"paragraph_words_mean":round(mean(pw),3),
          "msttr_50":round(msttr(toks),3),"lexical_entropy_bits":round(shannon_entropy(toks),3),
          "dialogue_word_ratio":round(dialogue_words/n,3),"adverb_ratio":round(adverbs/n,4),"weak_verb_ratio":round(weak/n,4),
          "filter_phrase_per_1k":round(filter_count/n*1000,3),"subordinator_per_sentence":round(sub/ns,3),
          "repeated_bigram_ratio":round(repeated_bigrams,4),"repeated_sentence_start_ratio":round(start_rep,4),
          "emdash_per_1k":round(emdash/n*1000,3),"semicolon_per_1k":round(semicolon/n*1000,3),"colon_per_1k":round(colon/n*1000,3),
          "flesch_reading_ease":round(reading_ease,2),"flesch_kincaid_grade":round(grade,2)
        }
        flags=self._flags(metrics)
        fit=self._fit(metrics,profile) if profile else None
        return ProseReport(metrics,flags,fit)

    def _flags(self,m):
        flags=[]
        def add(code,severity,msg,metric): flags.append({"code":code,"severity":severity,"metric":metric,"message":msg})
        if m["sentence_length_cv"]<.35 and m["sentence_count"]>=6: add("low_sentence_variation","warn","Sentence lengths are unusually uniform; inspect cadence for metronomic rhythm.","sentence_length_cv")
        if m["repeated_sentence_start_ratio"]>.18: add("repeated_openings","warn","Many sentences begin with the same one/two-word pattern.","repeated_sentence_start_ratio")
        if m["repeated_bigram_ratio"]>.10: add("phrase_repetition","warn","Repeated adjacent-word patterns are dense enough to inspect.","repeated_bigram_ratio")
        if m["filter_phrase_per_1k"]>5: add("filtering","info","Perception/cognition filter phrases are frequent; inspect whether some can become direct experience.","filter_phrase_per_1k")
        if m["adverb_ratio"]>.035: add("adverb_density","info","-ly adverb density is high; this is a review signal, not an automatic defect.","adverb_ratio")
        if m["weak_verb_ratio"]>.10: add("weak_verb_density","info","Copular/weak-verb density is high; inspect static passages.","weak_verb_ratio")
        if m["long_sentence_ratio"]>.35: add("long_sentence_load","info","A large share of sentences exceed 30 words.","long_sentence_ratio")
        return flags

    def _fit(self,m,profile):
        metrics=profile.get("metrics",{})
        details={}; penalties=[]
        for name,bounds in metrics.items():
            if name not in m: continue
            x=float(m[name]); lo=bounds.get("min"); hi=bounds.get("max"); weight=float(bounds.get("weight",1))
            if lo is not None and x<float(lo):
                scale=max(abs(float(lo)),1.0); d=(float(lo)-x)/scale; status="low"
            elif hi is not None and x>float(hi):
                scale=max(abs(float(hi)),1.0); d=(x-float(hi))/scale; status="high"
            else: d=0; status="in_range"
            p=min(1.0,d)*weight; penalties.append(p)
            details[name]={"value":x,"status":status,"range":[lo,hi],"weight":weight,"penalty":round(p,4)}
        total_weight=sum(float(v.get("weight",1)) for v in metrics.values()) or 1
        score=max(0,100*(1-sum(penalties)/total_weight))
        return {"profile":profile.get("name","unnamed"),"fit_score":round(score,1),"pass":score>=float(profile.get("pass_score",80)),"details":details,
                "warning":"Fit score measures conformance to configured metric bands, not literary quality."}

def load_profile(path:str|Path): return yaml.safe_load(Path(path).read_text(encoding="utf-8"))

def calibrate(texts:list[str],name="custom",lower=.10,upper=.90):
    a=ProseAnalyzer(); reports=[a.analyze(t).metrics for t in texts if len(words(t))>=100]
    if not reports: raise ValueError("Need at least one sample with 100+ words")
    keys=[k for k,v in reports[0].items() if isinstance(v,(int,float)) and k not in {"word_count","sentence_count","paragraph_count"}]
    def q(vals,p):
        vals=sorted(vals); pos=(len(vals)-1)*p; lo=math.floor(pos); hi=math.ceil(pos)
        return vals[lo] if lo==hi else vals[lo]+(vals[hi]-vals[lo])*(pos-lo)
    metric={}
    for k in keys:
        vals=[float(r[k]) for r in reports]
        metric[k]={"min":round(q(vals,lower),4),"max":round(q(vals,upper),4),"weight":1}
    return {"name":name,"pass_score":80,"calibration":{"documents":len(reports),"quantiles":[lower,upper]},"metrics":metric}
