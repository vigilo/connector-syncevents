NAME := connector-syncevents
USER := vigilo-syncevents

all: build

include buildenv/Makefile.common.python


install: build install_python install_permissions
install_pkg: build install_python_pkg

install_python: settings.ini $(PYTHON)
	$(PYTHON) setup.py install --record=INSTALLED_FILES
install_python_pkg: settings.ini $(PYTHON)
	$(PYTHON) setup.py install --single-version-externally-managed \
		$(SETUP_PY_OPTS) --root=$(DESTDIR)

install_permissions:
	@echo "Creating the $(USER) user..."
	-/usr/sbin/groupadd $(USER)
	-/usr/sbin/useradd -s /sbin/nologin -M -g $(USER) \
		-d $(LOCALSTATEDIR)/lib/vigilo/$(NAME) \
		-c 'Vigilo $(USER) user' $(USER)
	chgrp $(USER) $(SYSCONFDIR)/vigilo/$(NAME)/settings.ini
	chmod 640 $(SYSCONFDIR)/vigilo/$(NAME)/settings.ini

clean: clean_python

lint: lint_pylint
tests: tests_nose
doc: apidoc sphinxdoc

.PHONY: install_pkg install_python install_python_pkg install_data install_permissions

# vim: set noexpandtab :
