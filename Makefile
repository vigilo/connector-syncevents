NAME := connector-syncevents

all: build settings.ini

include buildenv/Makefile.common

settings.ini: settings.ini.in
	sed -e 's,@LOCALSTATEDIR@,$(LOCALSTATEDIR),g' \
		-e 's,@NAGIOSCMDPIPE@,$(NAGIOSCMDPIPE),g' $^ > $@

install: settings.ini $(PYTHON)
	$(PYTHON) setup.py install --single-version-externally-managed --root=$(DESTDIR) --record=INSTALLED_FILES
	chmod a+rX -R $(DESTDIR)$(PREFIX)/lib*/python*/*

clean: clean_python
	rm -f settings.ini

lint: lint_pylint
tests: tests_nose
