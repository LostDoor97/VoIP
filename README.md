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
└──────┬──────┘         └─────────────┘         └──────┬──────┘
       │                                               │
       └─────────────────── RTP ───────────────────────┘
                      (Flux Audio)
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

### Option NAT/Internet (STUN)

Le client supporte maintenant STUN pour annoncer l'IP/port public RTP dans le SDP.

Dans `client_config.json` (ou `client2_config.json`), activer:

```json
"network": {
       "stun_enabled": true,
       "stun_server": "stun.l.google.com",
       "stun_port": 19302,
       "stun_timeout": 1.5
}
```

> Note: STUN aide pour certains NAT, mais les NAT symétriques nécessitent souvent TURN/ICE complet.

## Démarrage

### Lancer le serveur SIP

```bash
python src/server/sip_server.py
```

### Lancer le client SIP

```bash
python src/client/gui.py
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
