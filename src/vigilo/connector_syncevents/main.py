# vim: set fileencoding=utf-8 sw=4 ts=4 et :
"""
Ce composant lit les événements en cours dans la base de données, et demande à
Nagios de renvoyer les états pour les services concernés, afin de garantir la
synchronicité des deux bases.
"""

import sys
import time
from datetime import datetime, timedelta

from vigilo.common.conf import settings
settings.load_module(__name__)

from vigilo.models.configure import configure_db
configure_db(settings['database'], 'sqlalchemy_',
    settings['database']['db_basename'])

from vigilo.common.logging import get_logger
LOGGER = get_logger(__name__)

from vigilo.common.gettext import translate
_ = translate(__name__)

from twisted.internet import defer
from twisted.application import service
from twisted.internet import reactor
from twisted.python import log
from twisted.words.protocols.jabber.jid import JID
from twisted.words.xish import domish
from twisted.words.protocols.jabber import xmlstream, sasl
from wokkel.pubsub import Item, PubSubRequest
#from wokkel import client
from sqlalchemy.exc import InvalidRequestError, OperationalError
from sqlalchemy.sql.expression import null as expr_null, union

from vigilo.pubsub import NodeOwner
from vigilo.pubsub.xml import NS_COMMAND
from vigilo.connector import client
from vigilo.connector.forwarder import PubSubSender
from vigilo.models.session import DBSession
from vigilo.models import tables


def get_events(minutes_old):
    """
    Retourne les événements corrélés dont la date de dernier changement d'état
    est antérieure ou égale à la date courante moins C{minutes_old} minutes.

    @param minutes_old: Durée de consolidation en minutes.
    @type  minutes_old: C{int}
    @return: Liste d'évènements corrélés.
    @rtype: C{list} of C{mixed}
    """
    lls_correvents = DBSession.query(
        tables.StateName.statename,
        tables.CorrEvent.idcorrevent.label('id'),
        tables.Host.name.label('hostname'),
        tables.LowLevelService.servicename.label('servicename'),
    ).join(
        (tables.Event,
            tables.Event.current_state == tables.StateName.idstatename),
        (tables.CorrEvent, tables.CorrEvent.idcause == tables.Event.idevent),
        (tables.Host, tables.Host.idsupitem == tables.LowLevelService.idhost),
        (tables.LowLevelService,
            tables.LowLevelService.idservice == tables.Event.idsupitem),
    ).filter(
        tables.CorrEvent.status != u'AAClosed',
    ).filter(
        tables.Event.timestamp <= datetime.today()
            - timedelta(minutes=int(minutes_old)),
    )

    host_correvents = DBSession.query(
        tables.StateName.statename,
        tables.CorrEvent.idcorrevent.label('id'),
        tables.Host.name.label('hostname'),
        expr_null().label('servicename'),
    ).join(
        (tables.Event,
            tables.Event.current_state == tables.StateName.idstatename),
        (tables.CorrEvent, tables.CorrEvent.idcause == tables.Event.idevent),
        (tables.SupItem, tables.SupItem.idsupitem == tables.Event.idsupitem),
        (tables.Host, tables.Host.idsupitem == tables.SupItem.idsupitem),
    ).filter(
        tables.CorrEvent.status != u'AAClosed',
    ).filter(
        tables.Event.timestamp <= datetime.today()
            - timedelta(minutes=int(minutes_old)),
    )

    correvents = union(
        lls_correvents,
        host_correvents,
        correlate=False
    ).alias()

    try:
        return DBSession.query(correvents).all()
    except (InvalidRequestError, OperationalError), e:
        LOGGER.exception(_(u'Database exception raised: %s'), e)
        raise e


