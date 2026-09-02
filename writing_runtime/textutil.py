from __future__ import annotations
import math, re, statistics
from collections import Counter
WORD_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
SENTENCE_RE = re.compile(r"(?<=[.!?])(?:[\"'”’)]*)\s+")

def words(text: str) -> list[str]:
    return WORD_RE.findall(text)

def sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text: return []
    return [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]

def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]

def normalize_phrase(s: str) -> str:
    return " ".join(w.lower().replace("’", "'") for w in words(s))

def syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w: return 0
    if len(w) <= 3: return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    groups = re.findall(r"[aeiouy]+", w)
    return max(1, len(groups))

def mean(xs): return statistics.mean(xs) if xs else 0.0
def stdev(xs): return statistics.pstdev(xs) if len(xs) > 1 else 0.0

def msttr(tokens: list[str], window: int = 50) -> float:
    t = [x.lower() for x in tokens]
    if not t: return 0.0
    if len(t) < window: return len(set(t))/len(t)
    vals=[]
    for i in range(0, len(t)-window+1, window):
        chunk=t[i:i+window]; vals.append(len(set(chunk))/window)
    return mean(vals)

def shannon_entropy(tokens: list[str]) -> float:
    if not tokens: return 0.0
    c=Counter(x.lower() for x in tokens); n=len(tokens)
    return -sum((v/n)*math.log2(v/n) for v in c.values())
