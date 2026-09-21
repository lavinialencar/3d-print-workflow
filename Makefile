.PHONY: test check scan links help

help:            ## list the targets
	@grep -E '^[a-z]+:.*##' Makefile | sed 's/:.*##/ -/'

test:            ## run the unit tests (no hardware, no network)
	python3 -m unittest discover -s tests -v

scan:            ## fail if anything personal-looking is in the repository
	python3 tools/scan_personal_data.py

check:           ## everything CI runs: compile, tests, scan, links
	python3 -m py_compile scripts/*.py tools/*.py
	python3 -m unittest discover -s tests
	python3 tools/scan_personal_data.py
	python3 tools/check_links.py

links:           ## verify every relative link and anchor in the Markdown files
	python3 tools/check_links.py