#def send_statistics(xmlstream, _service, node):
#    """
#    Envoie des statistiques sur les événements corrélés actuellement
#    affichés dans VigiBoard.
#
#    @param xmlstream: Canal de communication avec le bus XMPP.
#    @param _service: Service de publication à utiliser.
#    @type _service: C{JID}
#    @param node: Nom du nœud XMPP vers lequel les statistiques
#        doivent être envoyées.
#    @type node: C{basestring}
#    @return: Deferred sur l'envoi du message au nœud XMPP.
#    @rtype: C{defer.Deferred}
#    """
#    # Récupération du nombre de nouveaux événements corrélés.
#    new_correvents = DBSession.query(CorrEvent).filter(
#        CorrEvent.status == u'None').count()
#    LOGGER.info(_('There are %(count)d new correlated events.') % {
#        'count': new_correvents,
#    })
#
#    # Récupération du nombre d'événements corrélés non fermés,
#    # en fonction de l'état courant de l'événement corrélé.
#    db_statistics = DBSession.query(
#            StateName.statename,
#            sql_functions.count().label("count"),
#        ).join(
#            (Event, Event.current_state == StateName.idstatename),
#            (CorrEvent, CorrEvent.idcause == Event.idevent),
#        ).filter(
#            CorrEvent.status != u'AAClosed',
#        ).group_by(StateName.statename).all()
#
#    # Création d'un domish.Element avec les statistiques.
#    statistics = domish.Element((NS_STATISTICS, 'statistics'))
#    xml_new = statistics.addElement("new")
#    xml_new.addContent(str(new_correvents))
#
#    active = statistics.addElement("active")
#    for stat in db_statistics:
#        xml_stat = active.addElement("count")
#        xml_stat['state'] = stat.statename
#        xml_stat.addContent(str(stat.count))
#        LOGGER.info(_('There are %(count)d active correlated events in the '
#            '"%(state)s" state.') % {
#            'count': stat.count,
#            'state': stat.statename,
#        })
#
#    # Création et envoi du message.
#    item = Item(payload=statistics)
#    request = PubSubRequest('publish')
#    request.recipient = _service
#    request.nodeIdentifier = node
#    request.items = [item]
#    request.sender = None
#
#    def cb(response):
#        LOGGER.info(_('The statistics were successfully sent to the bus.'))
#        return response
#
#    def eb(error):
#        LOGGER.info(_('An error occurred while sending the statistics (%r).') %
#                        error)
#        return error
#
#    d = request.send(xmlstream)
#    d.addCallbacks(cb, eb)
#    return d


#class DeferredMaybeTLSClientFactory(client.DeferredClientFactory):
#    def __init__(self, jid, password, require_tls):
#        super(DeferredMaybeTLSClientFactory, self).__init__(jid, password)
#        self.addBootstrap(xmlstream.STREAM_CONNECTED_EVENT, self._connected)
#        self.removeBootstrap(xmlstream.INIT_FAILED_EVENT, self.deferred.errback)
#        self.addBootstrap(xmlstream.INIT_FAILED_EVENT, self._init_failure)
#        self.require_tls = require_tls
#
#    def _connected(self, xs):
#        """
#        On modifie dynamiquement l'attribut "required" du plugin
#        d'authentification TLSInitiatingInitializer créé automatiquement
#        par wokkel, pour imposer TLS si l'administrateur le souhaite.
#        """
#        for initializer in xs.initializers:
#            if isinstance(initializer, xmlstream.TLSInitiatingInitializer):
#                initializer.required = self.require_tls
#
#    def _init_failure(self, failure):
#        global RESULT
#
#        if failure.check(sasl.SASLNoAcceptableMechanism, sasl.SASLAuthError):
#            LOGGER.error(_("Authentication failed:"))
#            reactor.stop()
#            RESULT = 1
#            return failure
#        if failure.check(xmlstream.FeatureNotAdvertized):
#            LOGGER.error(_("Server does not support TLS encryption."))
#            reactor.stop()
#            RESULT = 1
#            return failure
#        return self.deferred.errback(failure)


