**********************
Guide d'administration
**********************


Installation
============

Pré-requis logiciels
--------------------
Afin de pouvoir faire fonctionner le connecteur de métrologie, l'installation
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

Seuil pour l'envoi de demandes d'état
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
L'option ``minutes_old`` détermine l'âge minimum d'une alerte (en minutes),
au-dessous duquel on ne demande pas de mise à jour à Nagios. Vigilo configure
Nagios pour que des notifications soient réémises toutes les 30 minutes,
il faut donc régler ici une valeur légèrement supérieure, pour ne cibler
que les états désynchronisés.

La valeur par défaut est 35 minutes.

.. warning::
    Si cette valeur ou la fréquence des réémissions de notifications dans Nagios
    doivent être modifiées, il faut faire attention à toujours garder les deux
    en cohérence.

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
