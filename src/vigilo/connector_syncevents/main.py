# vim: set fileencoding=utf-8 sw=4 ts=4 et :
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


def get_events(time_limit):
    """
    Retourne les événements corrélés plus récents que L{time_limit}.

    @param time_limit: Date après laquelle on ignore les évènements.
    @type  time_limit: C{datetime.datetime}
    @return: Liste d'évènements corrélés.
    @rtype: C{list} of C{mixed}
    """
    LOGGER.debug("Listing events in the database older than %s",
                 time_limit.strftime("%Y-%m-%d %H:%M:%S"))

    lls_correvents = DBSession.query(
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
    )

    host_correvents = DBSession.query(
        tables.Host.name.label('hostname'),
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

    correvents = union(
        lls_correvents,
        host_correvents,
        correlate=False
    ).alias()

    try:
        return DBSession.query(correvents).all()
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
        self.mas_send_simult = 1
        self.batch_send_perf = 1
        # ce qu'il faut envoyer
        self.to_sync = to_sync

    def connectionInitialized(self):
        """À la connexion, on envoie les demandes, puis on se déconnecte"""
        super(SyncSender, self).connectionInitialized()
        d = self.askNagios()
        d.addCallback(lambda x: self.quit())

    def askNagios(self):
        """Envoie les demandes de notifications à Nagios"""
        replies = []
        for supitem in self.to_sync:
            message = self._buildNagiosMessage(supitem)
            reply = self.publishXml(message)
            replies.append(reply)
        return defer.DeferredList(replies)

    def _buildNagiosMessage(self, supitem):
        """
        Construit le message de commande Nagios approprié
        @param supitem: Hôte ou service concerné. Doit disposer d'une propriété
            C{hostname} et d'une propriété C{servicename}
        @type  supitem: C{object}
        """
        if supitem.servicename:
            return self._buildNagiosServiceMessage(supitem.hostname,
                                                   supitem.servicename)
        else:
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
        cmdvalue = "%s;%s;0;vigilo:syncevents" % (hostname, servicename)
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
        cmdvalue = "%s;0;vigilo:syncevents" % hostname
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
    events = get_events(time_limit)
    if not events:
        LOGGER.debug("No events to synchronize")
        return # rien à faire
    LOGGER.debug("Found %d event(s) to synchronize", len(events))

    xmpp_client = client.client_factory(settings)
    sender = SyncSender(events)
    sender.setHandlerParent(xmpp_client)

    application = service.Application('Vigilo state synchronizer')
    xmpp_client.setServiceParent(application)
    app.startApplication(application, False)
    reactor.run()
    LOGGER.debug("Done sending notification requests")

