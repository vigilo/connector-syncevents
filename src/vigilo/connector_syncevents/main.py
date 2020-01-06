# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2020 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Ce composant lit les événements en cours dans la base de données, et demande
à Nagios de renvoyer les états pour les services concernés, afin de garantir
la synchronicité des deux bases.
"""

import time
import sys
import logging
from optparse import OptionParser
from datetime import datetime, timedelta

from zope.interface import implements

from vigilo.common.conf import settings
settings.load_module(__name__)

from vigilo.models.configure import configure_db
configure_db(settings['database'], 'sqlalchemy_')

from vigilo.common.logging import get_logger, get_error_message
LOGGER = get_logger(__name__)

from vigilo.common.gettext import translate
_ = translate(__name__)

from twisted.internet import defer
from sqlalchemy.exc import InvalidRequestError, OperationalError
from sqlalchemy.sql.expression import null as expr_null, union

from vigilo.common.lock import grab_lock
from vigilo.connector.client import oneshotclient_factory
from vigilo.connector.handlers import buspublisher_factory
from vigilo.models.session import DBSession
from vigilo.models import tables
from vigilo.models.tables.eventsaggregate import EventsAggregate



def _add_ventilation(query):
    return query.join(
                (tables.Ventilation,
                    tables.Ventilation.idhost == tables.Host.idhost),
                (tables.VigiloServer,
                    tables.VigiloServer.idvigiloserver
                    == tables.Ventilation.idvigiloserver),
                (tables.Application,
                    tables.Application.idapp == tables.Ventilation.idapp),
            ).filter(
                tables.Application.name == u"nagios"
            ).filter(
                tables.VigiloServer.disabled == False
            )


def get_old_lls(time_limit):
    """
    Récupère les services à synchroniser.

    On configure Nagios pour renvoyer l'état des services non-OK toutes les X
    minutes. L'état est alors mis à jour dans la base. Donc si on trouve un
    état dans la base qui n'a pas été mis à jour il y a moins de X minutes,
    c'est potentiellement un message perdu, donc un service à re-synchroniser.

    Attention par contre, si l'hôte est DOWN Nagios n'enverra pas de mise à
    jours pour les services de cet hôte. Il faut donc exclure ces services.

    @param time_limit: Date après laquelle on ignore les états.
    @type  time_limit: C{datetime.datetime}
    @return: Requête SQL permettant de récupérer la liste des services
        dont l'état est obsolète.
    @rtype: C{sqlalchemy.orm.query.Query}
    """
    state_up = tables.StateName.statename_to_value(u'UP')
    state_ok = tables.StateName.statename_to_value(u'OK')

    # On récupère d'abord les hôtes DOWN/UNREACHABLE pour pouvoir ne remonter
    # que les services désynchronisés sur les hôtes OK/UP (#727)
    # Un hôte peut être "OK" si un exploitant a "Forcé à fermer"
    # une alarme portant sur cet hôte.
    hosts_down = DBSession.query(
        tables.Host.idhost,
    ).join(
        (tables.State, tables.State.idsupitem == tables.Host.idhost),
    ).filter(
        tables.State.state.in_([state_up, state_ok]),
    )

    lls_to_update = DBSession.query(
        tables.Host.name.label('hostname'),
        tables.LowLevelService.servicename.label('servicename'),
        tables.VigiloServer.name.label("vigiloserver"),
    ).join(
        (tables.LowLevelService,
            tables.LowLevelService.idhost == tables.Host.idsupitem),
        (tables.State,
            tables.State.idsupitem == tables.LowLevelService.idservice),
    ).filter(
        # On ne veut resynchroniser que les états anormaux.
        ~tables.State.state.in_([state_up, state_ok]),
    ).filter(
        tables.State.timestamp <= time_limit,
    ).filter(
        tables.Host.idhost.in_(hosts_down)
    )
    return _add_ventilation(lls_to_update)


def get_old_hosts(time_limit):
    """
    Récupère les hôtes à synchroniser.

    Voir le commentaire précédent sur les services pour le critère de
    désynchronisation. La situation est similaire pour les hôtes.

    @param time_limit: Date après laquelle on ignore les états.
    @type  time_limit: C{datetime.datetime}
    @return: Requête SQL permettant de récupérer la liste des hôtes
        dont l'état est obsolète.
    @rtype: C{sqlalchemy.orm.query.Query}
    """
    # Les hôtes OK/UP ne nous intéressent pas.
    # Un hôte peut être "OK" si un exploitant a "Forcé à fermer"
    # une alarme portant sur cet hôte.
    state_up = tables.StateName.statename_to_value(u'UP')
    state_ok = tables.StateName.statename_to_value(u'OK')

    q = DBSession.query(
        tables.Host.name.label('hostname'),
        # pour faire une UNION il faut le même nombre de colonnes
        expr_null().label('servicename'),
        tables.VigiloServer.name.label("vigiloserver"),
    ).join(
        (tables.State, tables.State.idsupitem == tables.Host.idhost),
    ).filter(
        # On ne veut resynchroniser que les états anormaux.
        ~tables.State.state.in_([state_up, state_ok])
    ).filter(
        tables.State.timestamp <= time_limit
    )
    return _add_ventilation(q)


def get_old_hls(hls_time_limit):
    """
    Récupère les services de haut niveau à synchroniser.

    On configure Nagios pour renvoyer l'état des services de haut niveau
    non-OK toutes les X minutes. L'état est alors mis à jour dans la base.
    Donc si on trouve un état dans la base qui n'a pas été mis à jour
    il y a moins de X minutes, c'est potentiellement un message perdu
    donc un service à re-synchroniser.

    La resynchronisation permet aussi d'initialiser proprement
    les services de haut niveau côté Vigilo lorsqu'ils sont
    dans un état nominal côté Nagios.

    @param hls_time_limit: Date après laquelle on ignore les états.
    @type  hls_time_limit: C{datetime.datetime}
    @return: Requête SQL permettant de récupérer la liste des services
        de haut niveau dont l'état est obsolète.
    @rtype: C{sqlalchemy.orm.query.Query}
    """
    # On force Nagios à envoyer une notification pour les états suivants :
    # OK : état nominal; Nagios n'émet pas de notification dans ce cas,
    #      mais on a besoin de l'information pour éviter des incohérences.
    # UNKNOWN : état initial des HLS dans Nagios. Donc il n'enverra pas
    #           de notification à Vigilo si le service est toujours UNKNOWN
    #           après la première vérification.
    state_ok = tables.StateName.statename_to_value(u'OK')
    state_unknown = tables.StateName.statename_to_value(u'UNKNOWN')

    q = DBSession.query(
        expr_null().label('hostname'),
        tables.HighLevelService.servicename,
        expr_null().label('vigiloserver'),
    ).select_from(
        tables.HighLevelService
    ).join(
        (tables.State,
            tables.State.idsupitem == tables.HighLevelService.idservice),
    ).filter(tables.State.state.in_([state_ok, state_unknown])
    ).filter(tables.State.timestamp <= hls_time_limit)
    return q


def get_desync_event_services():
    """
    Récupère les services dont l'état et les événements sont désynchronisés

    @return: Requête SQL permettant de récupérer la liste des services
        dont l'état ne correspond pas au dernier événement stocké.
    @rtype: C{sqlalchemy.orm.query.Query}
    """
    # Les hôtes OK/UP ne nous intéressent pas.
    # Un hôte peut être "OK" si un exploitant a "Forcé à fermer"
    # une alarme portant sur cet hôte.
    state_up = tables.StateName.statename_to_value(u'UP')
    state_ok = tables.StateName.statename_to_value(u'OK')

    # On récupère d'abord les hôtes DOWN/UNREACHABLE pour pouvoir ne remonter
    # que les services désynchronisés sur les hôtes OK/UP (#727)
    # Un hôte peut être "OK" si un exploitant a "Forcé à fermer"
    # une alarme portant sur cet hôte.
    hosts_down = DBSession.query(
        tables.Host.idhost,
    ).join(
        (tables.State, tables.State.idsupitem == tables.Host.idhost),
    ).filter(
        tables.State.state.in_([state_up, state_ok]),
    )

    q = DBSession.query(
        tables.Host.name.label('hostname'),
        tables.LowLevelService.servicename.label('servicename'),
        tables.VigiloServer.name.label("vigiloserver"),
    ).join(
        (tables.LowLevelService,
            tables.LowLevelService.idhost == tables.Host.idhost),
        (tables.State,
            tables.State.idsupitem == tables.LowLevelService.idservice),
        (tables.Event,
            tables.Event.idsupitem == tables.State.idsupitem),
    ).filter(
        tables.State.state != tables.Event.current_state
    ).filter(
        tables.Host.idhost.in_(hosts_down)
    )
    return _add_ventilation(q)


def get_desync_event_hosts():
    """
    Récupère les hôtes dont l'état et les événements sont désynchronisés.

    @return: Requête SQL permettant de récupérer la liste des hôtes
        dont l'état ne correspond pas au dernier événement stocké.
    @rtype: C{sqlalchemy.orm.query.Query}
    """
    q = DBSession.query(
        tables.Host.name.label('hostname'),
        # pour faire une UNION il faut le même nombre de colonnes
        expr_null().label('servicename'),
        tables.VigiloServer.name.label("vigiloserver"),
    ).join(
        (tables.State,
            tables.State.idsupitem == tables.Host.idhost),
        (tables.Event,
            tables.Event.idsupitem == tables.State.idsupitem),
    ).filter(
        tables.State.state != tables.Event.current_state
    )
    return _add_ventilation(q)


def keep_only_open_correvents(req):
    """
    Ne conserve que les évènements associés à un C{CorrEvent} encore ouvert

    @param req: Requête SQLAlchemy de filtrage pour ne garder que les
        C{CorrEvent} actifs.
    @type req: C{sqlalchemy.orm.query.Query}
    """
    return req.join(
            (EventsAggregate,
                EventsAggregate.idevent == tables.Event.idevent),
            (tables.CorrEvent,
                tables.CorrEvent.idcorrevent == EventsAggregate.idcorrevent),
        ).filter(
            tables.CorrEvent.ack != tables.CorrEvent.ACK_CLOSED
        )


def get_desync(time_limit, hls_time_limit, max_events=0):
    """
    Retourne les hôtes/services à synchroniser.

    @param time_limit: Date après laquelle on ignore les états
        en ce qui concerne les hôtes et les services de bas niveau.
        Passer la valeur C{None} pour désactiver cette partie
        de la resynchronisation.
    @type  time_limit: C{datetime.datetime} or C{None}
    @param hls_time_limit: Date après laquelle on ignore les états
        pour les services de haut niveau. Passer la valeur C{None}
        pour désactiver cette partie de la resynchronisation.
    @type  hls_time_limit: C{datetime.datetime} or C{None}
    @param max_events: Nombre maximum d'éléments.
    @type  max_events: C{int}
    @return: Liste d'hôtes/services à synchroniser
    @rtype: C{list} of C{mixed}

    @todo: récupérer aussi l'adresse du serveur nagios dans la ventilation
    """
    resync = []

    if time_limit is not None:
        # Resynchronisation des états des LLS/hosts.
        LOGGER.info(_("Listing hosts/services states older than %s"),
                     time_limit.strftime("%Y-%m-%d %H:%M:%S"))
        resync.extend([
            get_old_lls(time_limit),
            get_old_hosts(time_limit),
        ])

    if hls_time_limit is not None:
        # Resynchronisation des états des HLS.
        LOGGER.info(_("Listing high-level services states older than %s"),
                     hls_time_limit.strftime("%Y-%m-%d %H:%M:%S"))
        resync.append(get_old_hls(hls_time_limit))

    resync.append(keep_only_open_correvents(get_desync_event_services()))
    resync.append(keep_only_open_correvents(get_desync_event_hosts()))

    to_update = union(*resync, correlate=False)
    if max_events:
        to_update = to_update.limit(max_events)

    try:
        return DBSession.query(to_update.alias()).all()
    except (InvalidRequestError, OperationalError) as e:
        LOGGER.error(_('Database exception raised: %s'),
                        get_error_message(e))
        raise e



class SyncSender(object):
    """
    Envoi des demandes de synchronisation sur le bus, à destination des serveurs Nagios
    """

    #implements(IPushProducer)


    def __init__(self, to_sync):
        """
        @param to_sync: Résultats de la requête à la base de données. Chaque
            résultat doit disposer d'une propriété C{hostname} et d'une
            propriété C{servicename}
        @type  to_sync: C{list}
        """
        self.to_sync = to_sync
        self.publisher = None # BusSender


    @defer.inlineCallbacks
    def askNagios(self, client):
        """Envoie les demandes de notifications à Nagios"""
        for supitem in self.to_sync:
            message = self._buildNagiosMessage(supitem)
            yield self.publisher.write(message)


    def _buildNagiosMessage(self, supitem):
        """
        Construit le message de commande Nagios approprié.

        @param supitem: Hôte ou service concerné. Doit disposer d'une propriété
            C{hostname} et d'une propriété C{servicename}
        @type  supitem: C{object}
        @return: Le message pour Nagios
        @rtype: C{dict}
        @todo: ajouter une clé routing_key pour n'envoyer qu'au serveur Nagios
            concerné
        """
        msg = { "type": "nagios",
                "timestamp": int(time.time()),
                }

        if supitem.vigiloserver:
            msg['routing_key'] = supitem.vigiloserver

        if not supitem.hostname:
            msg["cmdname"] = "SEND_CUSTOM_SVC_NOTIFICATION"
            msg["value"] = ("High-Level-Services;%s;0;vigilo;syncevents"
                         % (supitem.servicename, ))
            LOGGER.debug(
                _("Asking for update on high-level service \"%(service)s\""),
                {"service": supitem.servicename})
        elif supitem.servicename:
            msg["cmdname"] = "SEND_CUSTOM_SVC_NOTIFICATION"
            msg["value"] = ("%s;%s;0;vigilo;syncevents"
                         % (supitem.hostname, supitem.servicename))
            LOGGER.debug(_("Asking for update on service \"%(service)s\" "
                           "on host \"%(host)s\""),
                         {"host": supitem.hostname,
                          "service": supitem.servicename})
        else:
            msg["cmdname"] = "SEND_CUSTOM_HOST_NOTIFICATION"
            msg["value"] = "%s;0;vigilo;syncevents" % supitem.hostname
            LOGGER.debug(_("Asking for update on host \"%(host)s\""),
                         {"host": supitem.hostname})
        return msg



def main():
    # Options
    opt_parser = OptionParser()
    opt_parser.add_option("-d", "--debug", action="store_true")
    opt_parser.add_option("-n", "--dry-run", action="store_true",
                          help="Do not send synchronization messages")
    opts, args = opt_parser.parse_args()
    if args:
        opt_parser.error("No arguments allowed")
    if opts.debug:
        LOGGER.parent.setLevel(logging.DEBUG)
        log_traffic = True
    else:
        log_traffic = False

    # Lock
    lockfile = settings["connector-syncevents"].get("lockfile",
                        "/var/lock/subsys/vigilo-connector-syncevents/lock")
    lock_result = grab_lock(lockfile)
    if not lock_result:
        sys.exit(1)

    # Récupération des événements corrélés dont la durée
    # de consolidation sont supérieures à celles configurées.
    try:
        minutes_old = int(settings['connector-syncevents']["minutes_old"])
    except KeyError:
        minutes_old = 45

    try:
        hls_minutes_old = int(settings['connector-syncevents']["hls_minutes_old"])
    except KeyError:
        hls_minutes_old = -1

    now = datetime.now()
    if minutes_old < 0:
        time_limit = None
    else:
        time_limit = now - timedelta(minutes=int(minutes_old))

    if hls_minutes_old < 0:
        hls_time_limit = None
    else:
        hls_time_limit = now - timedelta(minutes=int(hls_minutes_old))

    try:
        max_events = int(settings['connector-syncevents']["max_events"])
    except KeyError:
        max_events = 0
    events = get_desync(time_limit, hls_time_limit, max_events)
    if not events:
        LOGGER.info(_("No events to synchronize"))
        return # rien à faire
    LOGGER.info(_("Found %d event(s) to synchronize"), len(events))

    if opts.dry_run:
        for supitem in events:
            if not supitem.hostname:
                LOGGER.debug(
                    _("Asking for update on high-level service \"%(service)s\""),
                    {"service": supitem.servicename})
            elif supitem.servicename:
                LOGGER.debug(_("Asking for update on service \"%(service)s\" "
                               "on host \"%(host)s\""),
                             {"host": supitem.hostname,
                              "service": supitem.servicename})
            else:
                LOGGER.debug(_("Asking for update on host \"%(host)s\""),
                             {"host": supitem.hostname})
        return

    osc = oneshotclient_factory(settings)
    osc.client.factory.noisy = False

    syncsender = SyncSender(events)
    osc.setHandler(syncsender.askNagios)

    bus_publisher = buspublisher_factory(settings, osc.client)
    syncsender.publisher = bus_publisher

    return osc.run(log_traffic=log_traffic)
