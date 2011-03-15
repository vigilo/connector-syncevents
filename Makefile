NAME := connector-syncevents
USER := vigilo-syncevents

all: build

include buildenv/Makefile.common


install: install_files install_permissions

install_files: settings.ini $(PYTHON)
	$(PYTHON) setup.py install --single-version-externally-managed --root=$(DESTDIR) --record=INSTALLED_FILES
	chmod a+rX -R $(DESTDIR)$(PREFIX)/lib*/python*/*

install_permissions:
	chgrp $(USER) $(SYSCONFDIR)/vigilo/$(NAME)/settings.ini
	chmod 640 $(SYSCONFDIR)/vigilo/$(NAME)/settings.ini

clean: clean_python

lint: lint_pylint
tests: tests_nose
