#!/usr/bin/env python
# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2018 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

import os, sys
from setuptools import setup, find_packages

sysconfdir = os.getenv("SYSCONFDIR", "/etc")
localstatedir = os.getenv("LOCALSTATEDIR", "/var")
cronext = os.getenv("CRONEXT", ".cron")

tests_require = [
    'coverage',
    'nose',
    'pylint',
    'mock',
]

def install_i18n(i18ndir, destdir):
    data_files = []
    langs = []
    for f in os.listdir(i18ndir):
        if os.path.isdir(os.path.join(i18ndir, f)) and not f.startswith("."):
            langs.append(f)
    for lang in langs:
        for f in os.listdir(os.path.join(i18ndir, lang, "LC_MESSAGES")):
            if f.endswith(".mo"):
                data_files.append(
                        (os.path.join(destdir, lang, "LC_MESSAGES"),
                         [os.path.join(i18ndir, lang, "LC_MESSAGES", f)])
                )
    return data_files

setup(name='vigilo-connector-syncevents',
        version='5.1.0dev',
        author='Vigilo Team',
        author_email='contact.vigilo@c-s.fr',
        url='https://www.vigilo-nms.com/',
        description="Vigilo events syncer",
        long_description="Update event states in the Vigilo database "
                         "by asking Nagios.",
        license='http://www.gnu.org/licenses/gpl-2.0.html',
        zip_safe=False, # pour pouvoir écrire le dropin.cache de twisted
        install_requires=[
            'setuptools',
            'vigilo-common',
            'vigilo-connector',
            'vigilo-models',
            ],
        namespace_packages = [
            'vigilo',
            ],
        packages=find_packages("src"),
        message_extractors={
            'src': [
                ('**.py', 'python', None),
            ],
        },
        extras_require={
            'tests': tests_require,
        },
        entry_points={
            'console_scripts': [
                'vigilo-connector-syncevents = vigilo.connector_syncevents.main:main',
                ],
        },
        package_dir={'': 'src'},
        data_files=[
                    (os.path.join(sysconfdir, "vigilo", "connector-syncevents"),
                        ["settings.ini"]),
                    (os.path.join(sysconfdir, "cron.d"),
                        ["pkg/vigilo-connector-syncevents%s" % cronext]),
                    (os.path.join(localstatedir, "lock/subsys"), []),
                    (os.path.join(localstatedir, "lock/subsys/vigilo-connector-syncevents"), []),
                   ] + install_i18n("i18n", os.path.join(sys.prefix, "share", "locale")),
        )

