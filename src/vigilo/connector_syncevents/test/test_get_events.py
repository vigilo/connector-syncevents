# -*- coding: utf-8 -*-
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Teste la requête à la base de données
"""
import unittest
from datetime import datetime, timedelta

from vigilo.common.conf import settings
settings.load_module(__name__)
from vigilo.models.configure import configure_db
configure_db(settings['database'], 'sqlalchemy_')

from vigilo.models.session import DBSession, metadata
from vigilo.models import tables
from vigilo.models.demo import functions as df

from vigilo.connector_syncevents.main import get_events

# désactivation de "Too many public methods"
# pylint: disable-msg=R0904

class TestRequest(unittest.TestCase):
    """
    Teste la requête de récupération des événements à synchroniser
    """

    def setUp(self):
        # La vue GroupPath dépend de Group et GroupHierarchy.
        # SQLAlchemy ne peut pas détecter correctement la dépendance.
        # On crée le schéma en 2 fois pour contourner ce problème.
        # Idem pour la vue UserSupItem (6 dépendances).
        mapped_tables = metadata.tables.copy()
        del mapped_tables[tables.grouppath.GroupPath.__tablename__]
        del mapped_tables[tables.usersupitem.UserSupItem.__tablename__]
        metadata.create_all(tables=mapped_tables.itervalues())
        metadata.create_all(tables=[tables.grouppath.GroupPath.__table__, 
            tables.usersupitem.UserSupItem.__table__])

        DBSession.add(tables.StateName(statename=u'OK', order=1))
        DBSession.add(tables.StateName(statename=u'UNKNOWN', order=2))
        DBSession.add(tables.StateName(statename=u'WARNING', order=3))
        DBSession.add(tables.StateName(statename=u'CRITICAL', order=4))
        DBSession.add(tables.StateName(statename=u'UP', order=1))
        DBSession.add(tables.StateName(statename=u'UNREACHABLE', order=2))
        DBSession.add(tables.StateName(statename=u'DOWN', order=4))
        DBSession.flush()

    def tearDown(self):
        DBSession.rollback()
        DBSession.expunge_all()
        metadata.drop_all()

    def test_no_events(self):
        """Pas d'évènements"""
        time_limit = datetime.now() - timedelta(minutes=42)
        self.assertEqual(get_events(time_limit), [])

    def test_age_younger_host(self):
        """Évènements trop récents sur un hôte"""
        host = df.add_host("testhost")
        now = datetime.now()
        age = now - timedelta(minutes=19)
        time_limit = now - timedelta(minutes=20)
        DBSession.merge(tables.State(
                idsupitem=host.idhost,
                state=tables.StateName.statename_to_value(u"DOWN"),
                timestamp=age))
        DBSession.flush()
        results = get_events(time_limit)
        self.assertEqual(len(results), 0)

    def test_age_equal_host(self):
        """Évènements à la limite d'âge sur un hôte"""
        host = df.add_host("testhost")
        now = datetime.now()
        age = now - timedelta(minutes=20)
        time_limit = age
        DBSession.merge(tables.State(
                idsupitem=host.idhost,
                state=tables.StateName.statename_to_value(u"DOWN"),
                timestamp=age))
        DBSession.flush()
        results = get_events(time_limit)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, None)

    def test_age_older_host(self):
        """Évènements suffisamment vieux sur un hôte"""
        host = df.add_host("testhost")
        now = datetime.now()
        age = now - timedelta(minutes=21)
        time_limit = now - timedelta(minutes=20)
        DBSession.merge(tables.State(
                idsupitem=host.idhost,
                state=tables.StateName.statename_to_value(u"DOWN"),
                timestamp=age))
        DBSession.flush()
        results = get_events(time_limit)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, None)

    def test_age_younger_service(self):
        """Évènements trop récents sur un service"""
        host = df.add_host("testhost")
        svc = df.add_lowlevelservice(host, "testsvc")
        now = datetime.now()
        age = now - timedelta(minutes=19)
        time_limit = now - timedelta(minutes=20)
        DBSession.merge(tables.State(
                idsupitem=svc.idservice,
                state=tables.StateName.statename_to_value(u"CRITICAL"),
                timestamp=age))
        DBSession.flush()
        results = get_events(time_limit)
        print results
        self.assertEqual(len(results), 0)

    def test_age_equal_service(self):
        """Évènements à la limite d'âge sur un service"""
        host = df.add_host("testhost")
        svc = df.add_lowlevelservice(host, "testsvc")
        now = datetime.now()
        age = now - timedelta(minutes=20)
        time_limit = age
        DBSession.merge(tables.State(
                idsupitem=svc.idservice,
                state=tables.StateName.statename_to_value(u"CRITICAL"),
                timestamp=age))
        DBSession.flush()
        results = get_events(time_limit)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, "testsvc")

    def test_age_older_service(self):
        """Évènements suffisamment vieux sur un service"""
        host = df.add_host("testhost")
        svc = df.add_lowlevelservice(host, "testsvc")
        now = datetime.now()
        age = now - timedelta(minutes=21)
        time_limit = now - timedelta(minutes=20)
        DBSession.merge(tables.State(
                idsupitem=svc.idservice,
                state=tables.StateName.statename_to_value(u"CRITICAL"),
                timestamp=age))
        DBSession.flush()
        results = get_events(time_limit)
        print results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, "testsvc")

    def test_state_down(self):
        """État DOWN"""
        host = df.add_host("testhost")
        now = datetime.now()
        age = now - timedelta(minutes=42)
        DBSession.merge(tables.State(
                idsupitem=host.idhost,
                state=tables.StateName.statename_to_value(u"DOWN"),
                timestamp=age))
        DBSession.flush()
        results = get_events(now)
        print results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, None)

    def test_state_up(self):
        """État UP"""
        host = df.add_host("testhost")
        now = datetime.now()
        age = now - timedelta(minutes=42)
        DBSession.merge(tables.State(
                idsupitem=host.idhost,
                state=tables.StateName.statename_to_value(u"UP"),
                timestamp=age))
        results = get_events(now)
        print results
        self.assertEqual(len(results), 0)

    def test_state_critical(self):
        """État CRITICAL"""
        host = df.add_host("testhost")
        svc = df.add_lowlevelservice(host, "testsvc")
        now = datetime.now()
        age = now - timedelta(minutes=42)
        DBSession.merge(tables.State(
                idsupitem=svc.idservice,
                state=tables.StateName.statename_to_value(u"CRITICAL"),
                timestamp=age))
        results = get_events(now)
        print results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, "testsvc")

    def test_state_warning(self):
        """État WARNING"""
        host = df.add_host("testhost")
        svc = df.add_lowlevelservice(host, "testsvc")
        now = datetime.now()
        age = now - timedelta(minutes=42)
        DBSession.merge(tables.State(
                idsupitem=svc.idservice,
                state=tables.StateName.statename_to_value(u"WARNING"),
                timestamp=age))
        DBSession.flush()
        results = get_events(now)
        print results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, "testsvc")

    def test_state_unknown(self):
        """État UNKNOWN"""
        host = df.add_host("testhost")
        svc = df.add_lowlevelservice(host, "testsvc")
        now = datetime.now()
        age = now - timedelta(minutes=42)
        DBSession.merge(tables.State(
                idsupitem=svc.idservice,
                state=tables.StateName.statename_to_value(u"UNKNOWN"),
                timestamp=age))
        DBSession.flush()
        results = get_events(now)
        print results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, "testsvc")

    def test_state_ok(self):
        """État OK"""
        host = df.add_host("testhost")
        svc = df.add_lowlevelservice(host, "testsvc")
        now = datetime.now()
        age = now - timedelta(minutes=42)
        DBSession.merge(tables.State(
                idsupitem=svc.idservice,
                state=tables.StateName.statename_to_value(u"OK"),
                timestamp=age))
        results = get_events(now)
        print results
        self.assertEqual(len(results), 0)

    def test_service_when_host_down(self):
        """Évènements vieux sur un service dont l'hôte est DOWN"""
        host = df.add_host("testhost")
        svc = df.add_lowlevelservice(host, "testsvc")
        now = datetime.now()
        age = now - timedelta(minutes=21)
        time_limit = now - timedelta(minutes=20)
        DBSession.merge(tables.State(
                idsupitem=host.idhost,
                state=tables.StateName.statename_to_value(u"DOWN"),
                timestamp=now))
        DBSession.merge(tables.State(
                idsupitem=svc.idservice,
                state=tables.StateName.statename_to_value(u"UNKNOWN"),
                timestamp=age))
        DBSession.flush()
        results = get_events(time_limit)
        print results
        self.assertEqual(len(results), 0)

    def test_above_max_events(self):
        """Trop d'événements à synchroniser"""
        now = datetime.now()
        age = now - timedelta(minutes=42)
        for i in range(10):
            host = df.add_host("testhost%d" % i)
            DBSession.merge(tables.State(
                    idsupitem=host.idhost,
                    state=tables.StateName.statename_to_value(u"DOWN"),
                    timestamp=age))
        DBSession.flush()
        results = get_events(now, 2)
        print results
        self.assertEqual(len(results), 2)
