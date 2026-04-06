"""
Interface Graphique pour le Client VoIP
Interface utilisateur avec Tkinter pour les appels
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
import sys
import time
import socket
from datetime import datetime
from typing import Optional

# Ajouter le parent directory au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sip_client import SIPClient


class VoIPClientGUI:
    """
    Interface graphique principale pour le client VoIP
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("VoIP Client")
        self.root.geometry("920x680")
        self.root.configure(bg="#0f172a")
        self.root.resizable(True, True)

        # Configuration du style
        self._setup_styles()

        # Client SIP
        self.client: Optional[SIPClient] = None
        self.config = self._load_config()

        # Variables d'état
        self.call_state = tk.StringVar(value="Déconnecté")
        self.call_duration = tk.StringVar(value="00:00")
        self.status_var = tk.StringVar(value="Initialisation...")
        
        self.last_call_direction = 'out'
        self.history_file = f"config/history_{self.config['client']['user_id']}.json"
        self.call_history = []
        
        self.ringing_event = threading.Event()
        self.ringing_thread = None
        self.local_hangup_handled = False
        self.registration_confirmed = False

        # Créer l'interface
        self._create_widgets()
        self._load_history()

        # Démarrer le client après un court délai
        self.root.after(100, self._start_client)

        # Timer pour mettre à jour la durée d'appel
        self._update_duration()

    def _setup_styles(self):
        """Configure les styles de l'interface"""
        style = ttk.Style()
        style.theme_use('clam')

        # Couleurs
        self.colors = {
            'bg_primary': '#0f172a',
            'bg_secondary': '#1e293b',
            'accent': '#3b82f6',
            'accent_hover': '#2563eb',
            'success': '#22c55e',
            'danger': '#ef4444',
            'warning': '#f59e0b',
            'text_light': '#e2e8f0',
            'text_dark': '#e2e8f0',
            'card_bg': '#111827',
            'input_bg': '#0b1220',
            'border': '#334155'
        }

        # Configuration des styles
        style.configure('Title.TLabel', font=('Segoe UI', 18, 'bold'), background=self.colors['bg_primary'], foreground=self.colors['text_light'])
        style.configure('Status.TLabel', font=('Segoe UI', 10), background=self.colors['bg_secondary'], foreground=self.colors['text_light'])
        style.configure('Call.TLabel', font=('Segoe UI', 12, 'bold'), background=self.colors['bg_secondary'], foreground=self.colors['text_light'])
        style.configure('TNotebook', background=self.colors['bg_primary'], borderwidth=0)
        style.configure('TNotebook.Tab', font=('Segoe UI', 10, 'bold'), padding=[12, 6], background=self.colors['bg_secondary'], foreground=self.colors['text_light'])
        style.map('TNotebook.Tab', background=[('selected', self.colors['accent'])], foreground=[('selected', 'white')])

    def _load_config(self) -> dict:
        """Charge la configuration (fichier ou sélection utilisateur au démarrage)."""
        if len(sys.argv) > 1:
            config_file = sys.argv[1]
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except FileNotFoundError:
                messagebox.showwarning("Configuration", f"Fichier introuvable: {config_file}\nUtilisation de la sélection utilisateur.")

        base_client = self._read_json('config/client_config.json', {
            'client': {
                'server_host': 'localhost',
                'server_port': 5060,
                'local_rtp_port': 0,
            },
            'audio': {
                'sample_rate': 8000,
                'channels': 1,
                'frame_size': 160,
                'codec': 'PCMU',
                'echo_cancellation': True,
                'noise_suppression': True,
            },
            'ui': {
                'theme': 'default',
                'language': 'fr',
                'show_notifications': True,
            },
            'network': {
                'stun_enabled': False,
                'stun_server': 'stun.l.google.com',
                'stun_port': 19302,
                'stun_timeout': 1.5,
            },
            'contacts': [],
        })

        server_cfg = self._read_json('config/server_config.json', {'users': {}, 'server': {}})
        users = server_cfg.get('users', {})

        if not users:
            fallback = {
                'client': {
                    'user_id': '1001',
                    'username': 'user1001',
                    'password': '',
                    'display_name': 'Utilisateur',
                    'server_host': base_client.get('client', {}).get('server_host', 'localhost'),
                    'server_port': base_client.get('client', {}).get('server_port', 5060),
                    'local_rtp_port': base_client.get('client', {}).get('local_rtp_port', 0),
                },
                'audio': base_client.get('audio', {}),
                'ui': base_client.get('ui', {}),
                'network': base_client.get('network', {}),
                'contacts': [],
            }
            return fallback

        selected_user_id = self._select_user_dialog(users)
        if not selected_user_id:
            selected_user_id = next(iter(users.keys()))

        selected_user = users.get(selected_user_id, {})

        contacts = [
            {'id': uid, 'name': info.get('display_name', uid)}
            for uid, info in users.items()
            if uid != selected_user_id
        ]

        return {
            'client': {
                'user_id': selected_user_id,
                'username': selected_user.get('username', selected_user_id),
                'password': selected_user.get('password', ''),
                'display_name': selected_user.get('display_name', selected_user_id),
                'server_host': base_client.get('client', {}).get('server_host', 'localhost'),
                'server_port': base_client.get('client', {}).get('server_port', 5060),
                'local_rtp_port': base_client.get('client', {}).get('local_rtp_port', 0),
            },
            'audio': base_client.get('audio', {}),
            'ui': base_client.get('ui', {}),
            'network': base_client.get('network', {}),
            'contacts': contacts,
        }

    def _read_json(self, file_path: str, default_value: dict) -> dict:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default_value

    def _select_user_dialog(self, users: dict) -> Optional[str]:
        """Affiche une boîte de dialogue de sélection utilisateur."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Choisir un utilisateur")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=self.colors['bg_primary'])

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width, height = 420, 230
        x = int((screen_w - width) / 2)
        y = int((screen_h - height) / 2)
        dialog.geometry(f"{width}x{height}+{x}+{y}")

        tk.Label(
            dialog,
            text="Sélectionnez le compte à utiliser",
            font=('Segoe UI', 13, 'bold'),
            bg=self.colors['bg_primary'],
            fg=self.colors['text_light']
        ).pack(pady=(20, 12))

        options = [f"{uid} - {info.get('display_name', uid)}" for uid, info in users.items()]
        selected = tk.StringVar(value=options[0])

        combo = ttk.Combobox(dialog, textvariable=selected, values=options, state='readonly', width=38)
        combo.pack(pady=8)
        combo.focus_set()

        result = {'user_id': None}

        def confirm():
            value = selected.get()
            result['user_id'] = value.split(' - ')[0].strip()
            dialog.destroy()

        def cancel():
            dialog.destroy()

        btn_row = tk.Frame(dialog, bg=self.colors['bg_primary'])
        btn_row.pack(pady=20)

        tk.Button(
            btn_row,
            text="Valider",
            command=confirm,
            bg=self.colors['success'],
            fg='white',
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor='hand2'
        ).pack(side=tk.LEFT, padx=6)

        tk.Button(
            btn_row,
            text="Annuler",
            command=cancel,
            bg=self.colors['danger'],
            fg='white',
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor='hand2'
        ).pack(side=tk.LEFT, padx=6)

        dialog.bind('<Return>', lambda _: confirm())
        dialog.bind('<Escape>', lambda _: cancel())
        dialog.wait_window()

        return result['user_id']

    def _create_widgets(self):
        """Crée tous les widgets de l'interface"""
        # Frame d'en-tête
        self._create_header()

        # Frame d'état
        self._create_status_frame()

        # Nouveau Design avec Onglets
        style = ttk.Style()
        style.configure('TNotebook.Tab', font=('Segoe UI', 10, 'bold'), padding=[10, 5])
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.tab_home = tk.Frame(self.notebook, bg=self.colors['card_bg'])
        self.tab_contacts = tk.Frame(self.notebook, bg=self.colors['card_bg'])
        self.tab_history = tk.Frame(self.notebook, bg=self.colors['card_bg'])
        self.tab_logs = tk.Frame(self.notebook, bg=self.colors['card_bg'])
        
        self.notebook.add(self.tab_home, text="Accueil")
        self.notebook.add(self.tab_contacts, text="Contacts")
        self.notebook.add(self.tab_history, text="Historique")
        self.notebook.add(self.tab_logs, text="Logs")

        # Contenu des onglets
        self._create_dial_frame(self.tab_home)
        self._create_call_controls(self.tab_home)
        
        self._create_contacts_frame(self.tab_contacts)
        self._create_history_frame(self.tab_history)
        self._create_log_frame(self.tab_logs)

    def _create_header(self):
        """Crée l'en-tête"""
        header = tk.Frame(self.root, bg=self.colors['bg_primary'], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        title = tk.Label(
            header,
            text="📞 VoIP Client",
            font=('Segoe UI', 20, 'bold'),
            bg=self.colors['bg_primary'],
            fg=self.colors['text_light']
        )
        title.pack(pady=15)

    def _create_status_frame(self):
        """Crée la frame d'état de connexion"""
        status_frame = tk.Frame(self.root, bg=self.colors['bg_secondary'], height=40)
        status_frame.pack(fill=tk.X)
        status_frame.pack_propagate(False)

        # État de connexion
        conn_label = tk.Label(
            status_frame,
            text="État:",
            font=('Helvetica', 10),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_light']
        )
        conn_label.pack(side=tk.LEFT, padx=10)

        self.status_label = tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=('Helvetica', 10, 'bold'),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_light']
        )
        self.status_label.pack(side=tk.LEFT, padx=5)

        # Indicateur LED
        self.led_canvas = tk.Canvas(status_frame, width=20, height=20, bg=self.colors['bg_secondary'], highlightthickness=0)
        self.led = self.led_canvas.create_oval(5, 5, 15, 15, fill='gray')
        self.led_canvas.pack(side=tk.RIGHT, padx=10)

    def _create_dial_frame(self, parent):
        """Crée la frame de composition du numéro"""
        dial_frame = tk.Frame(parent, bg=self.colors['card_bg'], pady=10)
        dial_frame.pack(fill=tk.X, padx=20, pady=10)

        # Titre
        tk.Label(
            dial_frame,
            text="Composer un numéro",
            font=('Segoe UI', 12, 'bold'),
            fg=self.colors['text_light'],
            bg=self.colors['card_bg']
        ).pack(pady=5)

        # Entry pour le numéro
        entry_frame = tk.Frame(dial_frame, bg=self.colors['card_bg'])
        entry_frame.pack(pady=5)

        self.number_entry = tk.Entry(
            entry_frame,
            font=('Segoe UI', 16),
            justify='center',
            width=20,
            bd=0,
            relief=tk.FLAT,
            bg=self.colors['input_bg'],
            fg=self.colors['text_light'],
            insertbackground=self.colors['text_light'],
            highlightthickness=1,
            highlightbackground=self.colors['border'],
            highlightcolor=self.colors['accent']
        )
        self.number_entry.pack(side=tk.LEFT, padx=5)
        self.number_entry.bind('<Return>', lambda e: self._call())

        # Bouton Appeler
        self.call_btn = tk.Button(
            entry_frame,
            text="📞 Appeler",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['success'],
            fg='white',
            bd=0,
            padx=20,
            pady=8,
            cursor='hand2',
            command=self._call
        )
        self.call_btn.pack(side=tk.LEFT, padx=5)

        # Clavier numérique
        keypad_frame = tk.Frame(dial_frame, bg=self.colors['card_bg'])
        keypad_frame.pack(pady=10)

        buttons = [
            ['1', '2', '3'],
            ['4', '5', '6'],
            ['7', '8', '9'],
            ['*', '0', '#']
        ]

        for row_idx, row in enumerate(buttons):
            for col_idx, digit in enumerate(row):
                btn = tk.Button(
                    keypad_frame,
                    text=digit,
                    font=('Segoe UI', 14, 'bold'),
                    width=4,
                    height=2,
                    bg='#1f2937',
                    fg=self.colors['text_light'],
                    activebackground='#334155',
                    activeforeground=self.colors['text_light'],
                    bd=0,
                    relief=tk.FLAT,
                    command=lambda d=digit: self._append_digit(d)
                )
                btn.grid(row=row_idx, column=col_idx, padx=3, pady=3)

    def _create_contacts_frame(self, parent):
        """Crée la frame des contacts"""
        contacts_frame = tk.LabelFrame(
            parent,
            text="  Contacts  ",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['card_bg'],
            fg=self.colors['text_light'],
            padx=10,
            pady=10
        )
        contacts_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Liste des contacts
        self.contacts_listbox = tk.Listbox(
            contacts_frame,
            font=('Segoe UI', 11),
            height=5,
            bg=self.colors['input_bg'],
            fg=self.colors['text_light'],
            bd=0,
            highlightthickness=1,
            highlightbackground=self.colors['border'],
            selectbackground=self.colors['accent'],
            selectforeground='white'
        )
        self.contacts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(contacts_frame, orient=tk.VERTICAL, command=self.contacts_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.contacts_listbox.configure(yscrollcommand=scrollbar.set)

        # Charger les contacts
        self._load_contacts()

        # Double-click pour appeler
        self.contacts_listbox.bind('<Double-Button-1>', lambda e: self._call_selected_contact())

    def _create_call_controls(self, parent):
        """Crée les contrôles d'appel"""
        controls_frame = tk.Frame(parent, bg=self.colors['card_bg'], pady=15)
        controls_frame.pack(fill=tk.X, padx=20)

        # Informations d'appel
        self.call_info_label = tk.Label(
            controls_frame,
            text="Aucun appel en cours",
            font=('Segoe UI', 14),
            bg=self.colors['card_bg'],
            fg=self.colors['text_light']
        )
        self.call_info_label.pack(pady=5)

        # Durée d'appel
        self.duration_label = tk.Label(
            controls_frame,
            textvariable=self.call_duration,
            font=('Consolas', 24, 'bold'),
            bg=self.colors['card_bg'],
            fg=self.colors['text_dark']
        )
        self.duration_label.pack(pady=5)

        # Boutons de contrôle
        btn_frame = tk.Frame(controls_frame, bg=self.colors['card_bg'])
        btn_frame.pack(pady=10)

        # Bouton Décrocher (visible pendant appel entrant)
        self.answer_btn = tk.Button(
            btn_frame,
            text="📞 Décrocher",
            font=('Segoe UI', 12, 'bold'),
            bg=self.colors['success'],
            fg='white',
            bd=0,
            padx=30,
            pady=15,
            cursor='hand2',
            command=self._accept_call,
            state=tk.DISABLED
        )
        self.answer_btn.pack(side=tk.LEFT, padx=10)

        # Bouton Raccrocher (rouge, grand)
        self.hangup_btn = tk.Button(
            btn_frame,
            text="📴 Raccrocher",
            font=('Segoe UI', 12, 'bold'),
            bg=self.colors['danger'],
            fg='white',
            bd=0,
            padx=30,
            pady=15,
            cursor='hand2',
            command=self._hangup,
            state=tk.DISABLED
        )
        self.hangup_btn.pack(side=tk.LEFT, padx=10)

        # Bouton Mute
        self.mute_btn = tk.Button(
            btn_frame,
            text="🔇 Mute",
            font=('Segoe UI', 10),
            bg='#95A5A6',
            fg='white',
            bd=0,
            padx=15,
            pady=10,
            cursor='hand2',
            command=self._toggle_mute
        )
        self.mute_btn.pack(side=tk.LEFT, padx=5)
        self.mute_btn.config(state=tk.DISABLED)

        # Bouton Hold
        self.hold_btn = tk.Button(
            btn_frame,
            text="⏸️ Hold",
            font=('Segoe UI', 10),
            bg='#95A5A6',
            fg='white',
            bd=0,
            padx=15,
            pady=10,
            cursor='hand2',
            command=self._toggle_hold
        )
        self.hold_btn.pack(side=tk.LEFT, padx=5)
        self.hold_btn.config(state=tk.DISABLED)

    def _create_history_frame(self, parent):
        """Crée la frame d'historique"""
        history_frame = tk.LabelFrame(
            parent,
            text="  Historique des appels  ",
            font=('Segoe UI', 11, 'bold'),
            bg=self.colors['card_bg'],
            fg=self.colors['text_light'],
            padx=10,
            pady=10
        )
        history_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Liste de l'historique
        self.history_listbox = tk.Listbox(
            history_frame,
            font=('Segoe UI', 10),
            height=6,
            bg=self.colors['input_bg'],
            fg=self.colors['text_light'],
            bd=0,
            highlightthickness=1,
            highlightbackground=self.colors['border'],
            selectbackground=self.colors['accent'],
            selectforeground='white'
        )
        self.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.history_listbox.bind('<Double-Button-1>', lambda e: self._call_selected_history())

    def _create_log_frame(self, parent):
        """Crée la frame de logs"""
        log_frame = tk.LabelFrame(
            parent,
            text="  Logs  ",
            font=('Segoe UI', 10, 'bold'),
            bg=self.colors['card_bg'],
            fg=self.colors['text_light'],
            padx=10,
            pady=10
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Zone de texte pour les logs
        self.log_text = tk.Text(
            log_frame,
            font=('Consolas', 10),
            height=4,
            bg=self.colors['input_bg'],
            fg=self.colors['text_light'],
            insertbackground=self.colors['text_light'],
            bd=0,
            highlightthickness=1,
            highlightbackground=self.colors['border'],
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _load_contacts(self):
        """Charge les contacts dans la liste"""
        contacts = self.config.get('contacts', [])
        for contact in contacts:
            display = f"{contact['name']} ({contact['id']})"
            self.contacts_listbox.insert(tk.END, display)

    def _load_history(self):
        """Charge l'historique depuis le JSON"""
        try:
            with open(self.history_file, 'r') as f:
                self.call_history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.call_history = []
            
        self.history_listbox.delete(0, tk.END)
        for call in self.call_history:
            self._insert_history_ui(call, append=True)
            
    def _save_history(self):
        """Sauvegarde l'historique dans un fichier JSON"""
        os.makedirs('config', exist_ok=True)
        with open(self.history_file, 'w') as f:
            json.dump(self.call_history, f, indent=4)
            
    def _insert_history_ui(self, call: dict, append: bool = False):
        """Insère un appel unique dans la vue de l'historique"""
        date_str = call.get('time', '')
        remote = call.get('remote', 'Inconnu')
        dir_icon = "📞" if call.get('direction') == 'out' else "📥"
        duration = call.get('duration', '00:00')
        status = call.get('status', '')
        
        missed = " [Manqué]" if status == 'missed' else ""
        text = f"[{date_str}] {dir_icon} {remote} | {duration}{missed}"
        
        if append:
            self.history_listbox.insert(tk.END, text)
            idx = self.history_listbox.size() - 1
        else:
            self.history_listbox.insert(0, text)
            idx = 0
            
        if status == 'missed':
            self.history_listbox.itemconfig(idx, {'fg': self.colors['danger']})

    def _call_selected_history(self):
        """Rappelle le numéro double-cliqué dans l'historique"""
        selection = self.history_listbox.curselection()
        if selection:
            item = self.history_listbox.get(selection[0])
            try:
                # Format: [YYYY-MM-DD HH:MM] ICON ID | 00:00
                part1 = item.split(" | ")[0]
                remote_id = part1.split(" ")[-1]
                self.number_entry.delete(0, tk.END)
                self.number_entry.insert(0, remote_id)
                self._call()
            except Exception as e:
                self._log(f"Impossible de rappeler depuis l'historique: {e}")

    def _start_client(self):
        """Démarre le client SIP"""
        self.status_var.set("Connexion au serveur SIP...")

        self._auto_switch_server_host()

        def start():
            try:
                self.client = SIPClient(self.config)

                # Configurer les callbacks
                self.client.on_registration_success = self._on_registered
                self.client.on_registration_failed = self._on_register_failed
                self.client.on_call_started = self._on_call_started
                self.client.on_call_ended = self._on_call_ended
                self.client.on_incoming_call = self._on_incoming_call
                self.client.on_call_state_changed = self._on_call_state_changed

                self.client.start()

            except Exception as e:
                self.root.after(0, lambda: self._log(f"Erreur: {e}"))
                self.root.after(0, lambda: self.status_var.set("Erreur de démarrage"))

        thread = threading.Thread(target=start, daemon=True)
        thread.start()

        # Si aucune réponse REGISTER n'arrive, éviter de rester bloqué sur "Initialisation..."
        self.root.after(8000, self._check_registration_timeout)

    def _auto_switch_server_host(self):
        """Bascule automatiquement vers un serveur SIP joignable si l'hôte configuré ne répond pas."""
        client_cfg = self.config.get('client', {})
        current_host = client_cfg.get('server_host', 'localhost')
        current_port = int(client_cfg.get('server_port', 5060))

        if self._probe_sip_host(current_host, current_port, timeout=0.9):
            return

        discovered_host = self._discover_sip_server(current_port, timeout=2.2)
        if discovered_host and discovered_host != current_host:
            self.config['client']['server_host'] = discovered_host
            self._log(f"Serveur SIP auto-détecté: {discovered_host}:{current_port} (ancien: {current_host})")
            self.status_var.set(f"Serveur auto-détecté: {discovered_host}")
        elif discovered_host:
            self.status_var.set(f"Serveur détecté: {discovered_host}")
        else:
            self._log(f"Auto-détection SIP indisponible, serveur conservé: {current_host}:{current_port}")

    def _probe_sip_host(self, host: str, port: int, timeout: float = 0.9) -> bool:
        """Teste si un hôte répond à une requête SIP OPTIONS."""
        probe = (
            f"OPTIONS sip:{host} SIP/2.0\r\n"
            f"Via: SIP/2.0/UDP 0.0.0.0;branch=z9hG4bK-probe\r\n"
            f"From: <sip:probe@local>;tag=probe\r\n"
            f"To: <sip:probe@{host}>\r\n"
            f"Call-ID: probe-{int(time.time() * 1000)}\r\n"
            f"CSeq: 1 OPTIONS\r\n"
            f"Content-Length: 0\r\n\r\n"
        ).encode('utf-8')

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(('0.0.0.0', 0))
            sock.settimeout(timeout)
            sock.sendto(probe, (host, port))
            data, _ = sock.recvfrom(2048)
            text = data.decode('utf-8', errors='ignore')
            return text.startswith('SIP/2.0 200') or text.startswith('SIP/2.0 100')
        except Exception:
            return False
        finally:
            sock.close()

    def _discover_sip_server(self, port: int, timeout: float = 2.2) -> Optional[str]:
        """Découvre un serveur SIP sur le LAN via broadcast OPTIONS."""
        probe = (
            "OPTIONS sip:discover SIP/2.0\r\n"
            "Via: SIP/2.0/UDP 0.0.0.0;branch=z9hG4bK-discover\r\n"
            "From: <sip:discover@local>;tag=discover\r\n"
            "To: <sip:discover@lan>\r\n"
            f"Call-ID: discover-{int(time.time() * 1000)}\r\n"
            "CSeq: 1 OPTIONS\r\n"
            "Content-Length: 0\r\n\r\n"
        ).encode('utf-8')

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(('0.0.0.0', 0))
            sock.settimeout(0.45)
            sock.sendto(probe, ('255.255.255.255', port))

            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    data, addr = sock.recvfrom(2048)
                    text = data.decode('utf-8', errors='ignore')
                    if text.startswith('SIP/2.0 200') or text.startswith('SIP/2.0 100'):
                        return addr[0]
                except socket.timeout:
                    continue

            return None
        except Exception:
            return None
        finally:
            sock.close()

    def _check_registration_timeout(self):
        """Signale un timeout de connexion si l'enregistrement SIP n'a pas abouti."""
        if not self.registration_confirmed:
            self._update_led('red')
            self.status_var.set("Échec: timeout enregistrement SIP")
            self._log(
                f"Aucune réponse REGISTER de {self.config['client']['server_host']}:{self.config['client']['server_port']}"
            )

    def _on_registered(self):
        """Callback: enregistré avec succès"""
        self.registration_confirmed = True
        self.root.after(0, lambda: self._update_led('green'))
        self.root.after(0, lambda: self.status_var.set(f"Connecté - {self.config['client']['user_id']}"))
        self.root.after(0, lambda: self._log("Enregistré auprès du serveur"))

    def _on_register_failed(self, error):
        """Callback: échec d'enregistrement"""
        self.registration_confirmed = True
        self.root.after(0, lambda: self._update_led('red'))
        self.root.after(0, lambda: self.status_var.set(f"Échec: {error}"))
        self.root.after(0, lambda: self._log(f"Échec enregistrement: {error}"))

    def _on_call_started(self, remote_user):
        """Callback: appel démarré"""
        self.root.after(0, lambda: self.call_info_label.config(
            text=f"En appel avec {remote_user}",
            fg=self.colors['success']
        ))
        self.root.after(0, lambda: self.hangup_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.mute_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.hold_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.call_btn.config(
            text="📴 Raccrocher",
            command=self._hangup,
            state=tk.NORMAL
        ))
        self.root.after(0, lambda: self._log(f"Appel établi avec {remote_user}"))

    def _on_call_ended(self, remote_user):
        """Callback: appel terminé"""
        if self.local_hangup_handled:
            self.local_hangup_handled = False
            return

        duration = self.call_duration.get()
        status = 'completed'
        if duration == "00:00":
            status = 'missed'

        call_record = {
            'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'remote': remote_user,
            'direction': self.last_call_direction,
            'duration': duration,
            'status': status
        }
        self.call_history.insert(0, call_record)
        self._insert_history_ui(call_record, append=False)
        self._save_history()

        self.root.after(0, lambda: self.call_info_label.config(
            text="Aucun appel en cours",
            fg='#7F8C8D'
        ))
        self.root.after(0, self._reset_call_buttons)
        self.root.after(0, lambda: self.call_duration.set("00:00"))
        self.root.after(0, lambda: self._log(f"Appel terminé avec {remote_user}"))

    def _on_incoming_call(self, caller_id):
        """Callback: appel entrant"""
        self.last_call_direction = 'in'
        self.root.after(0, lambda: self.call_info_label.config(
            text=f"Appel entrant de {caller_id}",
            fg=self.colors['warning']
        ))
        
        self.root.after(0, lambda: self.call_btn.config(
            text="📞 Décrocher",
            command=self._accept_call,
            state=tk.NORMAL
        ))
        self.root.after(0, lambda: self.answer_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.hangup_btn.config(
            text="📴 Refuser",
            command=self._reject_call,
            state=tk.NORMAL
        ))
        
        self.root.after(0, lambda: self._log(f"Appel entrant: {caller_id}"))
        self._start_ringing_sound()

    def _on_call_state_changed(self, state):
        """Callback: changement d'état d'appel"""
        if state == 'ringing':
            self._start_ringing_sound()
        elif state in ['active', 'terminated']:
            self._stop_ringing_sound()
            
        states = {
            'initiating': ('Appel en cours...', self.colors['warning']),
            'ringing': ('Ça sonne...', self.colors['warning']),
            'active': ('En appel', self.colors['success']),
            'on_hold': ('En attente', self.colors['accent']),
            'terminated': ('Appel terminé', '#7F8C8D')
        }
        text, color = states.get(state, (state, 'gray'))
        self.root.after(0, lambda: self.call_info_label.config(text=text, fg=color))
        self.root.after(0, lambda: self._log(f"État: {state}"))

    def _update_led(self, color):
        """Met à jour la LED d'état"""
        colors = {'green': '#27AE60', 'red': '#E74C3C', 'yellow': '#F39C12', 'gray': 'gray'}
        self.led_canvas.itemconfig(self.led, fill=colors.get(color, 'gray'))

    def _log(self, message):
        """Ajoute un message aux logs"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _update_duration(self):
        """Met à jour la durée d'appel"""
        if self.client and self.client.current_call:
            self.call_duration.set(self.client.get_call_duration())
        self.root.after(1000, self._update_duration)

    def _append_digit(self, digit):
        """Ajoute un chiffre au numéro"""
        current = self.number_entry.get()
        self.number_entry.delete(0, tk.END)
        self.number_entry.insert(0, current + digit)

    def _reset_call_buttons(self):
        """Réinitialise l'état des boutons d'appel"""
        self.call_btn.config(
            text="📞 Appeler",
            command=self._call,
            state=tk.NORMAL
        )
        self.answer_btn.config(state=tk.DISABLED)
        self.hangup_btn.config(
            text="📴 Raccrocher",
            command=self._hangup,
            state=tk.DISABLED
        )
        self.mute_btn.config(state=tk.DISABLED)
        self.hold_btn.config(state=tk.DISABLED)

    def _call(self):
        """Initie un appel"""
        if not self.client:
            self._log("Client SIP non prêt")
            return

        number = self.number_entry.get().strip()
        if number:
            self.last_call_direction = 'out'
            
            # Activer immédiatement le bouton de raccrochage en mode "Annuler"
            self.root.after(0, lambda: self.hangup_btn.config(
                text="📴 Annuler",
                command=self._hangup,
                state=tk.NORMAL
            ))
            self.root.after(0, lambda: self.call_btn.config(
                text="📴 Annuler",
                command=self._hangup,
                state=tk.NORMAL
            ))
            
            self._log(f"Appel de {number}...")
            self.client.call(number)

    def _call_selected_contact(self):
        """Appelle le contact sélectionné"""
        selection = self.contacts_listbox.curselection()
        if selection:
            item = self.contacts_listbox.get(selection[0])
            # Extraire l'ID du contact
            contact_id = item.split('(')[-1].strip(')')
            self.number_entry.delete(0, tk.END)
            self.number_entry.insert(0, contact_id)
            self._call()

    def _hangup(self):
        """Termine l'appel en cours"""
        if self.client:
            self.local_hangup_handled = True
            self._stop_ringing_sound()
            self._log("Raccrochage...")
            remote = self.client.current_call.remote_user if self.client.current_call else 'inconnu'
            duration = self.call_duration.get()
            self.client.hangup()

            call_record = {
                'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'remote': remote,
                'direction': self.last_call_direction,
                'duration': duration,
                'status': 'cancelled' if duration == '00:00' else 'completed'
            }
            self.call_history.insert(0, call_record)
            self._insert_history_ui(call_record, append=False)
            self._save_history()

            self.call_duration.set("00:00")
            self.call_info_label.config(text="Aucun appel en cours", fg=self.colors['text_light'])
            self.root.after(0, self._reset_call_buttons)

    def _accept_call(self):
        """Accepte un appel entrant"""
        if self.client:
            self._stop_ringing_sound()
            self._log("Acceptation de l'appel")
            
            self.root.after(0, lambda: self.answer_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.call_btn.config(
                text="📴 Raccrocher",
                command=self._hangup,
                state=tk.NORMAL
            ))
            self.root.after(0, lambda: self.hangup_btn.config(
                text="📴 Raccrocher",
                command=self._hangup,
                state=tk.NORMAL
            ))
            
            self.client.accept_call()

    def _reject_call(self):
        """Rejette un appel entrant"""
        if self.client:
            self._stop_ringing_sound()
            self._log("Rejet de l'appel")
            self.client.reject_call()
            self.root.after(0, self._reset_call_buttons)

    def _start_ringing_sound(self):
        """Démarre le son de sonnerie"""
        self.ringing_event.set()
        
        def ring_loop():
            import winsound
            while self.ringing_event.is_set():
                try:
                    winsound.Beep(440, 1000)
                    for _ in range(20):
                        if not self.ringing_event.is_set():
                            break
                        time.sleep(0.1)
                except Exception:
                    break
                    
        if not self.ringing_thread or not self.ringing_thread.is_alive():
            self.ringing_thread = threading.Thread(target=ring_loop, daemon=True)
            self.ringing_thread.start()

    def _stop_ringing_sound(self):
        """Arrête le son de sonnerie"""
        self.ringing_event.clear()

    def _toggle_mute(self):
        """Active/désactive le mute"""
        self._log("Mute (non implémenté)")
        # À implémenter avec le vrai handler audio

    def _toggle_hold(self):
        """Met en attente/reprend l'appel"""
        self._log("Hold (non implémenté)")
        # À implémenter

    def _on_closing(self):
        """Gère la fermeture de la fenêtre"""
        self._stop_ringing_sound()
        if self.client:
            self.client.stop()
        self.root.destroy()


def main():
    """Point d'entrée principal"""
    root = tk.Tk()

    # Icône (si disponible)
    try:
        root.iconbitmap('icon.ico')
    except Exception:
        pass

    app = VoIPClientGUI(root)
    root.protocol("WM_DELETE_WINDOW", app._on_closing)
    root.mainloop()


if __name__ == '__main__':
    main()