class SyncSender(PubSubSender):
    def __init__(self, to_sync)
        super(SyncSender, self).__init__()
        # pas de trucs compliqués
        self.mas_send_simult = 1
        self.batch_send_perf = 1
        # ce qu'il faut envoyer
        self.to_sync = to_sync

    def connectionInitialized(self):
        super(SyncSender, self).connectionInitialized()
        d = self.askNagios()
        d.addCallback(lambda x: self.stop())

    def askNagios(self):
        replies = []
        for service in self.to_sync:
            message = self._buildNagiosMessage(service)
            reply = self.publishXml(message)
            replies.append(reply)
        return defer.DeferredList(replies)

    def _buildNagiosMessage(self, service):
        print service
        if service.servicename:
            return self._buildNagiosServiceMessage(service.hostname,
                                                   service.servicename)
        else:
            return self._buildNagiosHostMessage(service.hostname)

    def _buildNagiosServiceMessage(self, host, service):
        msg = (
            '<command xmlns="%(namespace)s">'
                '<timestamp>%(timestamp)d</timestamp>'
                '<cmdname>SEND_CUSTOM_SVC_NOTIFICATION</cmdname>'
                '<value>%(host)s;%(service)s;0;vigilo:syncevents</value>'
            '</command>' % {
                "namespace": NS_COMMAND,
                "timestamp": int(time.time()),
                "host": self.hostname,
                "service": self.servicename,
                }
             )
    def _buildNagiosHostMessage(self, host):
        msg = (
            '<command xmlns="%(namespace)s">'
                '<timestamp>%(timestamp)d</timestamp>'
                '<cmdname>SEND_CUSTOM_HOST_NOTIFICATION</cmdname>'
                '<value>%(host)s;0;vigilo:syncevents</value>'
            '</command>' % {
                "namespace": NS_COMMAND,
                "timestamp": int(time.time()),
                "host": self.hostname,
                }
             )

    def stop(self):
        self.xmlstream.sendFooter()
        reactor.callLater(0.5, reactor.stop)


#def create_client():
#
#    from vigilo.pubsub.checknode import VerificationNode
#    try:
#        require_tls = settings['bus'].as_bool('require_tls')
#    except KeyError:
#        require_tls = False
#
#    # Temps max entre 2 tentatives de connexion (par défaut 1 min)
#    max_delay = int(settings["bus"].get("max_reconnect_delay", 60))
#
#    xmpp_client = VigiloXMPPClient(
#            JID(settings['bus']['jid']),
#            settings['bus']['password'],
#            host,
#            require_tls=require_tls,
#            max_delay=max_delay)
#    xmpp_client.setName('xmpp_client')
#    return
#
#    try:
#        xmpp_client.logTraffic = settings['bus'].as_bool('log_traffic')
#    except KeyError:
#        xmpp_client.logTraffic = False
#
#    # Création de la factory pour le client XMPP.
#    service.Application('XMPP client')
#    factory = DeferredMaybeTLSClientFactory(
#        JID(settings['bus']['jid']),
#        settings['bus']['password'],
#        require_tls,
#    )
#
#    try:
#        factory.streamManager.logTraffic = \
#            settings['bus'].as_bool('log_traffic')
#    except KeyError:
#        factory.streamManager.logTraffic = False
#
#    # Création du client XMPP
#    d = client.clientCreator(factory)



def main():
    """
    Fonction principale
    """
    # Récupération des événements corrélés dont la priorité et la
    # durée de consolidation sont supérieures à celles configurées.
    try:
        minutes_old = int(settings['connector-syncevents']["minutes_old"])
    except KeyError:
        minutes_old = 30
    events = get_events(minutes_old)
    if not events:
        return # rien à faire

    xmpp_client = client.client_factory(settings)
    sender = PubSubSender(events)
    sender.setHandlerParent(xmpp_client)

    reactor.run()


if __name__ == '__main__':
    main()

