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

from mock import Mock

from vigilo.connector_syncevents.main import SyncSender

# on a le droit d'accéder aux attributs privés:
# pylint: disable-msg=W0212



class DBResult(object):
    def __init__(self, hostname, servicename, vigiloserver):
        self.hostname = hostname
        self.servicename = servicename
        self.vigiloserver = vigiloserver



class TestSyncSender(unittest.TestCase):


    def test_buildHostMessage(self):
        """Fonction buildHostMessage"""
        db = DBResult("testhost", None, "collector")
        sender = SyncSender(None)
        result = sender._buildNagiosMessage(db)
        self.assertEqual(result["type"], "nagios")
        self.assertEqual(result["cmdname"],
                         "SEND_CUSTOM_HOST_NOTIFICATION")
        self.assertEqual(result["value"],
                         "testhost;0;vigilo;syncevents")
        self.assertEqual(result["routing_key"], "collector")


    def test_buildServiceMessage(self):
        """Fonction buildServiceMessage"""
        db = DBResult("testhost", "testservice", "collector")
        sender = SyncSender(None)
        result = sender._buildNagiosMessage(db)
        self.assertEqual(result["type"], "nagios")
        self.assertEqual(result["cmdname"],
                         "SEND_CUSTOM_SVC_NOTIFICATION")
        self.assertEqual(result["value"],
                         "testhost;testservice;0;vigilo;syncevents")
        self.assertEqual(result["routing_key"], "collector")


    @deferred(timeout=30)
    def test_askNagios(self):
        """Fonction askNagios"""
        db = DBResult("testhost", "testservice", "collector")
        count = 42
        tosync = [ db for _i in range(count) ]
        sender = SyncSender(tosync)
        sender.publisher = Mock()
        d = sender.askNagios(None)
        def check(r):
            self.assertEqual(len(sender.publisher.write.call_args_list), count)
        d.addCallback(check)
        return d



