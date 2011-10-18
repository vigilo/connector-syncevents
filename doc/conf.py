# -*- coding: utf-8 -*-

project = u'Vigilo connector-syncevents'

pdf_documents = [
        ('admin', "admin-connector-syncevents", "Connector-syncevents : Guide d'administration", u'Vigilo'),
]

latex_documents = [
        ('admin', 'admin-connector-syncevents.tex', u"Connector-syncevents : Guide d'administration",
         'AA100004-2/TODO', 'vigilo'),
]

execfile("../buildenv/doc/conf.py")
