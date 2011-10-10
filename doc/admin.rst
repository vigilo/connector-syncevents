**********************
Guide d'administration
**********************

Ce document a pour objectif de présenter le fonctionnement du module
connector-syncevents aux administrateurs.


Installation
============

Pré-requis logiciels
--------------------
Afin de pouvoir faire fonctionner le connecteur de métrologie, l'installation
préalable des logiciels suivants est requise :

* python (>= 2.5), sur la machine où le connecteur est installé
* ejabberd (>= 2.1), éventuellement sur une machine distante
* postgresql-server (>= 8.3), éventuellement sur une machine distante

Reportez-vous aux manuels de ces différents logiciels pour savoir comment
procéder à leur installation sur votre machine.

Ce module requiert également la présence de plusieurs dépendances Python. Ces
dépendances seront automatiquement installées en même temps que le paquet du
connecteur.

Installation du paquet RPM
--------------------------
L'installation du connecteur se fait en installant simplement le paquet RPM
« vigilo-connector-metro ». La procédure exacte d'installation dépend du
gestionnaire de paquets utilisé. Les instructions suivantes décrivent la
procédure pour les gestionnaires de paquets RPM les plus fréquemment
rencontrés.

Installation à l'aide de urpmi::

    urpmi vigilo-connector-syncevents

Installation à l'aide de yum::

    yum install vigilo-connector-syncevents

Création du compte XMPP
-----------------------
Le connector-metro nécessite qu'un compte soit créé sur la machine hébergeant
le bus XMPP pour le composant.

Les comptes doivent être créés sur la machine qui héberge le serveur ejabberd,
à l'aide de la commande::

    $ su ejabberd -c \
        'ejabberdctl register connector-syncevents localhost connector-syncevents'

**Note :** si plusieurs instances du connecteur s'exécutent simultanément sur
le parc, chaque instance doit disposer de son propre compte (JID). Dans le cas
contraire, des conflits risquent de survenir qui peuvent perturber le bon
fonctionnement de la solution.



Configuration
=============

Le module connector-metro est fourni avec un fichier de configuration situé
par défaut dans ``/etc/vigilo/connector-syncevents/settings.ini``.

.. include:: ../../connector/doc/admin-conf-1.rst

.. Lister ici les sections spécifiques au connecteur

connector-syncevents
    Contient les options spécifiques au connecteur syncevents.

database
    Contient les options relatives à la connexion à la base de données de
    Vigilo.

.. include:: ../../connector/doc/admin-conf-2.rst

.. include:: ../../models/doc/admin-conf.rst

.. Documenter ici les sections spécifiques au connecteur

Configuration spécifique au connecteur syncevents
-------------------------------------------------
Le connecteur syncevents dispose d'une seule option de configuration :
« minutes_old ». Cette option détermine l'âge minimum d'une alerte en minutes,
au-dessous duquel on ne demande pas de mise à jour à Nagios. Vigilo configure
Nagios pour qu'il ré-envoie les notifications après 30 minutes, il faut donc
régler ici une valeur légèrement supérieure, pour ne cibler que les états
désynchronisés.

La valeur par défaut est 35 minutes.

Si cette valeur ou la fréquence des ré-expéditions de notifications dans Nagios
doivent être modifiées, il faut faire attention à toujours garder les deux en
cohérence.



Utilisation
===========

Lancement du composant
----------------------
Le composant connector-syncevents est construit de sorte qu'une fois lancé, il
liste les états qui semblent désynchronisés en base de données, et envoie des
messages à Nagios pour qu'il ré-expédie les notifications sur ces états. Les
données transmises sont précisées au chapitre .

S'il n'y a pas d'état à synchroniser, le connecteur s'arrête sans se connecter
au bus. Le lancement se fait en exécutant la commande .

Activation régulière
--------------------
Il est recommandé de planifier l'exécution de la commande à intervalles
réguliers (par exemple, toutes les 10 minutes) afin d'effectuer des
re-synchronisations assez fréquemment. Grâce à la limite d'âge configurée,
seuls les événements qui semblent dé-synchronisés seront sélectionnés. Il y a
donc peu d'impact à réaliser cette vérification assez fréquemment (seule une
requête SQL est effectuée). Une bonne pratique consiste à exécuter
périodiquement cette commande à l'aide d'un planificateur de tâches comme
*cron*.

Le listing suivant donne un exemple de configuration utilisant *cron*::

    # minutes heures n°jour mois jour commande > journal
    # Exécution de la commande de synchronisation.
    */10 * * * * vigilo-syncevents /usr/bin/vigilo-connector-syncevents >/dev/null

Cette commande doit être lancée soit en tant que l'utilisateur
« vigilo-syncevents », soit en tant que « root », pour avoir accès à son
fichier settings.ini. Il est recommandé de ne pas utiliser « root », mais de
lui préférer l'utilisateur dédié.

À l'installation, le connecteur installe cette tâche planifiée dans *cron*,
mais la laisse désactivée. Pour l'activer, il suffit de dé-commenter l'entrée
dans le fichier ``/etc/cron.d/vigilo-connector-syncevents``.

Nature des informations transmises
----------------------------------
Le connecteur syncevents envoie des messages de commande qui seront récupérées
par le connector-nagios, puis transmis à Nagios après avoir été convertis vers
la syntaxe adéquate.

Ce messages sont des demandes de ré-émission de notification, définis dans la
documentation Nagios aux URL suivantes :

* `SEND_CUSTOM_HOST_NOTIFICATION`_
* `SEND_CUSTOM_SVC_NOTIFICATION`_

.. _SEND_CUSTOM_HOST_NOTIFICATION: http://old.nagios.org/developerinfo/externalcommands/commandinfo.php?command_id=134
.. _SEND_CUSTOM_SVC_NOTIFICATION: http://old.nagios.org/developerinfo/externalcommands/commandinfo.php?command_id=135

Pour circuler sur le bus XMPP, ces demandes sont encodées dans un message
Vigilo de type « command », dont un exemple suit::

    <command xmlns='http://www.projet-vigilo.org/xmlns/command1'>
      <cmdname>SEND_CUSTOM_SVC_NOTIFICATION</cmdname>
      <value>server.example.com;Load 01;0;vigilo;syncevents</value>
    </command>

Après réception par Nagios, ce dernier va ré-expédier une notification de
l'état de l'hôte ou du service concerné, qui suivra le chemin classique des
notifications dans Vigilo : elle sera réceptionnée par le corrélateur, qui
mettra à jour l'état dans la base Vigilo.



Annexes
=======

.. include:: ../../connector/doc/glossaire.rst


.. vim: set tw=79 :
