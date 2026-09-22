.PHONY: test conformance verify-examples demo

test:
	python -m unittest discover -s tests -v

conformance:
	python conformance/run.py

verify-examples:
	python -m paxlet.cli verify examples/hello
	python -m paxlet.cli verify examples/statistics-mean
	python -m paxlet.cli verify examples/science-fasta-gc
	python -m paxlet.cli verify examples/text-wordcount
	python -m paxlet.cli verify examples/sensor-calibrate

demo:
	python -m paxlet.cli run examples/hello hello --input '{"name":"Paxlet"}'
