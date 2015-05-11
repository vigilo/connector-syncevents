**********************
Guide d'administration
**********************


Installation
============

Pré-requis logiciels
--------------------
Afin de pouvoir faire fonctionner le connecteur syncevents, l'installation
préalable des logiciels suivants est requise :

* python (>= 2.5), sur la machine où le connecteur est installé
* rabbitmq (>= 2.7.1), éventuellement sur une machine distante
* postgresql-server (>= 8.3), éventuellement sur une machine distante


.. Installation du RPM
.. include:: ../buildenv/doc/package.rst

.. Compte sur le bus et fichier de configuration
.. include:: ../../connector/doc/admin-conf-1.rst

.. Lister ici les sections spécifiques au connecteur

connector-syncevents
    Contient les options spécifiques au connecteur syncevents.

database
    Contient les options relatives à la connexion à la base de données de
    Vigilo.

.. include:: ../../connector/doc/admin-conf-2.rst

.. Documenter ici les sections spécifiques au connecteur

Configuration spécifique au connecteur syncevents
-------------------------------------------------

Le connecteur syncevents dispose de quelques options de configuration
spécifiques, détaillées ci-dessous.

Seuils pour l'envoi des demandes d'état
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
L'option ``minutes_old`` détermine l'âge minimum (en minutes) d'une alerte
ou d'un état portant sur un hôte ou un service de bas niveau
au-dessus duquel on demande une mise à jour à Nagios.

Nagios est configuré pour ré-émettre des notifications toutes les 30 minutes
pour les hôtes et les services de bas niveau. Il faut donc régler ici
une valeur légèrement supérieure, pour ne cibler que les états désynchronisés.

Une valeur négative désactive cette resynchronisation.
La valeur par défaut est 45 minutes.

.. warning::
    Cette valeur doit être cohérente avec la fréquence des réémissions
    de notifications configurées dans Nagios pour les alertes sur les hôtes
    et les services de bas niveau.

L'option ``hls_minutes_old`` détermine l'âge minimum d'un état (en minutes)
portant sur un service de haut niveau au-dessus duquel on demande
une mise à jour à Nagios. Elle sert également à initialiser les services
de haut niveau plus rapidement, en contrepartie d'une dégradation
des performances générales de Vigilo.

Nagios est configuré pour ré-émettre des notifications toutes les 30 minutes
pour les services de haut niveau. Il faut donc régler ici une valeur
légèrement supérieure, pour ne cibler que les états désynchronisés.

Une valeur négative désactive cette resynchronisation.
La valeur par défaut est -1 (ie. la resynchronisation est désactivée).

.. warning::
    Si la resynchronisation des services de haut niveau est souhaitée,
    cette valeur doit être cohérente avec la fréquence des réémissions
    de notifications configurées dans Nagios pour les alertes sur les
    services de haut niveau.

Emplacement du fichier de verrou
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Un fichier de verrou est créé par le connector-syncevents afin d'empêcher
l'exécution simultanée de plusieurs instances du connecteur.

L'option ``lockfile`` peut être utilisée pour spécifier l'emplacement du
fichier de verrou à créer. L'emplacement par défaut de ce fichier de verrou
est ``/var/lock/vigilo-connector-syncevents/lock``.

Limite sur le nombre de demandes d'état
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
L'option ``max_events`` permet de limiter le nombre de demandes de réémission
d'état qui peuvent être envoyées à Nagios au cours d'une exécution du
connecteur syncevents.

Cette option est particulièrement utile afin d'empêcher une inondation du bus
de communication de Vigilo sur un parc de grande taille lorsqu'un incident
majeur survient sur la plate-forme de supervision (par exemple : collecteur
qui ne répond plus).

Si cette option n'est pas renseignée, aucune limite n'est imposée sur le nombre
de demandes de réémission d'état qui peuvent être envoyées à Nagios au cours
de la même exécution.


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
Le connecteur syncevents envoie des messages contenant des commandes qui seront
récupérées par le connector-nagios, puis transmises à Nagios après avoir été
converties en utilisant la syntaxe adéquate.

Ce messages sont des demandes de ré-émission de notification, définis dans la
documentation Nagios aux URL suivantes :

* `SEND_CUSTOM_HOST_NOTIFICATION`_
* `SEND_CUSTOM_SVC_NOTIFICATION`_

.. _SEND_CUSTOM_HOST_NOTIFICATION: http://old.nagios.org/developerinfo/externalcommands/commandinfo.php?command_id=134
.. _SEND_CUSTOM_SVC_NOTIFICATION: http://old.nagios.org/developerinfo/externalcommands/commandinfo.php?command_id=135

Pour circuler sur le bus, ces demandes sont encodées dans un message
Vigilo de type « command », dont un exemple suit :

.. sourcecode:: javascript

    { "type": "nagios",
      "cmdname": "SEND_CUSTOM_SVC_NOTIFICATION",
      "value": "server.example.com;Load 01;0;vigilo;syncevents",
    }

Après réception par Nagios, ce dernier va ré-expédier une notification de
l'état de l'hôte ou du service concerné, qui suivra le chemin classique des
notifications dans Vigilo : elle sera réceptionnée par le corrélateur, qui
mettra à jour l'état dans la base Vigilo.



Annexes
=======

.. include:: ../../connector/doc/glossaire.rst


.. vim: set tw=79 :
