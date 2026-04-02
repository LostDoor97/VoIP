# Documentation des Protocoles VoIP

## 1. Introduction

Ce document détaille les protocoles utilisés dans notre implémentation VoIP.

---

## 2. Protocole SIP (Session Initiation Protocol)

### 2.1 Présentation

SIP est un protocole de signalisation de couche application (RFC 3261) utilisé pour:
- Établir des sessions multimédias
- Modifier les paramètres d'une session
- Terminer une session

### 2.2 Composants SIP

```
┌─────────────────────────────────────────────────────────┐
│                    ÉLÉMENTS SIP                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  User Agent (UA)                                         │
│  ───────────────                                         │
│  Entité logique qui initie ou reçoit des appels          │
│  - UA Client (UAC): Initie les requêtes                  │
│  - UA Serveur (UAS): Reçoit et répond aux requêtes       │
│                                                          │
│  Proxy Server                                            │
│  ────────────                                            │
│  Intermédiaire qui route les requêtes SIP                │
│  - Stateful: Garde l'état des transactions               │
│  - Stateless: Ne garde pas l'état                        │
│                                                          │
│  Registrar                                               │
│  ───────────                                             │
│  Reçoit les REGISTER et stocke les localisations         │
│                                                          │
│  Location Service                                        │
│  ───────────────                                         │
│  Base de données des utilisateurs enregistrés            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 2.3 Méthodes SIP

| Méthode | Description | Exemple d'utilisation |
|---------|-------------|----------------------|
| REGISTER | Enregistrement de la position | Client s'enregistre auprès du serveur |
| INVITE | Initiation de session | Démarrage d'un appel |
| ACK | Accusé de réception | Confirmation de réception de réponse finale |
| BYE | Terminaison de session | Fin d'un appel |
| CANCEL | Annulation de requête | Annuler un appel en cours d'établissement |
| OPTIONS | Requête de capacités | Vérifier les capacités d'un serveur |

### 2.4 Codes de Réponse SIP

#### 1xx - Information

| Code | Signification | Description |
|------|---------------|-------------|
| 100 | Trying | La requête est en cours de traitement |
| 180 | Ringing | L'utilisateur distant est en train de sonner |
| 181 | Call Forwarded | L'appel est redirigé |
| 183 | Session Progress | Informations sur la progression de session |

#### 2xx - Succès

| Code | Signification | Description |
|------|---------------|-------------|
| 200 | OK | La requête a réussi |

#### 3xx - Redirection

| Code | Signification | Description |
|------|---------------|-------------|
| 301 | Moved Permanently | L'utilisateur a une nouvelle adresse |
| 302 | Moved Temporarily | L'utilisateur est temporairement ailleurs |

#### 4xx - Erreur Client

| Code | Signification | Description |
|------|---------------|-------------|
| 400 | Bad Request | La requête est mal formée |
| 401 | Unauthorized | Authentification requise |
| 403 | Forbidden | La requête est refusée |
| 404 | Not Found | L'utilisateur n'existe pas |
| 407 | Proxy Auth Required | Authentification proxy requise |
| 408 | Request Timeout | Délai d'attente dépassé |
| 480 | Temporarily Unavailable | L'utilisateur est indisponible |
| 486 | Busy Here | L'utilisateur est occupé |

#### 5xx - Erreur Serveur

| Code | Signification | Description |
|------|---------------|-------------|
| 500 | Internal Server Error | Erreur interne du serveur |
| 503 | Service Unavailable | Service indisponible |

#### 6xx - Échec Global

| Code | Signification | Description |
|------|---------------|-------------|
| 603 | Decline | L'utilisateur refuse l'appel |

### 2.5 En-têtes SIP Principaux

| Header | Format | Description |
|--------|--------|-------------|
| Via | `SIP/2.0/UDP host;branch=id` | Chemin parcouru par la requête |
| From | `<sip:user@host>;tag=id` | Expéditeur de la requête |
| To | `<sip:user@host>;tag=id` | Destinataire de la requête |
| Call-ID | `unique-id@host` | Identifiant unique de l'appel |
| CSeq | `number METHOD` | Numéro de séquence |
| Contact | `<sip:user@host:port>` | URI de contact direct |
| Max-Forwards | `integer` | Nombre maximum de sauts (défaut: 70) |
| Content-Type | `type/subtype` | Type de contenu du corps |
| Content-Length | `integer` | Taille du corps en bytes |

---

## 3. Protocole RTP (Real-time Transport Protocol)

### 3.1 Présentation

RTP (RFC 3550) est un protocole de transport pour les données en temps réel:
- Audio (voix, musique)
- Vidéo
- Données de simulation

### 3.2 Caractéristiques

- **Transport**: UDP (généralement)
- **Ports**: Pairs pour RTP, impairs pour RTCP
- **Séquençage**: Numéros de séquence pour détecter les pertes
- **Timestamps**: Horodatages pour la synchronisation
- **Identification de source**: SSRC pour identifier la source

### 3.3 Types de Payload Audio

| Payload Type | Codec | Fréquence | Description |
|--------------|-------|-----------|-------------|
| 0 | PCMU | 8000 Hz | G.711 μ-law |
| 8 | PCMA | 8000 Hz | G.711 A-law |
| 9 | G722 | 8000 Hz | G.722 (wideband) |
| 18 | G729 | 8000 Hz | G.729 |
| 101-127 | Dynamic | - | Types dynamiques (ex: Opus) |

### 3.4 RTCP (RTP Control Protocol)

RTCP fonctionne conjointement avec RTP pour:
- Fournir des statistiques de qualité
- Synchroniser les flux
- Identifier les participants

**Types de paquets RTCP:**
- SR (Sender Report): Rapport d'envoi
- RR (Receiver Report): Rapport de réception
- SDES (Source Description): Description de source
- BYE: Indication de fin
- APP: Applications spécifiques

---

## 4. Protocole SDP (Session Description Protocol)

### 4.1 Présentation

SDP (RFC 4566) décrit les paramètres des sessions multimédias:
- Type de média (audio, vidéo)
- Codec et paramètres
- Adresses et ports
- Informations de timing

### 4.2 Format SDP

```
v=<version>          # Version du protocole (0)
o=<username> <session-id> <version> <network-type> <address-type> <address>
                     # Origine/propriétaire de la session
