# -*- coding: utf-8 -*-
# Copyright (C) 2006-2020 CS GROUP - France
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Teste la requête à la base de données
"""
from __future__ import print_function

import os
import unittest
from datetime import datetime, timedelta

os.environ['VIGILO_SETTINGS'] = 'settings_tests.ini'
from vigilo.common.conf import settings
settings.load_module(__name__)
from vigilo.models.configure import configure_db
configure_db(settings['database'], 'sqlalchemy_')

from vigilo.models.session import DBSession, metadata
from vigilo.models import tables
from vigilo.models.demo import functions as df

from vigilo.connector_syncevents.main import get_desync

# désactivation de "Too many public methods"
# pylint: disable-msg=R0904

class TestRequest(unittest.TestCase):
    """
    Teste la requête de récupération des événements à synchroniser
    """

    def setUp(self):
        # On crée les tables, puis les vues.
        mapped_tables = metadata.tables.copy()
        views = {}
        for tablename in mapped_tables:
            info = mapped_tables[tablename].info or {}
            if info.get('vigilo_view'):
                views[tablename] = mapped_tables[tablename]
        for view in views:
            del mapped_tables[view]

        metadata.create_all(tables=mapped_tables.itervalues())
        metadata.create_all(tables=views.values())

        DBSession.add(tables.StateName(statename=u'OK', order=1))
        DBSession.add(tables.StateName(statename=u'UNKNOWN', order=2))
        DBSession.add(tables.StateName(statename=u'WARNING', order=3))
        DBSession.add(tables.StateName(statename=u'CRITICAL', order=4))
        DBSession.add(tables.StateName(statename=u'UP', order=1))
        DBSession.add(tables.StateName(statename=u'UNREACHABLE', order=2))
        DBSession.add(tables.StateName(statename=u'DOWN', order=4))

        df.add_application("nagios")
        df.add_vigiloserver("collector")

        DBSession.flush()

    def tearDown(self):
        DBSession.rollback()
        DBSession.expunge_all()
        metadata.drop_all()

    def test_no_events(self):
        """Pas d'évènements"""
        time_limit = datetime.utcnow() - timedelta(minutes=42)
        self.assertEqual(get_desync(time_limit, time_limit), [])

    def test_age_younger_host(self):
        """Évènements trop récents sur un hôte"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=19)
        time_limit = utcnow - timedelta(minutes=20)
        df.add_host_state(host, "DOWN", timestamp=age)
        DBSession.flush()
        results = get_desync(time_limit, time_limit)
        self.assertEqual(len(results), 0)

    def test_age_equal_host(self):
        """Évènements à la limite d'âge sur un hôte"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=20)
        time_limit = age
        df.add_host_state(host, "DOWN", timestamp=age)
        results = get_desync(time_limit, time_limit)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, None)
        self.assertEqual(results[0].vigiloserver, "collector")

    def test_age_older_host(self):
        """Évènements suffisamment vieux sur un hôte"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=21)
        time_limit = utcnow - timedelta(minutes=20)
        df.add_host_state(host, "DOWN", timestamp=age)
        results = get_desync(time_limit, time_limit)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, None)
        self.assertEqual(results[0].vigiloserver, "collector")

    def test_age_younger_service(self):
        """Évènements trop récents sur un service"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        svc = df.add_lowlevelservice(host, "testsvc")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=19)
        time_limit = utcnow - timedelta(minutes=20)
        df.add_svc_state(svc, "CRITICAL", timestamp=age)
        results = get_desync(time_limit, time_limit)
        print(results)
        self.assertEqual(len(results), 0)

    def test_age_equal_service(self):
        """Évènements à la limite d'âge sur un service"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        svc = df.add_lowlevelservice(host, "testsvc")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=20)
        time_limit = age
        df.add_svc_state(svc, "CRITICAL", timestamp=age)
        results = get_desync(time_limit, time_limit)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, "testsvc")
        self.assertEqual(results[0].vigiloserver, "collector")

    def test_age_older_service(self):
        """Évènements suffisamment vieux sur un service"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        svc = df.add_lowlevelservice(host, "testsvc")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=21)
        time_limit = utcnow - timedelta(minutes=20)
        df.add_svc_state(svc, "CRITICAL", timestamp=age)
        results = get_desync(time_limit, time_limit)
        print(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, "testsvc")
        self.assertEqual(results[0].vigiloserver, "collector")

    def test_state_down(self):
        """État DOWN"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=42)
        df.add_host_state(host, "DOWN", timestamp=age)
        DBSession.flush()
        results = get_desync(utcnow, utcnow)
        print(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, None)
        self.assertEqual(results[0].vigiloserver, "collector")

    def test_state_up(self):
        """État UP"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=42)
        df.add_host_state(host, "UP", timestamp=age)
        results = get_desync(utcnow, utcnow)
        print(results)
        self.assertEqual(len(results), 0)

    def test_state_critical(self):
        """État CRITICAL"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        svc = df.add_lowlevelservice(host, "testsvc")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=42)
        df.add_svc_state(svc, "CRITICAL", timestamp=age)
        results = get_desync(utcnow, utcnow)
        print(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, "testsvc")
        self.assertEqual(results[0].vigiloserver, "collector")

    def test_state_warning(self):
        """État WARNING"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        svc = df.add_lowlevelservice(host, "testsvc")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=42)
        df.add_svc_state(svc, "WARNING", timestamp=age)
        results = get_desync(utcnow, utcnow)
        print(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, "testsvc")
        self.assertEqual(results[0].vigiloserver, "collector")

    def test_state_unknown(self):
        """État UNKNOWN"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        svc = df.add_lowlevelservice(host, "testsvc")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=42)
        df.add_svc_state(svc, "UNKNOWN", timestamp=age)
        results = get_desync(utcnow, utcnow)
        print(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, "testsvc")
        self.assertEqual(results[0].vigiloserver, "collector")

    def test_state_ok(self):
        """État OK"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        svc = df.add_lowlevelservice(host, "testsvc")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=42)
        df.add_svc_state(svc, "OK", timestamp=age)
        results = get_desync(utcnow, utcnow)
        print(results)
        self.assertEqual(len(results), 0)

    def test_service_when_host_down(self):
        """Évènements vieux sur un service dont l'hôte est DOWN"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        svc = df.add_lowlevelservice(host, "testsvc")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=21)
        time_limit = utcnow - timedelta(minutes=20)
        df.add_host_state(host, "DOWN", timestamp=utcnow)
        df.add_svc_state(svc, "UNKNOWN", timestamp=age)
        results = get_desync(time_limit, time_limit)
        print(results)
        self.assertEqual(len(results), 0)

    def test_above_max_events(self):
        """Trop d'événements à synchroniser"""
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=42)
        for i in range(10):
            host = df.add_host("testhost%d" % i)
            df.add_host_state(host, "DOWN", timestamp=age)
            df.add_ventilation(host, "collector", "nagios")
        DBSession.flush()
        results = get_desync(utcnow, utcnow, 2)
        print(results)
        self.assertEqual(len(results), 2)

    def test_events_service(self):
        """État différent entre la table State et Event pour un service"""
        host = df.add_host("testhost")
        df.add_ventilation(host, "collector", "nagios")
        svc = df.add_lowlevelservice(host, "testsvc")
        df.add_svc_state(svc, "WARNING")
        e = df.add_event(svc, "CRITICAL", "dummy")
        # on créé un service normal (synchronisé) pour que le service à tester
        # ne soit pas la cause de l'aggrégat
        svc_normal = df.add_lowlevelservice(host, "normalsvc")
        df.add_svc_state(svc_normal, "WARNING")
        e_normal = df.add_event(svc_normal, "WARNING", "dummy")
        # 2 correvents sont ajoutés : un où le service à tester est la cause,
        # un où il ne l'est pas.
        df.add_correvent([e, e_normal])
        df.add_correvent([e_normal, e])
        time_limit = datetime.utcnow() - timedelta(minutes=42)
        results = get_desync(time_limit, time_limit)
        print(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, "testsvc")
        self.assertEqual(results[0].vigiloserver, "collector")

    def test_events_hosts(self):
        """État différent entre la table State et Event pour un hôte"""
        host = df.add_host("testhost")
        df.add_host_state(host, "OK")
        e = df.add_event(host, "DOWN", "dummy")
        df.add_ventilation(host, "collector", "nagios")
        # on créé un hôte normal (synchronisé) pour que l'hôte à tester
        # ne soit pas la cause de l'aggrégat
        host_normal = df.add_host("normalhost")
        df.add_host_state(host_normal, "DOWN")
        e_normal = df.add_event(host_normal, "DOWN", "dummy")
        # 2 correvents sont ajoutés : un où l'hôte à tester est la cause, un où
        # il ne l'est pas.
        df.add_correvent([e, e_normal])
        df.add_correvent([e_normal, e])
        time_limit = datetime.utcnow() - timedelta(minutes=42)
        results = get_desync(time_limit, time_limit)
        print(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, "testhost")
        self.assertEqual(results[0].servicename, None)
        self.assertEqual(results[0].vigiloserver, "collector")

    def test_event_closed_service(self):
        """Évènements vieux mais sur un correvent fermé (service)"""
        host = df.add_host("testhost")
        svc = df.add_lowlevelservice(host, "testsvc")
        df.add_svc_state(svc, "WARNING")
        e = df.add_event(svc, "CRITICAL", "dummy")
        # on créé un service normal (synchronisé) pour que le service à tester
        # ne soit pas la cause de l'aggrégat
        svc_normal = df.add_lowlevelservice(host, "normalsvc")
        df.add_svc_state(svc_normal, "WARNING")
        e_normal = df.add_event(svc_normal, "WARNING", "dummy")
        # 2 correvents sont ajoutés : un où le service à tester est la cause,
        # un où il ne l'est pas.
        df.add_correvent([e, e_normal], status=tables.CorrEvent.ACK_CLOSED)
        df.add_correvent([e_normal, e], status=tables.CorrEvent.ACK_CLOSED)
        time_limit = datetime.utcnow() - timedelta(minutes=42)
        results = get_desync(time_limit, time_limit)
        print(results)
        self.assertEqual(len(results), 0)

    def test_event_closed_host(self):
        """Évènements vieux mais sur un correvent fermé (host)"""
        host = df.add_host("testhost")
        host = df.add_host("testhost2")
        df.add_host_state(host, "UP")
        e = df.add_event(host, "DOWN", "dummy")
        df.add_correvent([e], status=tables.CorrEvent.ACK_CLOSED)
        time_limit = datetime.utcnow() - timedelta(minutes=42)
        results = get_desync(time_limit, time_limit)
        print(results)
        self.assertEqual(len(results), 0)

    def test_hls_state_critical(self):
        """État CRITICAL sur un Service de Haut Niveau"""
        svc = df.add_highlevelservice("testsvc")
        svc2 = df.add_highlevelservice("testsvc2")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=42)
        df.add_svc_state(svc, "CRITICAL", timestamp=age)
        df.add_svc_state(svc2, "CRITICAL", timestamp=utcnow)
        results = get_desync(age, age)
        print(results)
        self.assertEqual(len(results), 0)

    def test_hls_state_warning(self):
        """État WARNING sur un Service de Haut Niveau"""
        svc = df.add_highlevelservice("testsvc")
        svc2 = df.add_highlevelservice("testsvc2")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=42)
        df.add_svc_state(svc, "WARNING", timestamp=age)
        df.add_svc_state(svc2, "WARNING", timestamp=utcnow)
        results = get_desync(age, age)
        print(results)
        self.assertEqual(len(results), 0)

    def test_hls_state_unknown(self):
        """État UNKNOWN sur un Service de Haut Niveau"""
        svc = df.add_highlevelservice("testsvc")
        svc2 = df.add_highlevelservice("testsvc2")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=42)
        df.add_svc_state(svc, "UNKNOWN", timestamp=age)
        df.add_svc_state(svc2, "UNKNOWN", timestamp=utcnow)
        results = get_desync(age, age)
        print(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, None)
        self.assertEqual(results[0].servicename, "testsvc")
        self.assertEqual(results[0].vigiloserver, None)

    def test_hls_state_ok(self):
        """État OK sur un Service de Haut Niveau"""
        svc = df.add_highlevelservice("testsvc")
        svc2 = df.add_highlevelservice("testsvc2")
        utcnow = datetime.utcnow()
        age = utcnow - timedelta(minutes=42)
        df.add_svc_state(svc, "OK", timestamp=age)
        df.add_svc_state(svc2, "OK", timestamp=utcnow)
        results = get_desync(age, age)
        print(results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].hostname, None)
        self.assertEqual(results[0].servicename, "testsvc")
        self.assertEqual(results[0].vigiloserver, None)

