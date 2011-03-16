# -*- coding: utf-8 -*-
"""
Teste le connecteur syncevents
"""
import os
import tempfile
import shutil
import unittest

# ATTENTION: ne pas utiliser twisted.trial, car nose va ignorer les erreurs
# produites par ce module !!!
#from twisted.trial import unittest
from nose.twistedtools import reactor, deferred

from twisted.internet import defer
from twisted.words.xish import domish

from vigilo.connector_syncevents.main import SyncSender
from vigilo.pubsub.xml import NS_COMMAND

from vigilo.connector.test.helpers import XmlStreamStub, wait



class DBResult(object):
    def __init__(self, hostname, servicename):
        self.hostname = hostname
        self.servicename = servicename


class TestSyncSender(unittest.TestCase):
    """Teste le connecteur XMPP"""

    def test_buildHostMessage(self):
        """Fonction buildHostMessage"""
        db = DBResult("testhost", None)
        self.sender = SyncSender(None)
        result = self.sender._buildNagiosMessage(db)
        self.assertEqual(result.name, "command")
        self.assertEqual(result.uri, NS_COMMAND)
        self.assertEqual(str(result.cmdname),
                         "SEND_CUSTOM_HOST_NOTIFICATION")
        self.assertEqual(str(result.value),
                         "testhost;0;vigilo:syncevents")

    def test_buildServiceMessage(self):
        """Fonction buildServiceMessage"""
        db = DBResult("testhost", "testservice")
        self.sender = SyncSender(None)
        result = self.sender._buildNagiosMessage(db)
        self.assertEqual(result.name, "command")
        self.assertEqual(result.uri, NS_COMMAND)
        self.assertEqual(str(result.cmdname),
                         "SEND_CUSTOM_SVC_NOTIFICATION")
        self.assertEqual(str(result.value),
                         "testhost;testservice;0;vigilo:syncevents")

    #@deferred(timeout=30)
    #@defer.inlineCallbacks
    def test_askNagios(self):
        """Fonction askNagios"""
        db = DBResult("testhost", "testservice")
        count = 42
        tosync = [ db for i in range(count) ]
        self.sender = SyncSender(tosync)
        stub = XmlStreamStub()
        self.sender.xmlstream = stub.xmlstream
        # pas de yield ci-dessous, les réponses n'arriveront jamais
        self.sender.askNagios()
        self.assertEqual(len(stub.output), count)



