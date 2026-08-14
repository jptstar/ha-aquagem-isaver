# Aquagem iSaver Power pour Home Assistant

Intégration locale HACS pour piloter un **Aquagem iSaver Power 1100** à travers une passerelle RS485 vers TCP en mode transparent.

## Entités

- interrupteur de marche/arrêt de la pompe ;
- consigne de vitesse de 1200 à 2900 tr/min ;
- vitesse remontée par le variateur ;
- état de connexion.

## Installation manuelle

Copier `custom_components/aquagem_isaver` dans le dossier `custom_components` de Home Assistant, redémarrer Home Assistant, puis ajouter **Aquagem iSaver Power** depuis **Paramètres > Appareils et services**.

## Installation avec HACS

Publier ce dossier comme dépôt GitHub public, l'ajouter dans HACS comme dépôt personnalisé de type **Integration**, installer l'intégration et redémarrer Home Assistant.

## Configuration

Saisir l'adresse IP locale de la passerelle. Le port `502` est proposé par défaut et reste modifiable. L'intervalle de lecture est réglable entre 5 et 300 secondes.

La passerelle doit être configurée en **TCP / RTU-BUFFERED**, avec un délai de 5000 ms. Aucun Unit-ID n'est demandé par l'intégration : l'identifiant `0xAA` est déjà présent au début des trames propriétaires.

## Protocole et arrêt

Cette version reprend les trames observées dans le flow Node-RED :

- lecture : `AA C3 07 D1 00 02 + CRC16` ;
- écriture : `AA D0 0B B9 [valeur 16 bits] + CRC16` ;
- arrêt : valeur **0** ;
- marche : dernière consigne valide, 1200 tr/min au premier démarrage.

Le CRC est recalculé pour chaque commande. Pour la valeur `1`, le CRC Modbus correct est envoyé en ordre RTU `CB C2`; la trame manuelle `C2 CB` visible dans le flow est inversée.

La valeur `1` n'est volontairement pas utilisée pour arrêter la pompe : le flow de référence la nomme « bit vitesse fixe », tandis que sa trame d'arrêt explicite utilise `0`.

> Important : le classeur constructeur n'était pas accessible lors de la génération. Tester d'abord sur une installation surveillée. Si le variateur répond avec une trame différente, activer les journaux Home Assistant et ouvrir un ticket avec la trame reçue.

Une passerelle silencieuse n'empêche pas l'ajout de l'intégration. Les entités sont créées comme indisponibles et la lecture est retentée automatiquement selon l'intervalle configuré.

Depuis la version 0.1.2, les réponses TCP fragmentées sont réassemblées avant décodage et l'unité `rpm` est compatible avec Home Assistant 2026.

Depuis la version 0.1.3, aucune relecture immédiate n'est lancée après une commande : la passerelle dispose du temps nécessaire pour libérer sa connexion avant le prochain cycle normal.
