# Bookwright comparison benchmark

Bookwright is intentionally **not** a runtime dependency. Test it separately against the same planted continuity failures before extending our graph/continuity code.

Install/one-shot according to Bookwright's published CLI package:

```powershell
uvx --from bookwright-cli bookwright version
```

Benchmark targets to reproduce in a disposable Bookwright project:

1. stale possession after a Chapter 5 retcon;
2. character location contradiction;
3. Chapter 9 secret leaked before its reveal;
4. branch-aware replacement of a fact at Chapter 5;
5. character knowledge: truth exists but POV does not know it yet;
6. chronology regression;
7. unresolved setup/payoff/thread state.

Record for every case: deterministic pass/fail, exact command, false positives, whether model inference was required, project-format conversion cost, and whether branches are represented natively. Do not compare marketing feature lists; compare planted failures.
