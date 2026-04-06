# Projet VoIP - Application de Communication par Internet

## Équipe de Développement

| Membre | Rôle |
|--------|------|
| AHOULIMI BIDENIMM | Architecture SIP & Réseau |
| SIDIKI ABOUBAKAR | Développement Client & Interface |
| EL KARFI SOUFIA | Serveur Proxy & Routage |
| LAZAAR EL MEHDI | Streaming Audio & Codecs |

## Description du Projet

Ce projet implémente une application complète de Voice over IP (VoIP) utilisant les protocoles **SIP** (Session Initiation Protocol) pour l'établissement des appels et **RTP** (Real-time Transport Protocol) pour le transport des flux audio.

## Architecture Technique

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Client A   │◄───────►│  Serveur    │◄───────►│  Client B   │
│  (SIP UA)   │  SIP    │  SIP/Proxy  │  SIP    │  (SIP UA)   │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       └────────────── RTP direct (LAN) ──────────────┘
                               ou
                 RTP relayé via serveur (Internet)
```

### Composants

1. **Client SIP** (`src/client/`) - Application utilisateur avec interface
2. **Serveur SIP/Proxy** (`src/server/`) - Routage et gestion des sessions
3. **Module Audio** (`src/shared/`) - Encodage/décodage audio (G.711, Opus)
4. **Module RTP** (`src/shared/`) - Transport des paquets audio

## Prérequis

- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)
- Microphone et haut-parleurs

## Installation

### 1. Cloner ou télécharger le projet

```bash
cd projet-chaoub
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Configuration

Modifier les fichiers de configuration dans `config/`:
- `server_config.json` - Configuration du serveur SIP
- `client_config.json` - Configuration du client

### Option NAT/Internet (STUN + Relais RTP serveur)

Le client supporte STUN pour annoncer l'IP/port public RTP dans le SDP.
Le serveur supporte aussi un mode \"relais média\" (RTP relay) pour les appels Internet difficiles.

#### Configuration client (STUN)

Dans `client_config.json` (ou `client2_config.json`), activer:

```json
"network": {
       "stun_enabled": true,
       "stun_server": "stun.l.google.com",
       "stun_port": 19302,
       "stun_timeout": 1.5
}
```

#### Configuration serveur (relai RTP)

Dans `server_config.json`:

```json
"server": {
       "host": "0.0.0.0",
       "sip_port": 5060,
       "rtp_port_start": 10000,
       "rtp_port_end": 20000,
       "media_relay_enabled": true,
       "public_host": "IP_PUBLIQUE_OU_DNS_DU_SERVEUR"
}
```

> Note: STUN + relais RTP améliore fortement les appels Internet, mais ICE/TURN reste la solution la plus robuste multi-opérateurs.

## Démarrage

### Lancer le serveur SIP

```bash
python src/server/sip_server.py
```

### Lancer le client SIP

```bash
python src/client/gui.py
```

## Déploiement Internet (2 PC Windows)

### PC1 (serveur Windows)

1. Configurer `config/server_config.json` avec:
       - `public_host` = IP publique ou DNS du PC1
       - `media_relay_enabled` = `true`
2. Ouvrir le firewall Windows:

```powershell
New-NetFirewallRule -DisplayName "VoIP SIP UDP 5060" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 5060 -Profile Any
New-NetFirewallRule -DisplayName "VoIP RTP UDP 10000-20000" -Direction Inbound -Action Allow -Protocol UDP -LocalPort 10000-20000 -Profile Any
```

3. Configurer la box/routeur (port forwarding):
       - UDP `5060` vers IP locale de PC1
       - UDP `10000-20000` vers IP locale de PC1

4. Lancer le serveur:

```powershell
Set-Location "C:\chemin\projet-chaoub"
.venv\Scripts\python.exe src\server\sip_server.py
```

### PC2 (client Windows distant)

1. Dans `config/client_config.json` (et/ou `client2_config.json`):
       - `server_host` = IP publique ou DNS de PC1
       - `server_port` = `5060`
2. Lancer un test de connectivité:

```powershell
Set-Location "C:\chemin\projet-chaoub"
.venv\Scripts\python.exe tests\test_connectivity.py --host IP_PUBLIQUE_OU_DNS_DU_SERVEUR --port 5060
```

3. Lancer le client:

```powershell
.venv\Scripts\python.exe src\client\gui.py
```

## Utilisation

1. **Enregistrement** : Chaque client s'enregistre auprès du serveur avec un identifiant unique
2. **Appel** : Composer le numéro ou sélectionner un contact
3. **Communication** : Parler via le microphone, écouter via les haut-parleurs
4. **Fin d'appel** : Cliquer sur le bouton "Raccrocher"

## Fonctionnalités

- [x] Établissement d'appels via SIP
- [x] Transport audio via RTP
- [x] Codecs G.711 (PCM) et Opus
- [x] Interface utilisateur graphique
- [x] Gestion des contacts
- [x] Historique des appels
- [x] Mise en attente (Hold)
- [x] Transfert d'appel

## Structure du Projet

```
projet-chaoub/
├── src/
│   ├── client/          # Application client SIP
│   │   ├── sip_client.py
│   │   ├── gui.py
│   │   └── audio_handler.py
│   ├── server/          # Serveur SIP/Proxy
│   │   └── sip_server.py
│   └── shared/          # Modules partagés
│       ├── rtp.py
│       ├── codecs.py
│       └── sip_messages.py
├── tests/               # Scripts de test
├── config/              # Fichiers de configuration
├── docs/                # Documentation
└── README.md
```

## Protocoles Utilisés

### SIP (RFC 3261)
- REGISTER : Enregistrement des utilisateurs
- INVITE : Initiation d'appel
- ACK : Accusé de réception
- BYE : Terminaison d'appel
- CANCEL : Annulation d'appel

### RTP (RFC 3550)
- Transport des flux audio en temps réel
- Séquençage des paquets
- Détection de perte de paquets

## Tests

Exécuter la suite de tests :

```bash
python -m pytest tests/
```

Ou lancer les tests manuels :

```bash
python tests/test_connectivity.py
```

## Documentation Complète

Voir le dossier `docs/` pour :
- Le rapport de synthèse
- Les diagrammes d'architecture
- La spécification des messages SIP
- Les résultats de tests

## Licence

Projet académique - Équipe de 4 étudiants

## Contact

Pour toute question, contacter l'équipe via le dépôt du projet.
