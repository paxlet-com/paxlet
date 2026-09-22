# Contributing

Paxlet Core should stay smaller than the systems built with it.

Before adding a Core field, ask:

1. Is it necessary to identify, verify, distribute or execute a package?
2. Can an independent implementation support it without Taskand?
3. Can a junior developer explain it after reading one page?

Run before submitting changes:

```bash
python -m unittest discover -s tests -v
python conformance/run.py
```
