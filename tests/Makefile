# Copyright 2013 semantics GmbH
# Written by Marcus Brinkmann <m.brinkmann@semantics.de>

old_report = $(lastword $(sort $(wildcard out/report-*.dat)))

PYTHON=python
COVERAGE=$(PYTHON)

all: out/report.html

clean:
	rm -f out/report.dat out/report.html

realclean: clean
	rm -f out/report-*.dat

out/report.dat: data/*.txt
	$(COVERAGE) mwtests.py

out/report.html: report.py out/report.dat
	$(PYTHON) report.py $(if $(old_report), --old-input=$(old_report)) out/report.dat

commit: out/report.html
	cp out/report.dat out/report-`date -Iseconds`.dat

.PHONY: clean realclean
