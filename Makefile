NAME := connector-syncevents
USER := vigilo-syncevents

all: build

include buildenv/Makefile.common


install: install_python install_permissions
install_pkg: install_python_pkg

install_python: settings.ini $(PYTHON)
	$(PYTHON) setup.py install --record=INSTALLED_FILES
install_python_pkg: settings.ini $(PYTHON)
	$(PYTHON) setup.py install --single-version-externally-managed --root=$(DESTDIR)

install_permissions:
	chgrp $(USER) $(SYSCONFDIR)/vigilo/$(NAME)/settings.ini
	chmod 640 $(SYSCONFDIR)/vigilo/$(NAME)/settings.ini

clean: clean_python

lint: lint_pylint
tests: tests_nose

.PHONY: install_pkg install_python install_python_pkg install_data install_permissions
