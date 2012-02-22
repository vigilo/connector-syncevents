# -*- coding: utf-8 -*-

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