s=<session-name>     # Nom de la session
i=<session-info>     # Informations (optionnel)
u=<uri>              # URI (optionnel)
e=<email>            # Email (optionnel)
p=<phone>            # Téléphone (optionnel)
c=<network-type> <address-type> <connection-address>
                     # Informations de connexion
b=<bwtype>:<bandwidth> # Bande passante (optionnel)
t=<start-time> <stop-time> # Timing de la session
r=<repeat>           # Répétition (optionnel)
z=<timezone>         # Fuseau horaire (optionnel)
k=<key-type>         # Clé de chiffrement (optionnel)
a=<attribute>        # Attributs (optionnel)
m=<media> <port> <proto> <fmt> # Description du média
```

### 4.3 Exemple SDP Complet

```
v=0
o=alice 2890844526 2890844526 IN IP4 host.example.com
s=Appel VoIP
c=IN IP4 192.168.1.100
t=0 0
m=audio 49170 RTP/AVP 0 8 101
b=AS:64
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
a=rtpmap:101 telephone-event/8000
a=fmtp:101 0-15
a=ptime:20
a=maxptime:20
a=sendrecv
```

### 4.4 Attributs SDP Communs

| Attribut | Description |
|----------|-------------|
| rtpmap | Mapping payload type → codec |
| fmtp | Paramètres de format |
| ptime | Durée de packetisation (ms) |
| maxptime | Durée maximale de packetisation |
| sendrecv | Mode d'émission/réception |
| sendonly | Émission seulement |
| recvonly | Réception seulement |
| inactive | Media inactif |

---

## 5. Codec G.711

### 5.1 Présentation

G.711 (ITU-T) est un codec audio non compressé avec compression logarithmique:
- **Débit**: 64 kbps
- **Bande passante**: 300-3400 Hz (téléphonique)
- **Latence**: Très faible (< 1ms)
- **Qualité**: MOS 4.4

### 5.2 Variantes

| Variante | Région | Compression |
|----------|--------|-------------|
| μ-law (PCMU) | Amérique du Nord, Japon | Logarithme μ=255 |
| A-law (PCMA) | Europe, Reste du monde | Fonction A=87.7 |

### 5.3 Encodage

```
Échantillon PCM 13-bit → Compression logarithmique → 8-bit

