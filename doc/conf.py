# -*- coding: utf-8 -*-
# Copyright (C) 2011-2020 CS GROUP - France
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

name = u'connector-syncevents'

project = u'Vigilo %s' % name

pdf_documents = [
        ('admin', "admin-%s" % name, "Connector-syncevents : Guide d'administration", u'Vigilo'),
]

latex_documents = [
        ('admin', 'admin-%s.tex' % name, u"Connector-syncevents : Guide d'administration",
         'AA100004-2/TODO', 'vigilo'),
]

execfile("../buildenv/doc/conf.py")
