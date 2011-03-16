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
configure_db(settings['database'], 'sqlalchemy_')

from vigilo.common.logging import get_logger
LOGGER = get_logger(__name__)

from vigilo.common.gettext import translate
_ = translate(__name__)

from twisted.internet import defer
from twisted.application import service, app
from twisted.internet import reactor
from twisted.python import log
from twisted.words.protocols.jabber.jid import JID
from twisted.words.xish import domish
from twisted.words.protocols.jabber import xmlstream, sasl
from wokkel.pubsub import Item, PubSubRequest
from sqlalchemy.exc import InvalidRequestError, OperationalError
from sqlalchemy.sql.expression import null as expr_null, union
from sqlalchemy import or_

from vigilo.pubsub import NodeOwner
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
        LOGGER.exception(_(u'Database exception raised: %s'), e)
        raise e


class SyncSender(PubSubSender):
    def __init__(self, to_sync):
        super(SyncSender, self).__init__()
        # pas de trucs compliqués
        self.mas_send_simult = 1
        self.batch_send_perf = 1
        # ce qu'il faut envoyer
        self.to_sync = to_sync

    def connectionInitialized(self):
        super(SyncSender, self).connectionInitialized()
        d = self.askNagios()
        d.addCallback(lambda x: self.quit())

    def askNagios(self):
        replies = []
        for service in self.to_sync:
            message = self._buildNagiosMessage(service)
            reply = self.publishXml(message)
            replies.append(reply)
        return defer.DeferredList(replies)

    def _buildNagiosMessage(self, service):
        if service.servicename:
            return self._buildNagiosServiceMessage(service.hostname,
                                                   service.servicename)
        else:
            return self._buildNagiosHostMessage(service.hostname)

    def _buildNagiosServiceMessage(self, hostname, servicename):
        msg = domish.Element((NS_COMMAND, 'command'))
        msg.addElement('timestamp', content=str(int(time.time())))
        msg.addElement('cmdname', content="SEND_CUSTOM_SVC_NOTIFICATION")
        cmdvalue = "%s;%s;0;vigilo:syncevents" % (hostname, servicename)
        msg.addElement('value', content=cmdvalue)
        return msg

    def _buildNagiosHostMessage(self, hostname):
        msg = domish.Element((NS_COMMAND, 'command'))
        msg.addElement('timestamp', content=str(int(time.time())))
        msg.addElement('cmdname', content="SEND_CUSTOM_HOST_NOTIFICATION")
        cmdvalue = "%s;0;vigilo:syncevents" % hostname
        msg.addElement('value', content=cmdvalue)
        return msg

    def quit(self):
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
        return # rien à faire

    xmpp_client = client.client_factory(settings)
    sender = SyncSender(events)
    sender.setHandlerParent(xmpp_client)

    application = service.Application('Vigilo state synchronizer')
    xmpp_client.setServiceParent(application)
    app.startApplication(application, False)
    reactor.run()


if __name__ == '__main__':
    main()

