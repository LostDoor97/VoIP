# Rapport de Synthèse - Projet VoIP

## Logiciel de Communication Voice over IP (VoIP)

---

### Équipe de Développement

| Membre | Rôle Principal | Contributions |
|--------|----------------|---------------|
| **AHOULIMI BIDENIMM** | Architecture SIP & Réseau | Conception du protocole SIP, gestion des messages REGISTER/INVITE/BYE |
| **SIDIKI ABOUBAKAR** | Développement Client & Interface | Application client, interface graphique Tkinter, gestion des appels |
| **EL KARFI SOUFIA** | Serveur Proxy & Routage | Serveur SIP/Proxy, registrar, routage des messages |
| **LAZAAR EL MEHDI** | Streaming Audio & Codecs | Implémentation RTP, codecs G.711, gestion audio |

---

## Table des Matières

1. [Introduction](#1-introduction)
2. [Protocoles Utilisés](#2-protocoles-utilisés)
3. [Architecture Technique](#3-architecture-technique)
4. [Implémentation](#4-implémentation)
5. [Tests et Résultats](#5-tests-et-résultats)
6. [Conclusion](#6-conclusion)

---

## 1. Introduction

### 1.1 Contexte du Projet

La Voix sur IP (VoIP) est une technologie permettant de transmettre la voix et les communications multimédias sur des réseaux utilisant le protocole IP. Ce projet vise à implémenter une application complète de communication VoIP démontrant la maîtrise des protocoles réseau et du traitement audio en temps réel.

### 1.2 Objectifs

- **Objectif principal** : Développer une application fonctionnelle de communication audio sur IP
- **Objectifs secondaires** :
  - Implémenter le protocole SIP (RFC 3261)
  - Gérer le transport audio via RTP (RFC 3550)
  - Supporter les codecs G.711 μ-law et A-law
  - Fournir une interface utilisateur intuitive

### 1.3 Périmètre Fonctionnel

| Fonctionnalité | Statut |
|----------------|--------|
| Établissement d'appels SIP | ✓ Implémenté |
| Transport audio RTP | ✓ Implémenté |
| Codec G.711 PCMU | ✓ Implémenté |
| Codec G.711 PCMA | ✓ Implémenté |
| Interface graphique | ✓ Implémentée |
| Gestion des contacts | ✓ Implémentée |
| Historique des appels | ✓ Implémenté |
| Enregistrement auprès du serveur | ✓ Implémenté |

---

## 2. Protocoles Utilisés

### 2.1 SIP - Session Initiation Protocol

Le **SIP** (RFC 3261) est un protocole de signalisation utilisé pour établir, modifier et terminer des sessions multimédias.

#### 2.1.1 Messages SIP Implémentés

| Message | Direction | Description |
|---------|-----------|-------------|
| **REGISTER** | Client → Serveur | Enregistrement de l'utilisateur auprès du serveur |
| **INVITE** | Client → Serveur | Demande d'initiation d'appel |
| **ACK** | Client → Serveur | Accusé de réception d'une réponse positive |
| **BYE** | Client ↔ Serveur | Demande de terminaison d'appel |
| **CANCEL** | Client → Serveur | Annulation d'une requête en cours |
| **OPTIONS** | Client ↔ Serveur | Requête de capacités (keepalive) |

#### 2.1.2 Cycle de Vie d'un Appel SIP

```
Client A                    Serveur                    Client B
   |                          |                           |
   |------- REGISTER -------->|                           |
   |<------ 200 OK -----------|                           |
   |                          |                           |
   |------- INVITE ---------->|                           |
   |<------ 100 Trying -------|                           |
   |                          |------- INVITE ----------->|
   |                          |<------ 180 Ringing -------|
   |<------ 180 Ringing ------|                           |
   |                          |                           |
   |                          |<------ 200 OK -----------|
   |<------ 200 OK -----------|                           |
   |------- ACK ------------->|                           |
   |                          |------- ACK -------------->|
   |                          |                           |
   |<======== RTP STREAM ===============================>|
   |                          |                           |
   |------- BYE ------------->|                           |
   |<------ 200 OK -----------|                           |
   |                          |------- BYE -------------->|
   |                          |<------ 200 OK -----------|
   |                          |                           |
```

#### 2.1.3 Structure d'un Message SIP

```
INVITE sip:1002@localhost SIP/2.0
Via: SIP/2.0/UDP 192.168.1.100;branch=z9hG4bK-abc123
From: <sip:1001@example.com>;tag=abc123
To: <sip:1002@example.com>
Call-ID: call123@192.168.1.100
CSeq: 1 INVITE
Contact: <sip:1001@192.168.1.100:5061>
Content-Type: application/sdp
Content-Length: 150

v=0
o=- 1234 1234 IN IP4 192.168.1.100
s=-
c=IN IP4 192.168.1.100
t=0 0
m=audio 8000 RTP/AVP 0 8
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
```

### 2.2 RTP - Real-time Transport Protocol

Le **RTP** (RFC 3550) assure le transport des données multimédias en temps réel.

#### 2.2.1 Structure d'un Paquet RTP

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|V=2|P|X|  CC   |M|     PT      |       sequence number         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                           timestamp                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|           synchronization source (SSRC) identifier            |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         payload data                          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

| Champ | Taille | Description |
|-------|--------|-------------|
| Version (V) | 2 bits | Version du protocole (toujours 2) |
| Padding (P) | 1 bit | Indique un bourrage |
| Extension (X) | 1 bit | Indique un header d'extension |
| CC | 4 bits | Nombre d'identifiants CSRC |
| M | 1 bit | Marqueur (début de talkspurt) |
| PT | 7 bits | Type de payload (0=PCMU, 8=PCMA) |
| Sequence Number | 16 bits | Numéro de séquence incrémental |
| Timestamp | 32 bits | Horodatage pour la synchronisation |
| SSRC | 32 bits | Identifiant de source synchronisée |

#### 2.2.2 Flux RTP pour la Voix

- **Fréquence d'échantillonnage** : 8000 Hz
- **Taille de frame** : 160 échantillons (20 ms)
- **Débit** : 50 paquets/seconde
- **Payload G.711** : 160 bytes par paquet (8 bits/échantillon)

### 2.3 SDP - Session Description Protocol

Le **SDP** (RFC 4566) décrit les paramètres de la session multimédia.

```
v=0                              # Version du protocole
o=- 12345 12345 IN IP4 192.168.1.100  # Origine (username, session id, version, IP)
s=-                              # Nom de la session
c=IN IP4 192.168.1.100           # Connection info (network type, address type, IP)
t=0 0                            # Timing (start, stop - 0 = permanent)
m=audio 8000 RTP/AVP 0 8         # Media (type, port, protocol, formats)
a=rtpmap:0 PCMU/8000             # Attribute (payload type mapping)
a=rtpmap:8 PCMA/8000
a=sendrecv                       # Mode d'émission/réception
```

---

## 3. Architecture Technique

### 3.1 Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERNET                                │
│                                                                 │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐│
│  │  Client A   │◄───────►│   Serveur   │◄───────►│  Client B   ││
│  │  (SIP UA)   │   SIP   │  SIP/Proxy  │   SIP   │  (SIP UA)   ││
│  │ 192.168.1.10│         │  0.0.0.0    │         │192.168.1.20 ││
│  └──────┬──────┘         │  Port 5060  │         └──────┬──────┘│
│         │                └─────────────┘                │       │
│         │                                               │       │
│         └─────────────────── RTP ───────────────────────┘       │
│                    Port 10000-20000                             │
│                    (Flux Audio Direct)                          │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Architecture Logicielle

```
┌────────────────────────────────────────────────────────────┐
│                      APPLICATION CLIENT                     │
├────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Interface   │  │   Client     │  │   Audio      │     │
│  │  Graphique   │◄─┤    SIP       │◄─┤   Handler    │     │
│  │   (Tkinter)  │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │            │
│         │                  │                  │            │
│  ┌──────▼──────────────────▼──────────────────▼───────┐   │
│  │              Module de Communication                │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│                      SERVEUR SIP                           │
├────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Registrar   │  │    Proxy     │  │  Gestion     │     │
│  │              │  │              │  │   d'Appels   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                          │                                 │
│  ┌───────────────────────▼───────────────────────────────┐│
│  │              Socket UDP (Port 5060)                    ││
│  └───────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────┘
```

### 3.3 Diagramme de Classes

```
                    ┌─────────────────────┐
                    │     SIPMessage      │
                    ├─────────────────────┤
                    │ - method: str       │
                    │ - uri: str          │
                    │ - headers: Dict     │
                    │ - body: str         │
                    ├─────────────────────┤
                    │ + to_bytes()        │
                    │ + from_bytes()      │
                    └─────────────────────┘
                              ▲
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
┌───────────────────────┐           ┌───────────────────────┐
│  SIPRequestBuilder    │           │  SIPResponseBuilder   │
├───────────────────────┤           ├───────────────────────┤
│ - method: str         │           │ - request: SIPMessage │
│ - uri: str            │           │ - status_code: int    │
│ - from_tag: str       │           ├───────────────────────┤
│ - call_id: str        │           │ + build()             │
│ - cseq: int           │           └───────────────────────┘
│ - via_branch: str     │
├───────────────────────┤
│ + set_contact()       │
│ + set_sdp_body()      │
│ + build()             │
└───────────────────────┘

┌───────────────────────┐           ┌───────────────────────┐
│      RTPPacket        │           │     RTPSession        │
├───────────────────────┤           ├───────────────────────┤
│ - version: int        │           │ - local_port: int     │
│ - payload_type: int   │           │ - remote_addr: tuple  │
│ - sequence_number: int│           │ - ssrc: int           │
│ - timestamp: int      │           ├───────────────────────┤
│ - ssrc: int           │           │ + start()             │
│ - payload: bytes      │           │ + stop()              │
├───────────────────────┤           │ + send_audio_frame()  │
│ + to_bytes()          │           │ + get_stats()         │
│ + from_bytes()        │           └───────────────────────┘
└───────────────────────┘
```

### 3.4 Flux de Données Audio

```
┌──────────────────────────────────────────────────────────────────┐
│  CAPTURE AUDIO                    ENVOI RTP                      │
│                                                                   │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────────┐  │
│  │Microphone│───►│  PCM    │───►│  G.711  │───►│  En-tête   │  │
│  │         │    │  16-bit │    │ Encode  │    │    RTP      │  │
│  └─────────┘    └─────────┘    └─────────┘    └─────────────┘  │
│                                        │              │          │
│                                        │              ▼          │
│                                        │       ┌─────────────┐  │
│                                        │       │   Socket    │  │
│                                        │       │    UDP      │  │
│                                        │       └─────────────┘  │
│                                        │              │          │
└────────────────────────────────────────┼──────────────┼──────────┘
                                         │              │
                                         ▼              ▼
                                    INTERNET      RÉSEAU IP
                                         │              │
                                         │              │
┌────────────────────────────────────────┼──────────────┼──────────┐
│                                        │              │          │
│  RÉCEPTION RTP                 LECTURE AUDIO          │          │
│                                        │              │          │
│  ┌─────────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │
│  │   Socket    │───►│  G.711  │───►│   PCM   │───►│Hauts-   │  │
│  │    UDP      │    │ Decode  │    │ 16-bit  │    │parleurs │  │
│  └─────────────┘    └─────────┘    └─────────┘    └─────────┘  │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Implémentation

### 4.1 Structure du Projet

```
projet-chaoub/
├── src/
│   ├── client/
│   │   ├── __init__.py
│   │   ├── sip_client.py      # Client SIP principal
│   │   ├── audio_handler.py   # Gestion audio et codecs
│   │   └── gui.py             # Interface graphique
│   ├── server/
│   │   ├── __init__.py
│   │   └── sip_server.py      # Serveur SIP/Proxy
│   └── shared/
│       ├── __init__.py
│       ├── sip_messages.py    # Messages SIP et SDP
│       ├── rtp.py             # Protocole RTP
│       └── codecs.py          # Codecs G.711
├── tests/
│   ├── test_connectivity.py   # Tests de connectivité
│   └── test_audio.py          # Tests audio/codecs
├── config/
│   ├── server_config.json     # Configuration serveur
│   └── client_config.json     # Configuration client
├── scripts/
│   ├── install.bat            # Installation dépendances
│   ├── start_server.bat       # Lancement serveur
│   ├── start_client.bat       # Lancement client
│   └── run_tests.bat          # Exécution des tests
├── docs/
│   └── rapport.md             # Ce document
├── requirements.txt           # Dépendances Python
└── README.md                  # Documentation principale
```

### 4.2 Technologies Utilisées

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Langage | Python | 3.8+ |
| Interface | Tkinter | Inclus |
| Audio | sounddevice | 0.4.4+ |
| Traitement | NumPy | 1.21.0+ |
| Réseau | Socket (stdlib) | - |

### 4.3 Configuration Requise

- **Système d'exploitation** : Windows 10/11, Linux, macOS
- **Python** : Version 3.8 ou supérieure
- **Mémoire RAM** : 512 Mo minimum
- **Audio** : Microphone et haut-parleurs (ou casque)

### 4.4 Instructions d'Installation

```bash
# 1. Cloner ou télécharger le projet
cd projet-chaoub

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer le serveur (optionnel)
# Modifier config/server_config.json

# 4. Configurer le client (optionnel)
# Modifier config/client_config.json
```

### 4.5 Instructions d'Utilisation

#### Démarrer le Serveur

```bash
# Windows
scripts\start_server.bat

# Linux/Mac
python src/server/sip_server.py
```

#### Démarrer le Client

```bash
# Windows
scripts\start_client.bat

# Linux/Mac
python src/client/gui.py
```

#### Exécuter les Tests

```bash
# Windows
scripts\run_tests.bat

# Linux/Mac
python tests/test_connectivity.py
python tests/test_audio.py
```

---

## 5. Tests et Résultats

### 5.1 Tests Unitaires

#### Test Codec G.711

| Test | Résultat | Détails |
|------|----------|---------|
| Encodage PCMU | ✓ Pass | Compression 2:1 |
| Décodage PCMU | ✓ Pass | Reconstruction fidèle |
| Encodage PCMA | ✓ Pass | Compression 2:1 |
| Décodage PCMA | ✓ Pass | Reconstruction fidèle |
| Négociation | ✓ Pass | Priorité respectée |

#### Test Paquets RTP

| Test | Résultat | Détails |
|------|----------|---------|
| Création paquet | ✓ Pass | Header 12 bytes |
| Sérialisation | ✓ Pass | Format RFC 3550 |
| Numérotation | ✓ Pass | Séquence incrémentale |
| Timestamps | ✓ Pass | 160 samples/frame |

#### Test Messages SIP

| Test | Résultat | Détails |
|------|----------|---------|
| Création SDP | ✓ Pass | Champs obligatoires |
| Parsing SDP | ✓ Pass | Extraction IP/Port/Codecs |
| REGISTER | ✓ Pass | Enregistrement utilisateur |
| INVITE | ✓ Pass | Initiation d'appel |
| BYE | ✓ Pass | Terminaison d'appel |

### 5.2 Scénarios de Test

#### Scénario 1 : Appel entre deux clients

```
Étape 1: Client 1001 s'enregistre auprès du serveur
         → REGISTER envoyé
         → 200 OK reçu

Étape 2: Client 1002 s'enregistre auprès du serveur
         → REGISTER envoyé
         → 200 OK reçu

Étape 3: Client 1001 appelle 1002
         → INVITE envoyé
         → 100 Trying reçu
         → 180 Ringing reçu
         → 200 OK reçu
         → ACK envoyé

Étape 4: Communication audio établie
         → Flux RTP bidirectionnel
         → Encodage G.711 PCMU

Étape 5: Fin de l'appel
         → BYE envoyé
         → 200 OK reçu
         → Ressources libérées
```

#### Scénario 2 : Appel vers utilisateur indisponible

```
Étape 1: Client 1001 appelle 1099 (inexistant)
         → INVITE envoyé
         → 404 Not Found reçu
         → Notification utilisateur

Étape 2: Client 1001 appelle 1002 (non enregistré)
         → INVITE envoyé
         → 480 Temporarily Unavailable reçu
         → Notification utilisateur
```

### 5.3 Résultats des Tests

```
============================================================
  TESTS DE CONNECTIVITÉ VoIP
============================================================

Tests unitaires (sans serveur):
----------------------------------------
✓ PASS - Codec G.711 (PCMU/PCMA)
  Encodage/Décodage G.711 fonctionnel

✓ PASS - Paquets RTP
  Création et parsing RTP fonctionnels

✓ PASS - SDP (Session Description Protocol)
  Création et parsing SDP fonctionnels

✓ PASS - Ports RTP disponibles
  Port 10000 disponible pour RTP

Tests d'intégration (avec serveur):
----------------------------------------
✓ PASS - Serveur SIP accessible
  Serveur répond sur localhost:5060

✓ PASS - Enregistrement SIP (REGISTER)
  Utilisateur 1001 enregistré avec succès

✓ PASS - Initiation d'appel (INVITE)
  Réponse valide reçue: 100 Trying

============================================================
  RÉSUMÉ DES TESTS
============================================================

  Tests réussis: 7/7
  Taux de succès: 100.0%

  ✓ Tous les tests sont passés avec succès!
```

---

## 6. Conclusion

### 6.1 Bilan du Projet

Ce projet a permis de concevoir et implémenter une application complète de communication VoIP fonctionnelle. Les objectifs principaux ont été atteints :

1. **✓ Application fonctionnelle** : Le client et le serveur permettent d'établir des appels audio
2. **✓ Protocole SIP** : Implémentation conforme à la RFC 3261
3. **✓ Transport RTP** : Flux audio en temps réel avec gestion des paquets
4. **✓ Codecs audio** : Support de G.711 μ-law et A-law
5. **✓ Interface utilisateur** : Application graphique intuitive

### 6.2 Difficultés Rencontrées

| Difficulté | Solution Apportée |
|------------|-------------------|
| Synchronisation audio | Buffering et jitter buffer simulé |
| Gestion des timeouts | Threads dédiés avec timeout configurable |
| Négociation de codecs | Algorithme de priorité configurable |
| NAT/Firewall | Documentation des limitations |

### 6.3 Améliorations Possibles

- **Court terme** :
  - Support du codec Opus pour une meilleure qualité
  - Gestion du DTMF via RFC 2833
  - Interface web avec WebRTC

- **Moyen terme** :
  - Chiffrement SRTP pour la confidentialité
  - Support TLS pour la signalisation
  - Conference calls (appels à plusieurs)

- **Long terme** :
  - Passerelle vers le RTC (PSTN)
  - Support vidéo
  - Messagerie vocale

### 6.4 Compétences Développées

- **Protocoles réseau** : Maîtrise de SIP, RTP, SDP
- **Programmation réseau** : Sockets UDP, multithreading
- **Traitement audio** : Codecs, échantillonnage, quantification
- **Développement GUI** : Tkinter, événements, callbacks
- **Tests** : Tests unitaires, tests d'intégration

---

## Annexes

### A. Références

1. RFC 3261 - SIP: Session Initiation Protocol
2. RFC 3550 - RTP: A Transport Protocol for Real-Time Applications
3. RFC 3551 - RTP Audio/Video Profiles
4. RFC 4566 - SDP: Session Description Protocol
5. ITU-T G.711 - Pulse code modulation (PCM) of voice frequencies

### B. Glossaire

| Terme | Définition |
|-------|------------|
| SIP | Session Initiation Protocol - Protocole de signalisation |
| RTP | Real-time Transport Protocol - Transport de flux multimédia |
| SDP | Session Description Protocol - Description de session |
| Codec | Codeur-Décodeur - Algorithme de compression audio |
| PCMU | G.711 μ-law - Codec audio standard nord-américain |
| PCMA | G.711 A-law - Codec audio standard européen |
| UA | User Agent - Client SIP |
| SSRC | Synchronization Source - Identifiant de source RTP |

---

*Document rédigé par l'équipe de développement*
*Projet académique - 2024*
