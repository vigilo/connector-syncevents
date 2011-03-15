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


class TestRequest(unittest.TestCase):
    """
    Teste la requête de récupération des événements à synchroniser
    """

    def setUp(self):
        pass

    def tearDown(self):
        pass


class DBResult(object):
    def __init__(self, hostname, servicename)
        self.hostname = hostname
        self.servicename = servicename


class TestSyncSender(unittest.TestCase):
    """Teste le connecteur XMPP"""

    def test_buildHostMessage(self):
        db = DBResult("testhost", None)
        self.sender = SyncSender()
        self.assertEqual(self.sender._buildNagiosMessage(db),
                         "")

    def test_buildServiceMessage(self):
        db = DBResult("testhost", "testservice")
        self.sender = SyncSender()
        #stub = XmlStreamStub()
        #self.sender.xmlstream = stub.xmlstream
        self.assertEqual(self.sender._buildNagiosMessage(db),
                         "")

    @deferred(timeout=30)
    @defer.inlineCallbacks
    def test_askNagios(self):
        db = DBResult("testhost", "testservice")
        count = 42
        tosync = [ db for i in range(count) ]
        self.sender = SyncSender(tosync)
        stub = XmlStreamStub()
        self.sender.xmlstream = stub.xmlstream
        yield self.sender.askNagios()
        self.assertEqual(len(stub.output), count)



