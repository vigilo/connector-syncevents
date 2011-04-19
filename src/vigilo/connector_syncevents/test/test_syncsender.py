# -*- coding: utf-8 -*-
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Teste le connecteur syncevents
"""
import unittest

# ATTENTION: ne pas utiliser twisted.trial, car nose va ignorer les erreurs
# produites par ce module !!!
#from twisted.trial import unittest
from nose.twistedtools import reactor, deferred # pylint: disable-msg=W0611

from vigilo.pubsub.xml import NS_COMMAND
from vigilo.connector.test.helpers import XmlStreamStub

from vigilo.connector_syncevents.main import SyncSender

# on a le droit d'accéder aux attributs privés:
# pylint: disable-msg=W0212


class DBResult(object):
    def __init__(self, hostname, servicename):
        self.hostname = hostname
        self.servicename = servicename


class TestSyncSender(unittest.TestCase):
    """Teste le connecteur XMPP"""

    def test_buildHostMessage(self):
        """Fonction buildHostMessage"""
        db = DBResult("testhost", None)
        sender = SyncSender(None)
        result = sender._buildNagiosMessage(db)
        self.assertEqual(result.name, "command")
        self.assertEqual(result.uri, NS_COMMAND)
        self.assertEqual(str(result.cmdname),
                         "SEND_CUSTOM_HOST_NOTIFICATION")
        self.assertEqual(str(result.value),
                         "testhost;0;vigilo;syncevents")

    def test_buildServiceMessage(self):
        """Fonction buildServiceMessage"""
        db = DBResult("testhost", "testservice")
        sender = SyncSender(None)
        result = sender._buildNagiosMessage(db)
        self.assertEqual(result.name, "command")
        self.assertEqual(result.uri, NS_COMMAND)
        self.assertEqual(str(result.cmdname),
                         "SEND_CUSTOM_SVC_NOTIFICATION")
        self.assertEqual(str(result.value),
                         "testhost;testservice;0;vigilo;syncevents")

    #@deferred(timeout=30)
    #@defer.inlineCallbacks
    def test_askNagios(self):
        """Fonction askNagios"""
        db = DBResult("testhost", "testservice")
        count = 42
        tosync = [ db for _i in range(count) ]
        sender = SyncSender(tosync)
        stub = XmlStreamStub()
        sender.xmlstream = stub.xmlstream
        # pas de yield ci-dessous, les réponses n'arriveront jamais
        sender.askNagios()
        stub.send_replies()
        self.assertEqual(len(stub.output), count)



