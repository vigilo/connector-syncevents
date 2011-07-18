# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Ce composant lit les événements en cours dans la base de données, et demande
à Nagios de renvoyer les états pour les services concernés, afin de garantir
la synchronicité des deux bases.
"""

import time
from datetime import datetime, timedelta

from vigilo.common.conf import settings
settings.load_module(__name__)

from vigilo.models.configure import configure_db
configure_db(settings['database'], 'sqlalchemy_')

from vigilo.common.logging import get_logger
LOGGER = get_logger(__name__)

from vigilo.common.gettext import translate
_ = translate(__name__)

from twisted.internet import defer
from twisted.application import service, app
from twisted.internet import reactor
from twisted.words.xish import domish
from sqlalchemy.exc import InvalidRequestError, OperationalError
from sqlalchemy.sql.expression import null as expr_null, union

from vigilo.pubsub.xml import NS_COMMAND
from vigilo.connector import client
from vigilo.connector.forwarder import PubSubSender
from vigilo.models.session import DBSession
from vigilo.models import tables


def get_events(time_limit, max_events=0):
    """
    Retourne les événements corrélés plus récents que L{time_limit}.

    @param time_limit: Date après laquelle on ignore les évènements.
    @type  time_limit: C{datetime.datetime}
    @param max_events: Nombre maximum d'événements.
    @type  max_events: C{int}
    @return: Liste d'évènements corrélés.
    @rtype: C{list} of C{mixed}
    """
    LOGGER.info(_("Listing events in the database older than %s"),
                 time_limit.strftime("%Y-%m-%d %H:%M:%S"))

    # On récupère d'abord les hôtes DOWN pour pouvoir ne remonter que les
    # services désynchronisés sur les hôtes UP (#727)
    hosts_down = DBSession.query(
        tables.Host.idhost,
    ).join(
        (tables.State,
            tables.State.idsupitem == tables.Host.idhost),
        (tables.StateName,
            tables.StateName.idstatename == tables.State.state),
    ).filter(
        tables.StateName.statename == u"DOWN",
    )

    # On récupère les services à synchroniser
    lls_to_update = DBSession.query(
        tables.Host.name.label('hostname'),
        tables.LowLevelService.servicename.label('servicename'),
    ).join(
        (tables.LowLevelService,
            tables.LowLevelService.idhost == tables.Host.idsupitem),
        (tables.State,
            tables.State.idsupitem == tables.LowLevelService.idservice),
        (tables.StateName,
            tables.StateName.idstatename == tables.State.state),
    ).filter(
        tables.StateName.statename.in_([u"CRITICAL", u"WARNING", u"UNKNOWN"]),
    ).filter(
        tables.State.timestamp <= time_limit,
    ).filter(
        ~tables.Host.idhost.in_(hosts_down)
    )

    # On récupère les hôtes à synchroniser
    host_to_update = DBSession.query(
        tables.Host.name.label('hostname'),
        # pour faire une UNION il faut le même nombre de colonnes
        expr_null().label('servicename'),
    ).join(
        (tables.State,
            tables.State.idsupitem == tables.Host.idhost),
        (tables.StateName,
            tables.StateName.idstatename == tables.State.state),
    ).filter(
        tables.StateName.statename == u"DOWN",
    ).filter(
        tables.State.timestamp <= time_limit,
    )

    to_update = union(
        lls_to_update,
        host_to_update,
        correlate=False
    )

    if max_events:
        to_update = to_update.limit(max_events)

    try:
        return DBSession.query(to_update.alias()).all()
    except (InvalidRequestError, OperationalError), e:
        LOGGER.exception(_('Database exception raised: %s'), e)
        raise e


class SyncSender(PubSubSender):
    """
    Envoi des demandes de synchronisation sur le bus, à destination des serveurs Nagios
    """

    def __init__(self, to_sync):
        """
        @param to_sync: Résultats de la requête à la base de données. Chaque
            résultat doit disposer d'une propriété C{hostname} et d'une
            propriété C{servicename}
        @type  to_sync: C{list}
        """
        super(SyncSender, self).__init__()
        # pas de trucs compliqués
        self.max_send_simult = 1
        self.batch_send_perf = 1
        # ce qu'il faut envoyer
        self.to_sync = to_sync
        # ne pas spammer les logs
        self._max_log_each = 50

    def connectionInitialized(self):
        """À la connexion, on envoie les demandes, puis on se déconnecte"""
        super(SyncSender, self).connectionInitialized()
        d = self.askNagios()
        d.addCallback(lambda x: self.quit())

    @defer.inlineCallbacks
    def askNagios(self):
        """Envoie les demandes de notifications à Nagios"""
        log_each = len(self.to_sync) < self._max_log_each
        for supitem in self.to_sync:
            message = self._buildNagiosMessage(supitem, log_each)
            yield self.publishXml(message)

    def _buildNagiosMessage(self, supitem, do_log):
        """
        Construit le message de commande Nagios approprié
        @param supitem: Hôte ou service concerné. Doit disposer d'une propriété
            C{hostname} et d'une propriété C{servicename}
        @type  supitem: C{object}
        """
        if supitem.servicename:
            if do_log:
                LOGGER.info(_("Asking update for service \"%(service)s\" "
                              "on host \"%(host)s\""),
                            {"host": supitem.hostname,
                             "service": supitem.servicename})
            return self._buildNagiosServiceMessage(supitem.hostname,
                                                   supitem.servicename)
        else:
            if do_log:
                LOGGER.info(_("Asking update for host \"%(host)s\""),
                            {"host": supitem.hostname})
            return self._buildNagiosHostMessage(supitem.hostname)

    def _buildNagiosServiceMessage(self, hostname, servicename):
        """
        Construit un message de demande de notification pour un service Nagios
        @param hostname: nom d'hôte
        @type  hostname: C{str}
        @param servicename: nom de service
        @type  servicename: C{str}
        """
        msg = domish.Element((NS_COMMAND, 'command'))
        msg.addElement('timestamp', content=str(int(time.time())))
        msg.addElement('cmdname', content="SEND_CUSTOM_SVC_NOTIFICATION")
        cmdvalue = "%s;%s;0;vigilo;syncevents" % (hostname, servicename)
        msg.addElement('value', content=cmdvalue)
        return msg

    def _buildNagiosHostMessage(self, hostname):
        """
        Construit un message de demande de notification pour un hôte Nagios
        @param hostname: nom d'hôte
        @type  hostname: C{str}
        """
        msg = domish.Element((NS_COMMAND, 'command'))
        msg.addElement('timestamp', content=str(int(time.time())))
        msg.addElement('cmdname', content="SEND_CUSTOM_HOST_NOTIFICATION")
        cmdvalue = "%s;0;vigilo;syncevents" % hostname
        msg.addElement('value', content=cmdvalue)
        return msg

    def quit(self):
        """Déconnexion du bus et arrêt du connecteur"""
        self.xmlstream.sendFooter()
        reactor.stop()



def main():
    """
    Fonction principale
    """
    # Récupération des événements corrélés dont la priorité et la
    # durée de consolidation sont supérieures à celles configurées.
    try:
        minutes_old = int(settings['connector-syncevents']["minutes_old"])
    except KeyError:
        minutes_old = 35
    time_limit = datetime.now() - timedelta(minutes=int(minutes_old))
    try:
        max_events = int(settings['connector-syncevents']["max_events"])
    except KeyError:
        max_events = 0
    events = get_events(time_limit, max_events)
    if not events:
        LOGGER.info(_("No events to synchronize"))
        return # rien à faire
    LOGGER.info(_("Found %d event(s) to synchronize"), len(events))

    xmpp_client = client.client_factory(settings)
    xmpp_client.factory.noisy = False
    sender = SyncSender(events)
    sender.setHandlerParent(xmpp_client)

    application = service.Application('Vigilo state synchronizer')
    xmpp_client.setServiceParent(application)
    app.startApplication(application, False)
    reactor.run()
    LOGGER.info(_("Done sending notification requests"))

