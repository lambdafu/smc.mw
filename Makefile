# Copyright 2008-2013 semantics GmbH
# Written by Christian Heimes <c.heimes@semantics.de>
# Modified by Marcus Brinkmann <m.brinkmann@semantics.de>

PYTHON=python2.7
SETUPFLAGS=
COMPILEFLAGS=

.PHONY: inplace all rebuild test_inplace test clean realclean egg_info egg 
.PHONY: develop sdist update-parser

inplace:
	$(PYTHON) setup.py $(SETUPFLAGS) build_ext -i $(COMPILEFLAGS)

all: inplace

rebuild: clean all

test_inplace: inplace
	$(PYTHON) -m smc.mw.tests

test: test_inplace

clean:
	find . \( -name '*~' -or -name '*.o' -or -name '*.so' -or -name '*.py[cod]' \) -delete

realclean: clean
	$(PYTHON) setup.py clean -a
	rm -rf build
	rm -rf dist
	rm -f TAGS tags
	rm -rf smc.mw.egg-info

egg_info:
	rm -rf smc.mw.egg-info
	$(PYTHON) setup.py egg_info

egg: egg_info inplace
	$(PYTHON) setup.py bdist_egg

develop: egg_info inplace
	$(PYTHON) setup.py develop

sdist: egg_info
	$(PYTHON) setup.py sdist

.SUFFIXES: .ebnf .py
.ebnf.py:
	grako --whitespace="" --no-nameguard -o $@ $<

update-parser: smc/mw/mw.py smc/mw/mw_pre.py tests/testspec.py

