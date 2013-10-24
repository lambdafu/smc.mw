smc.mw
======

A mediawiki-compatible parser for Python.

Using
=====

To run the tests::

 $ make -C tests

The test result can be found in ``tests/out/report.html``.

A command line tool is available, too (installed as "mw")::

 $ echo "''Hello World''" | python smc/mw/tool.py
 <html><body><p><i>Hello World</i>
 </p></body></html>

Differences
===========

For specific differences, see the `test results`_.

* __TOC__ and other magic words must appear on a line on their own, while MediaWiki allows them everyhwere with some strange consequences.


.. _test results: http://htmlpreview.github.io/?http://github.com/lambdafu/smc.mw/blob/master/tests/out/report-0002.html

Thanks
======

The parser uses the grako_ parser generator for PEG grammars by ResQSoft Inc. and Juancarlo Añez.

.. _grako: https://bitbucket.org/apalala/grako


Authors
=======

* Marcus Brinkmann, m.brinkmann@semantics.de


Copyright
=========

smc.mw
------

Copyright (C) 2013 semantics GmbH.  All Rights Reserved.

For licensing, see the file LICENSE.txt.

::

 semantics
 Kommunikationsmanagement GmbH
 Viktoriaallee 45
 D-52066 Aachen
 Germany

 email: info(at)semantics.de
 url: http://www.semantics.de/

jquery
------

smc.mw includes jquery in the test suite under ``tests/static/jquery-1.10.1.min.js``::

 Copyright 2013 jQuery Foundation and other contributors
 http://jquery.com/

 Permission is hereby granted, free of charge, to any person obtaining
 a copy of this software and associated documentation files (the
 "Software"), to deal in the Software without restriction, including
 without limitation the rights to use, copy, modify, merge, publish,
 distribute, sublicense, and/or sell copies of the Software, and to
 permit persons to whom the Software is furnished to do so, subject to
 the following conditions:

 The above copyright notice and this permission notice shall be
 included in all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
 LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
 OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
 WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Test Data
---------

The test data under ``tests/data/parserTests.txt`` and
``tests/extra-data/*.txt`` is copied verbatim from the MediaWiki project::

 MediaWiki Parser test cases
 Some taken from http://meta.wikimedia.org/wiki/Parser_testing
 All (C) their respective authors and released under the GPL

tidylib
-------

The tidylib implementation in ``tests/mytidylib`` is derived from
PyTidyLib, version 0.2.1::

 Copyright 2009 Jason Stitt
 
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 
 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.
 
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 THE SOFTWARE.
