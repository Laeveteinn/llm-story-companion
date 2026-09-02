from __future__ import annotations

from collections import Counter
import math
from typing import Any

from .evidence import ToolStatus
from .textutil import words


def optional_language_metrics(text: str) -> tuple[dict[str, Any], list[ToolStatus]]:
    """Extract deterministic metrics from optional mature libraries.

    Failure is reported as capability status instead of breaking the core runtime.
    """
    metrics: dict[str, Any] = {}
    statuses: list[ToolStatus] = []

    try:
        import cmudict
        pronunciations = cmudict.dict()
        stresses = []
        covered = 0
        for token in words(text):
            entries = pronunciations.get(token.lower())
            if not entries:
                continue
            covered += 1
            phones = entries[0]
            stresses.extend(int(ch[-1]) for ch in phones if ch and ch[-1].isdigit())
        metrics["cmudict_coverage"] = round(covered / max(1, len(words(text))), 4)
        if stresses:
            metrics["stress_primary_ratio"] = round(sum(s == 1 for s in stresses) / len(stresses), 4)
            metrics["stress_secondary_ratio"] = round(sum(s == 2 for s in stresses) / len(stresses), 4)
        statuses.append(ToolStatus("cmudict", True, getattr(cmudict, "__version__", "installed")))
    except Exception as exc:
        statuses.append(ToolStatus("cmudict", False, detail=str(exc)))

    try:
        from wordfreq import zipf_frequency
        vals = [zipf_frequency(w.lower(), "en") for w in words(text) if w.isalpha()]
        if vals:
            metrics["wordfreq_zipf_mean"] = round(sum(vals) / len(vals), 4)
            metrics["wordfreq_rare_ratio_lt3"] = round(sum(v < 3 for v in vals) / len(vals), 4)
            metrics["wordfreq_very_rare_ratio_lt2"] = round(sum(v < 2 for v in vals) / len(vals), 4)
        statuses.append(ToolStatus("wordfreq", True, "installed"))
    except Exception as exc:
        statuses.append(ToolStatus("wordfreq", False, detail=str(exc)))

    try:
        import spacy
        try:
            nlp = spacy.load("en_core_web_sm")
        except Exception as exc:
            statuses.append(ToolStatus("spacy:en_core_web_sm", False, detail=str(exc)))
        else:
            doc = nlp(text)
            deps = []
            depths = []
            for token in doc:
                if token.is_space:
                    continue
                if token.head.i != token.i:
                    deps.append(abs(token.i - token.head.i))
                d = 0; cur = token; seen = set()
                while cur.head.i != cur.i and cur.i not in seen and d < 64:
                    seen.add(cur.i); cur = cur.head; d += 1
                depths.append(d)
            if deps:
                metrics["spacy_dependency_distance_mean"] = round(sum(deps) / len(deps), 4)
            if depths:
                metrics["spacy_dependency_depth_mean"] = round(sum(depths) / len(depths), 4)
                metrics["spacy_dependency_depth_max"] = max(depths)
            pos = Counter(t.pos_ for t in doc if not t.is_space)
            total = sum(pos.values()) or 1
            metrics["spacy_pos_ratios"] = {k: round(v / total, 4) for k, v in sorted(pos.items())}
            metrics["spacy_entity_count"] = len(doc.ents)
            statuses.append(ToolStatus("spacy:en_core_web_sm", True, spacy.__version__))
    except Exception as exc:
        statuses.append(ToolStatus("spacy", False, detail=str(exc)))

    # TextDescriptives is intentionally optional; it provides mature readability,
    # dependency-distance, information-theory and duplicate-text metrics.
    try:
        import textdescriptives as td
        try:
            frame = td.extract_metrics(
                text=text,
                spacy_model="en_core_web_sm",
                metrics=[
                    "descriptive_stats",
                    "readability",
                    "dependency_distance",
                    "pos_proportions",
                    "quality",
                    "information_theory",
                ],
            )
            row = frame.iloc[0].to_dict()
            for key, value in row.items():
                if key == "text":
                    continue
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    metrics[f"td_{key}"] = round(float(value), 6)
                elif isinstance(value, bool):
                    metrics[f"td_{key}"] = value
            statuses.append(ToolStatus("textdescriptives", True, getattr(td, "__version__", "installed")))

            # Coherence is deliberately isolated from the core TextDescriptives pass.
            # Some spaCy models/environments cannot provide the vector semantics it
            # needs; a coherence failure must not throw away mature readability,
            # information-theory, duplicate-text, POS, and dependency metrics.
            try:
                coherence = td.extract_metrics(
                    text=text,
                    spacy_model="en_core_web_sm",
                    metrics=["coherence"],
                )
                crow = coherence.iloc[0].to_dict()
                for key, value in crow.items():
                    if key == "text":
                        continue
                    if isinstance(value, bool):
                        metrics[f"td_{key}"] = value
                    elif isinstance(value, (int, float)) and math.isfinite(float(value)):
                        metrics[f"td_{key}"] = round(float(value), 6)
                statuses.append(ToolStatus("textdescriptives:coherence", True, getattr(td, "__version__", "installed")))
            except Exception as exc:
                statuses.append(ToolStatus("textdescriptives:coherence", False, detail=str(exc)))
        except Exception as exc:
            statuses.append(ToolStatus("textdescriptives", False, detail=str(exc)))
    except Exception as exc:
        statuses.append(ToolStatus("textdescriptives", False, detail=str(exc)))

    return metrics, statuses
