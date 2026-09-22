# Receipts and provenance

A receipt makes execution inspectable and reproducible enough to answer:

- what package/version ran?
- which action ran?
- what exact package bytes were used?
- what were the input/output digests?
- on which node/runtime?
- when did it start and finish?

Successful `paxlet run` writes a receipt to `.paxlet/receipts/` unless `--no-receipt` is used.

This is deliberately useful for scientific pipelines: datasets and results can be connected to the exact executable capability that produced them.
