.PHONY: install doctor plan run report lint compile inspect demo

TOPIC ?= Claude Anthropic Governance für deutsche Banken

install:
	pip install -e ".[providers]"

doctor:
	./pexon doctor

plan:
	./pexon plan --seeds "ai governance banken,lora fine-tuning" --write plan.yaml

run:
	./pexon run --topic "$(TOPIC)" --wait 0

report:
	./pexon report

lint:
	.venv/bin/ruff check src

compile:
	PYTHONPATH=src .venv/bin/python -m compileall -q src

inspect:
	./pexon inspect providers
	./pexon inspect settings

demo:
	@echo "See docs/DEMO.md for the CEO walkthrough."