μ-law:  F(x) = sign(x) * (ln(1 + μ|x|) / ln(1 + μ))
A-law:  F(x) = sign(x) * { A|x|/(1+lnA)           si |x| < 1/A
                           { (1+ln(A|x|))/(1+lnA)  sinon
```

### 5.4 Comparaison avec d'autres Codecs

| Codec | Débit | MOS | Complexité | Latence |
|-------|-------|-----|------------|---------|
| G.711 | 64 kbps | 4.4 | Très faible | < 1ms |
| G.729 | 8 kbps | 3.9 | Moyenne | 10ms |
| Opus | 6-510 kbps | 4.8 | Élevée | 5-20ms |
| G.722 | 48/56/64 kbps | 4.5 | Faible | < 1ms |

---

## 6. Séquence d'Établissement d'Appel

### 6.1 Diagramme de Séquence Complet

```
Client A (UAC)          Proxy/Registrar         Client B (UAS)
     │                        │                        │
     │─── REGISTER ──────────►│                        │
     │                        │─── Store Location ─────►│
     │<── 200 OK ─────────────│                        │
     │                        │                        │
     │─── INVITE ────────────►│                        │
     │                        │─── Lookup User ────────►│
     │<── 100 Trying ────────│                        │
     │                        │─── INVITE ────────────►│
     │                        │                        │
     │                        │<── 180 Ringing ────────│
     │<── 180 Ringing ───────│                        │
     │                        │                        │
     │                        │<── 200 OK (SDP B) ─────│
     │<── 200 OK (SDP B) ────│                        │
     │                        │                        │
     │─── ACK ──────────────►│                        │
     │                        │─── ACK ───────────────►│
     │                        │                        │
     │◄══════════════════════════════════════════════►│
     │              Session RTP Établie                │
     │                        │                        │
     │─── BYE ──────────────►│                        │
     │<── 200 OK ────────────│                        │
     │                        │─── BYE ───────────────►│
     │                        │<── 200 OK ─────────────│
     │                        │                        │
```

### 6.2 Négociation de Codecs

La négociation se fait via SDP dans l'INVITE et la réponse 200 OK:

**INVITE (offre):**
```
m=audio 8000 RTP/AVP 0 8 123
a=rtpmap:0 PCMU/8000
a=rtpmap:8 PCMA/8000
a=rtpmap:123 opus/48000/2
```

**200 OK (réponse - codec sélectionné):**
```
m=audio 9000 RTP/AVP 0
a=rtpmap:0 PCMU/8000
```

Dans cet exemple, PCMU (payload 0) a été sélectionné.

---

## 7. Références

1. **RFC 3261** - SIP: Session Initiation Protocol
2. **RFC 3262** - Reliability of Provisional Responses in SIP
3. **RFC 3264** - Offer/Answer Model with SDP
4. **RFC 3550** - RTP: A Transport Protocol for Real-Time Applications
5. **RFC 3551** - RTP Audio/Video Profiles
6. **RFC 4566** - SDP: Session Description Protocol
7. **ITU-T G.711** - Pulse code modulation (PCM) of voice frequencies

---

*Document technique - Projet VoIP 2024*
