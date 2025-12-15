import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from random import choice, randint, random
import sys
import os

from SocketLib import sendMessage, recvMessage
class RoundInfo:
    """Datová struktura pro uchování tipů a hodnocení jednoho kola."""
    def __init__(self, roundNumber, num_pegs=4):
        self.roundNumber = roundNumber
        # 6 = bílá / bez barvy - default hodnota
        self.guesses = [[6] * num_pegs] 
        self.evaluations = [] # List hodnocení


class LogikApp:
    def __init__(self, master, host, port):
        self.master = master
        self.master.title("Mastermind Logik Klient")
        self.master.geometry("600x800")
        self.master.minsize(550, 750)
        
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except tk.TclError:
             # Pokud clam není dostupný
            pass
        
        # Centrování okna
        self._center_window(600, 800)
        
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # --- KLIENTSKÝ STAV ---
        self.host = host
        self.port = port
        self.name = None
        self.role = None
        self.socket = None
        self.connected = False
        self.GAME_PREFIX = "LK"
        self.reconnected = False
        self.reconnectData = None
        self.input_values = None 
        self.other_player_name = None
        
        # --- HERNÍ STAV ---
        self.isRunning = False
        self.isPaused = False
        # Vylepšená paleta barev s lepším kontrastem
        self.palette = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4"] # 6 barev (0-5)
        self.num_pegs = 4
        self.currentRoundNumber = 0 
        self.rounds = []
        self.reconnecting = False
        self.disconnected_time = None
        self.me_online = 1
        self.opponent_online = 1
        self.opponent_name = "Protihráč"
        
        # --- UI PRVKY ---
        self.current_frame = None
        self.status_label = None 
        self._input_panel_initialized = False
        
        # Vytvoření hlavního rámečku
        self.main_container = tk.Frame(self.master, bg="#fcfcfc") # Světlejší pozadí
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Spuštění
        self._initialize_rounds()
        self.connect_to_server()
        self.show_login()

    def _center_window(self, width, height):
        """Centruje okno na obrazovce."""
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x_position = int((screen_width / 2) - (width / 2))
        y_position = int((screen_height / 2) - (height / 2))
        self.master.geometry(f"{width}x{height}+{x_position}+{y_position}")
        
    def _initialize_rounds(self):
        """Inicializuje 10 prázdných kol pro novou hru."""
        self.rounds = []
        for i in range(10):
            self.rounds.append(RoundInfo(i, self.num_pegs))

    # =========================================================================
    # Přepínání UI zobrazení (Login, Lobby, Game)
    # =========================================================================

    def _clear_frame(self):
        """Vymaže všechny widgety z hlavního kontejneru."""
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = None

    def show_login(self):
        self._clear_frame()
        self.current_frame = tk.Frame(self.main_container, bg="#fcfcfc", padx=20, pady=20)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.current_frame, text="Přihlášení do hry Logik", font=("Helvetica", 20, "bold"), fg="#111111", bg="#fcfcfc").pack(pady=(50, 30))

        form_frame = tk.Frame(self.current_frame, bg="#ffffff", bd=1, relief=tk.RAISED, padx=40, pady=40)
        form_frame.pack(pady=15)

        # Vstup pro jméno (použijeme ttk.Entry)
        tk.Label(form_frame, text="Jméno:", font=("Helvetica", 12), bg="#ffffff").grid(row=0, column=0, pady=10, sticky="w")
        self.name_entry = ttk.Entry(form_frame, width=30, font=("Helvetica", 12))
        self.name_entry.grid(row=0, column=1, padx=10)

        # Vstup pro roli (použijeme ttk.Entry)
        tk.Label(form_frame, text="Role (0=Tipující, 1=Hodnotitel):", font=("Helvetica", 12), bg="#ffffff").grid(row=1, column=0, pady=10, sticky="w")
        self.role_entry = ttk.Entry(form_frame, width=30, font=("Helvetica", 12))
        self.role_entry.grid(row=1, column=1, padx=10)

        # Stavový label pro Login
        self.login_status_label = tk.Label(self.current_frame, text="Stav: Připojeno k serveru", fg="#3cb44b", bg="#fcfcfc", font=("Helvetica", 10))
        self.login_status_label.pack(pady=15)
        
        # Tlačítka (použijeme ttk.Button)
        btn_frame = tk.Frame(self.current_frame, bg="#fcfcfc")
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Přihlásit se", command=self.submit_login, style='Accent.TButton').pack(side=tk.LEFT, padx=15, ipadx=10, ipady=5)
        
        ttk.Button(btn_frame, text="Obnovit hru (Reconnect)", command=lambda: self.handleReconnect(self.name_entry.get(), self.role_entry.get())).pack(side=tk.LEFT, padx=15, ipadx=10, ipady=5)

    def show_lobby(self):
        self._clear_frame()
        self.current_frame = tk.Frame(self.main_container, bg="#fcfcfc", padx=20, pady=20)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self.current_frame, text="Herní Lobby", font=("Helvetica", 20, "bold"), fg="#111111", bg="#fcfcfc").pack(pady=(10, 20))
        
        # Status Label pro Lobby
        self.status_label = tk.Label(self.current_frame, text="Načítám místnosti...", fg="#4363d8", bg="#fcfcfc", font=("Helvetica", 12))
        self.status_label.pack(pady=10)
        
        # Rámeček pro scroll
        self.room_list_frame = tk.Frame(self.current_frame, bg="#ffffff", bd=1, relief=tk.RIDGE)
        self.room_list_frame.pack(pady=10, fill=tk.BOTH, expand=True, padx=20)
        
        # Spustit načítání
        threading.Thread(target=self.choose_room, daemon=True).start()

    def show_game(self, start_type='new'):
        self._clear_frame()
        self.isRunning = True
        
        self.game_frame = tk.Frame(self.main_container, bg="#fcfcfc")
        self.game_frame.pack(fill=tk.BOTH, expand=True)
        self.current_frame = self.game_frame 

        # --- Top Panel (Status, Info, Presence) ---
        self.top_frame = tk.Frame(self.game_frame, bg="#ffffff", bd=1, relief=tk.FLAT, padx=10, pady=5)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)
        
        self.status_label = tk.Label(self.top_frame, text="Hra běží", fg="#3cb44b", font=("Helvetica", 14, "bold"), bg="#ffffff")
        self.status_label.pack(pady=5)
        
        role_text = "Hodnotitel" if self.role == 1 else "Tipující"
        tk.Label(self.top_frame, text=f"Hráč: {self.name} | Role: {role_text}", font=("Helvetica", 10), bg="#ffffff").pack(pady=2)

        # Testovací tlačítko: pošli záměrně vadnou zprávu serveru
        test_btn = ttk.Button(self.top_frame, text="Odeslat vadnou zprávu", command=self.send_bad_message)
        test_btn.pack(pady=5)

        # Presence Bar
        self.buildPresenceBar(self.top_frame)

        # --- Evaluator Secret Combination Display ---
        self.secret_frame = tk.Frame(self.game_frame, bg="#fcfcfc")
        if self.role == 1:
            self.secret_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
            # Vylepšené vykreslení tajné kombinace
            self.secret_canvas = tk.Canvas(self.secret_frame, width=250, height=40, bg="#fcfcfc", highlightthickness=0)
            self.secret_canvas.pack(side=tk.LEFT, padx=150)
            tk.Label(self.secret_frame, text="Tajná kombinace:", font=("Arial", 9, "bold"), bg="#fcfcfc").pack(side=tk.LEFT, padx=5)

        # --- Input Panel ---
        self.input_frame = tk.Frame(self.game_frame, bg="#ffffff", bd=1, relief=tk.RIDGE, padx=10, pady=10)
        self.input_frame.pack(side=tk.TOP, fill=tk.X, pady=5, padx=10)

        # --- Board Frame (Scrollable) ---
        self.board_frame = tk.Frame(self.game_frame, bg="#fcfcfc")
        self.board_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.drawBoard()
        
        if start_type == 'new' and self.role == 1:
            self.showInputPanel(role='evaluator')
        elif start_type == 'reconnect':
            pass

        threading.Thread(target=self.recvMessageThread, daemon=True).start()
        threading.Thread(target=self.reconnectMonitor, daemon=True).start()

    def send_bad_message(self):
        """Pošle záměrně vadnou zprávu serveru pro test jeho reakce."""
        try:
            msg = f"{self.GAME_PREFIX}:BAD_MESSAGE"
            sendMessage(self.socket, msg.encode())
            print("[TEST] Odeslána vadná zpráva:", msg)
            self.updateStatus("Vadná zpráva odeslána.", "#f58231")
        except Exception as e:
            print("[TEST] Nepodařilo se odeslat vadnou zprávu:", e)
            self.updateStatus("Chyba při odesílání vadné zprávy.", "#e6194b")

    # =========================================================================
    # Komunikace a stav serveru
    # =========================================================================

    def connect_to_server(self):
        try:
            print(f"[DEBUG] Připojuji se na {self.host}:{self.port} (typ: {type(self.host)}, {type(self.port)})")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"[DEBUG] Připojení úspěšné!")
            self.connected = True
            return True
        except Exception as e:
            print(f"[DEBUG] Chyba připojení: {type(e).__name__}: {e}")
            messagebox.showerror("Connection Error", f"Nepodařilo se připojit k serveru: {e}")
            self.socket = None
            self.connected = False
            return False

    def submit_login(self):
        if not self.connected:
            self.login_status_label.config(text="Stav: Odpojeno od serveru.", fg="red")
            return
        
        self.name = self.name_entry.get()
        role_str = self.role_entry.get()

        if not self.name or not role_str:
            self.login_status_label.config(text="Vyplň jméno i roli!", fg="red")
            return

        try:
            role_int = int(role_str)
            if role_int not in [0, 1]:
                raise ValueError
            self.role = role_int
        except ValueError:
            self.login_status_label.config(text="Role musí být 0 (Tipující) nebo 1 (Hodnotitel)!", fg="red")
            return
            
        threading.Thread(target=self.send_and_receive_login, daemon=True).start()

    def send_and_receive_login(self):
        try:
            STATE_PREFIX = "START_LOGIN"
            msg = f"{self.GAME_PREFIX}:{STATE_PREFIX}:{self.name}:{self.role}"
            sendMessage(self.socket, msg.encode())

            self.update_status_safely(self.login_status_label, "Čekám na odpověď od serveru…", "#4363d8")
            
            data = recvMessage(self.socket)
            if not data:
                self.connected = False
                self.update_status_safely(self.login_status_label, "❌ Server zavřel spojení.", "red")
                return

            data_str = data.decode()

            if self.evaluate_message(data_str, "LOGIN_SUCCESS", 4):
                self.update_status_safely(self.login_status_label, "✅ Přihlášení úspěšné!", "#3cb44b")
                self.master.after(500, self.show_lobby)
            else:
                self.connected = False
                self.update_status_safely(self.login_status_label, "❌ Přihlášení selhalo nebo server neodpovídá.", "#e6194b")
                return
        except Exception as e:
            self.connected = False
            self.update_status_safely(self.login_status_label, f"⚠️ Chyba při komunikaci: {e}", "#e6194b")

    def handleReconnect(self, name, role):
        if not self.connected:
            self.login_status_label.config(text="Stav: Odpojeno. Nelze reconnect.", fg="#e6194b")
            return
        
        self.name = name
        role_str = str(role)

        if not self.name or not role_str:
            self.login_status_label.config(text="Vyplň jméno i roli!", fg="#e6194b")
            return
        
        try:
            role_int = int(role_str)
            if role_int not in [0, 1]:
                raise ValueError
            self.role = role_int
        except ValueError:
            self.login_status_label.config(text="Role musí být 0 nebo 1!", fg="#e6194b")
            return
            
        threading.Thread(target=self.send_and_receive_reconnect, daemon=True).start()

    def send_and_receive_reconnect(self):
        try:
            RECONNECT_PREFIX = "RECONNECT_REQUEST"
            msg = f"{self.GAME_PREFIX}:{RECONNECT_PREFIX}:{self.name}:{self.role}"
            sendMessage(self.socket, msg.encode())

            self.update_status_safely(self.login_status_label, "Čekám na odpověď od serveru (Reconnect)…", "#f58231")
            data_bytes = recvMessage(self.socket)
            
            if not data_bytes:
                self.connected = False
                self.update_status_safely(self.login_status_label, "❌ Server zavřel spojení.", "#e6194b")
                return
            
            data = data_bytes.decode()
            
            if data and "RECONNECT_CONFIRM" in data:
                self.reconnectData = data
                # DŮLEŽITÉ: Resetneme isRunning aby se stará vlákna zastavila
                self.isRunning = False
                time.sleep(0.2)  # Počkej aby se vlákna zastavila
                self.master.after(0, self.continueGame)
            elif data and "RECONNECT_FAIL" in data:
                self.update_status_safely(self.login_status_label, "❌ Obnovení připojení selhalo (hra neexistuje).", "#e6194b")
            else:
                self.connected = False
                self.update_status_safely(self.login_status_label, "❌ Obnovení připojení selhalo.", "#e6194b")
        
        except Exception as e:
            self.connected = False
            self.update_status_safely(self.login_status_label, f"⚠️ Chyba reconnectu: {e}", "#e6194b")

    def continueGame(self):
        """Inicializuje GUI a obnovuje herní stav po reconnectu."""
        print(f"[{self.name}] Continuing game with reconnect data.")
        self.isRunning = True
        self.isPaused = False
        
        game_state = self.parseAndAttachReconnectData(self.reconnectData)
        
        self.show_game(start_type='reconnect') 
        self.drawBoard() 

        if game_state == 0 and self.role == 1:
            self.showInputPanel(role='evaluator')
            self.updateStatus("Čekáš na tip protihráče.", color="#4363d8")
        elif game_state == 0 and self.role == 0:
            self.updateStatus("Čekáš na tajnou kombinaci", color="#4363d8")
        elif game_state == 1 and self.role == 1:
            self.updateStatus("Tajná kombinace odeslána. Čekám na tip protihráče.", color="#4363d8")
        elif game_state == 1 and self.role == 0:
            self.showInputPanel(role='guesser')
            self.updateStatus("Můžeš hádat!", color="#3cb44b")
        elif game_state == 2 and self.role == 0:
            self.updateStatus("Tip odeslán. Čekám na hodnocení...", "#4363d8")
            self.hideInputPanel(show_status=True, status_text="Tip odeslán. Čekám na hodnocení...", color="#4363d8")
        elif game_state == 2 and self.role == 1:
            last_guess = self.rounds[self.currentRoundNumber].guesses[-1]
            guess_str = ''.join(str(x) for x in last_guess) if isinstance(last_guess, list) else last_guess
            
            self.showEvaluationPanel(guess_str)
            self.updateStatus("Protihráč tipoval! Ohodnoť jeho tip.", "#3cb44b")

    # =========================================================================
    # Lobby logika
    # =========================================================================

    def choose_room(self):
        """Pošle REQUEST_ROOMS a zobrazí seznam místností."""
        try:
            ROOM_REQUEST_PREFIX = "REQUEST_ROOMS"
            msg = f"{self.GAME_PREFIX}:{ROOM_REQUEST_PREFIX}:{self.name}:{self.role}"
            sendMessage(self.socket, msg.encode())

            rooms_bytes = recvMessage(self.socket)
            if not rooms_bytes:
                self.updateStatus("❌ Server neodpovídá.", "#e6194b")
                self.master.after(1000, self.on_close)
                return

            rooms_str = rooms_bytes.decode()

            if not self.evaluate_message(rooms_str, "ROOM_LIST", -1):
                self.updateStatus("Chybná odpověď od serveru.", "#e6194b")
                return

            raw_parts = rooms_str.split(":")
            rooms_list = [p for p in raw_parts[2:] if p]
            
            self._display_rooms(rooms_list)

        except Exception as e:
            self.updateStatus(f"⚠️ Chyba v lobby komunikaci: {e}", "#e6194b")
            self.master.after(1000, self.on_close)

    def _display_rooms(self, rooms_list):
        """Vykreslí tlačítka místností do scrollable rámce v lobby."""
        self.master.after(0, lambda: self._clear_room_display())
        
        if not rooms_list:
            self.updateStatus("Žádné volné místnosti nejsou dostupné.", "#e6194b")
            return
            
        self.updateStatus("Vyberte si volnou místnost pro hru:", "#4363d8")
        
        # === SCROLL FRAME ===
        frame_container = tk.Frame(self.room_list_frame, bg="#ffffff")
        frame_container.pack(fill="both", expand=True, padx=5, pady=5)

        canvas = tk.Canvas(frame_container, highlightthickness=0, bg="#ffffff")
        # ttk scrollbar
        scrollbar = ttk.Scrollbar(frame_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#ffffff")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.master.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))

        # === TLAČÍTKA PRO MÍSTNOSTI (ttk.Button) ===
        for room_id in rooms_list:
            btn = ttk.Button(
                scrollable_frame,
                text=f"Místnost {room_id}",
                command=lambda rid=room_id: threading.Thread(target=self.join_room, args=(rid,), daemon=True).start(),
                width=30
            )
            btn.pack(pady=5, padx=10, ipady=5)
            
    def _clear_room_display(self):
        """Vyčistí scroll frame."""
        for widget in self.room_list_frame.winfo_children():
            widget.destroy()

    def join_room(self, room_id):
        try:
            JOIN_PREFIX = "JOIN_ROOM"
            join_msg = f"{self.GAME_PREFIX}:{JOIN_PREFIX}:{self.name}:{self.role}:{room_id}"
            sendMessage(self.socket, join_msg.encode())

            self.updateStatus(f"Čekám na potvrzení připojení k místnosti {room_id}...", "#4363d8")

            data = recvMessage(self.socket)
            if not data:
                self.updateStatus("❌ Server neodpovídá.", "#e6194b")
                self.master.after(1000, self.on_close)
                return

            data_str = data.decode()

            if "JOIN_SUCCESS" in data_str:
                self.updateStatus(f"✅ Připojen k místnosti {room_id}, čekáš na soupeře...", "#3cb44b")
                threading.Thread(target=self.wait_for_game_start, daemon=True).start()

            elif "JOIN_FAIL" in data_str:
                self.updateStatus(f"⚠️ Místnost {room_id} je obsazena nebo je zde uživatel stejné role. Načítám znovu...", "#f58231")
                self.master.after(1000, lambda: threading.Thread(target=self.choose_room, daemon=True).start())
            else:
                self.updateStatus("❌ Neočekávaná odpověď od serveru. Načítám znovu...", "#e6194b")
                self.master.after(1500, lambda: threading.Thread(target=self.choose_room, daemon=True).start())

        except Exception as e:
            self.updateStatus(f"⚠️ Nepodařilo se připojit: {e}", "#e6194b")
            self.master.after(1500, lambda: threading.Thread(target=self.choose_room, daemon=True).start())

    def wait_for_game_start(self):
        try:
            data = recvMessage(self.socket)
            if not data:
                self.updateStatus("❌ Server neodpovídá.", "#e6194b")
                self.master.after(1000, self.on_close)
                return
            data_str = data.decode()
            parts = data_str.split(":")
            # GAME_START může přijít buď jako LK:GAME_START nebo LK:GAME_START:<name>
            if len(parts) >= 3:
                self.other_player_name = parts[2]

            if self.evaluate_message(data_str, "GAME_START", -1):
                message = f"{self.GAME_PREFIX}:READY_GAME_START:{self.name}:{self.role}"
                sendMessage(self.socket, message.encode())
                self.updateStatus("✅ Hra začíná!", "#3cb44b")
                self.master.after(500, self.show_game)
            else:
                self.updateStatus("❌ Neočekávaná zpráva od serveru.", "#e6194b")
                self.master.after(1000, self.on_close)
        except Exception as e:
            self.updateStatus(f"⚠️ Chyba při čekání na start hry: {e}", "#e6194b")
            self.master.after(1000, self.on_close)

    # =========================================================================
    # Herní logika a UI (integrováno z GameSecond.py)
    # =========================================================================

    def buildPresenceBar(self, parent_frame):
        """Vykreslí indikátory online/offline pro mě i protihráče."""
        self.presence_frame = tk.Frame(parent_frame, bg="#ffffff")
        self.presence_frame.pack(pady=2, fill=tk.X)

        # Já
        me_frame = tk.Frame(self.presence_frame, bg="#ffffff")
        me_frame.pack(side=tk.LEFT, padx=15)
        self.me_status_canvas = tk.Canvas(me_frame, width=16, height=16, highlightthickness=0, bd=0, bg="#ffffff")
        self.me_status_canvas.pack(side=tk.LEFT, padx=4)
        self.me_status_label = tk.Label(me_frame, text=f"{self.name}", bg="#ffffff")
        self.me_status_label.pack(side=tk.LEFT)

        # Protihráč
        opp_frame = tk.Frame(self.presence_frame, bg="#ffffff")
        opp_frame.pack(side=tk.LEFT, padx=15)
        self.opponent_status_canvas = tk.Canvas(opp_frame, width=16, height=16, highlightthickness=0, bd=0, bg="#ffffff")
        self.opponent_status_canvas.pack(side=tk.LEFT, padx=4)
        self.opponent_status_label = tk.Label(opp_frame, text=f"{self.other_player_name if self.other_player_name else ''}", bg="#ffffff")
        self.opponent_status_label.pack(side=tk.LEFT)

        self.updatePresenceUI()

    def updatePresenceUI(self, opponent_name=None):
        """Obnoví barvy koleček podle online/offline stavů (thread-safe)."""
        if opponent_name:
            self.opponent_name = opponent_name
        if not hasattr(self, 'master') or not self.master.winfo_exists():
            return

        def _draw():
            def paint(canvas, status):
                if not canvas or not canvas.winfo_exists():
                    return
                canvas.delete("all")
                col = "#3cb44b" if status else "#d9534f" 
                canvas.create_oval(2, 2, 14, 14, fill=col, outline=col)

            if self.me_status_label:
                self.me_status_label.config(text=f"{self.name}")
            if self.opponent_status_label:
                self.opponent_status_label.config(text=f"{self.other_player_name if self.other_player_name else ''}")

            paint(self.me_status_canvas, self.me_online)
            paint(self.opponent_status_canvas, self.opponent_online)

        try:
            self.master.after(0, _draw)
        except Exception:
            pass

    def parseAndAttachReconnectData(self, data):
        """Parsuje data po reconnectu a obnovuje herní stav."""
        try:
            parts = data.split(":")
            if len(parts) < 4 or parts[1] != "RECONNECT_CONFIRM":
                return 0 
            
            current_round_num = int(parts[2])
            game_state = int(parts[-1]) if parts[-1].isdigit() else 0

            # Pokud poslední položka není číslo stavu, ale jméno protihráče, získej jej z konce
            if not parts[-1].isdigit() and len(parts) >= 5:
                self.other_player_name = parts[-1]
                # Stav hry by pak měl být v předposlední položce
                game_state = int(parts[-2]) if parts[-2].isdigit() else 0
            
            self._initialize_rounds() 
            
            # Očekáváme, že poslední prvek je buď stav, nebo jméno; předposlední pak stav
            round_data_parts = parts[3:-2] if len(parts) > 5 else (parts[3:-1] if len(parts) > 4 else [])
            
            for i, round_str in enumerate(round_data_parts):
                if len(round_str) < 4: 
                    continue
                
                guesses_str = round_str[:-2]
                try:
                    blacks = int(round_str[-2])
                    whites = int(round_str[-1])
                except (ValueError, IndexError):
                    continue
                
                if i < len(self.rounds):
                    round_obj = self.rounds[i]
                else:
                    round_obj = RoundInfo(i, self.num_pegs)
                    self.rounds.append(round_obj)
                
                guesses_list = [int(ch) for ch in guesses_str if ch.isdigit()][:self.num_pegs]
                
                round_obj.guesses = [guesses_list]
                round_obj.evaluations = [(blacks, whites)]
            
            self.currentRoundNumber = current_round_num
            
        except Exception as e:
            print(f"Chyba při parsování reconnect dat: {e}")
        
        return game_state

    def showInputPanel(self, role):
        """Zobrazí unifikovaný panel pro výběr barev (Evaluator) nebo tipování (Guesser)."""
        
        for widget in self.input_frame.winfo_children():
            widget.destroy()
            
        self._input_panel_initialized = False
        self.is_evaluator_mode = (role == 'evaluator')
        self.current_palette = self.palette
        self.input_values = [6] * self.num_pegs
        self.input_slot_ids = []
        self.input_sent = False

        try:
            title_text = "Vyber tajnou kombinaci:" if self.is_evaluator_mode else f"Kolo {self.currentRoundNumber+1}: Hádej 4 barvy:"
            tk.Label(self.input_frame, text=title_text, font=("Helvetica", 11, "bold"), bg="#ffffff").pack(pady=4)

            input_ctrl_frame = tk.Frame(self.input_frame, bg="#ffffff")
            input_ctrl_frame.pack(pady=5)
            
            self.input_canvas = tk.Canvas(input_ctrl_frame, width=300, height=50, bg="#ffffff", highlightthickness=0)
            self.input_canvas.pack(side=tk.LEFT, padx=10)

            margin_x = 30
            spacing = 60
            cy = 25
            r = 14 

            for i in range(self.num_pegs):
                cx = margin_x + i * spacing
                oid = self.input_canvas.create_oval(
                    cx - r, cy - r, cx + r, cy + r,
                    fill="#ffffff", outline="#333333", width=2
                )
                self.input_slot_ids.append(oid)
                self.input_canvas.tag_bind(oid, "<Button-1>", lambda e, idx=i: self._on_input_slot_click(idx))

            ctrl = tk.Frame(input_ctrl_frame, bg="#ffffff")
            ctrl.pack(side=tk.LEFT, padx=10)

            # Tlačítka s ttk
            self.input_submit_btn = ttk.Button(
                ctrl, 
                text="Odeslat", 
                command=self._submit_input, 
                state=tk.DISABLED,
                style='Accent.TButton'
            )
            self.input_submit_btn.pack(pady=3)

            self.input_reset_btn = ttk.Button(ctrl, text="Vymazat", command=self._reset_input)
            self.input_reset_btn.pack(pady=3)

            self._input_panel_initialized = True
            self._update_input_submit_enabled()

        except Exception as e:
            print(f"showInputPanel UI error: {e}")
            self._input_panel_initialized = False

    def _on_input_slot_click(self, slot_idx):
        """Cykluje barvy pro daný slot."""
        try:
            cur = self.input_values[slot_idx]
            num_colors = len(self.current_palette)
            
            if cur == 6:
                new = 0 
            elif cur < num_colors - 1:
                new = cur + 1 
            else:
                new = 6
                
            self.input_values[slot_idx] = new
            
            oid = self.input_slot_ids[slot_idx]
            
            if new == 6:
                fill_color = "#ffffff"
                outline = "#333333"
            else:
                fill_color = self.current_palette[new]
                outline = "#7a7a7a"
            
            self.input_canvas.itemconfig(oid, fill=fill_color, outline=outline)
            self._update_input_submit_enabled()
        except Exception as e:
            print(f"_on_input_slot_click error: {e}")

    def _update_input_submit_enabled(self):
        """Povolí tlačítko, pokud jsou vyplněny všechny sloty (ne 6)."""
        try:
            if getattr(self, 'input_sent', False):
                self.input_submit_btn.config(state=tk.DISABLED)
                return
            all_set = all((v is not None and int(v) != 6) for v in self.input_values)
            if hasattr(self, 'input_submit_btn'):
                self.input_submit_btn.config(state=(tk.NORMAL if all_set else tk.DISABLED))
        except Exception:
            pass

    def _reset_input(self):
        """Vymaže všechny sloty."""
        try:
            self.input_values = [6] * self.num_pegs
            for oid in self.input_slot_ids:
                self.input_canvas.itemconfig(oid, fill="#ffffff", outline="#333333")
            self._update_input_submit_enabled()
        except Exception:
            pass

    def _submit_input(self):
        """Sestaví zprávu a odešle ji na server."""
        try:
            if getattr(self, 'input_sent', False) or any(int(v) == 6 for v in self.input_values):
                return

            s = ''.join(str(v) for v in self.input_values)
            
            if self.is_evaluator_mode:
                ok = self.send_choice(s)
                action = "kombinace"
            else:
                ok = self.send_guess(s)
                action = "tipu"
            
            if ok:
                self.input_sent = True
                self.updateStatus(f"{action.capitalize()} odeslán", "#3cb44b")
                
                try:
                    self.input_submit_btn.config(state=tk.DISABLED)
                    self.input_reset_btn.config(state=tk.DISABLED)
                    if not self.is_evaluator_mode:
                        self.hideInputPanel(show_status=True, status_text="Tip odeslán. Čekám na hodnocení...", color="#4363d8")
                    else:
                        self.hideInputPanel(show_status=True, status_text="Tajná kombinace odeslána. Čekám na tip protihráče.", color="#4363d8")
                    
                    self.drawBoard() 
                except Exception:
                    pass
            else:
                self.updateStatus(f"Chyba: nepodařilo se odeslat {action}", "#e6194b")
        except Exception as e:
            print(f"_submit_input error: {e}")

    def hideInputPanel(self, show_status=False, status_text="", color=""):
        """Skryje panel pro vstup a volitelně zobrazí status (pro Guessera/Evaluatora)."""
        try:
            if hasattr(self, 'input_frame') and self.input_frame:
                for widget in self.input_frame.winfo_children():
                    widget.destroy()
                if show_status:
                    tk.Label(self.input_frame, text=status_text, fg=color, font=("Helvetica", 12), bg="#ffffff").pack(pady=20)
                
                self._input_panel_initialized = False
        except Exception:
            pass

    def showEvaluationPanel(self, guess_str):
        """UI pro Hodnotitele (role 1): Vybrat počet černých a bílých kolíků."""
        
        self.hideInputPanel() 

        eval_frame = tk.Frame(self.input_frame, bd=1, relief=tk.RIDGE, bg="#ffffff")
        eval_frame.pack(pady=10, fill=tk.X, padx=10)

        tk.Label(eval_frame, text="Ohodnoť tip:", font=("Helvetica", 11, "bold"), bg="#ffffff").pack(pady=5)

        blacks_var = tk.IntVar(value=0)
        whites_var = tk.IntVar(value=0)

        def create_stepper(parent, label_text, var, max_val):
            frame = tk.Frame(parent, bg="#ffffff")
            frame.pack(side=tk.LEFT, padx=15)
            tk.Label(frame, text=label_text, bg="#ffffff").pack()
            
            def change_val(delta):
                new_val = var.get() + delta
                if 0 <= new_val <= max_val and (new_val + whites_var.get() <= 4 if var == blacks_var else new_val + blacks_var.get() <= 4):
                    var.set(new_val)
                    self._update_eval_submit_enabled(blacks_var.get(), whites_var.get())

            # Tlačítka ttk
            ttk.Button(frame, text="+", command=lambda: change_val(1), width=3).pack()
            tk.Label(frame, textvariable=var, font=("Helvetica", 12, "bold"), bg="#ffffff").pack()
            ttk.Button(frame, text="-", command=lambda: change_val(-1), width=3).pack()
            return var

        stepper_frame = tk.Frame(eval_frame, bg="#ffffff")
        stepper_frame.pack(pady=10, anchor=tk.CENTER)
        create_stepper(stepper_frame, "Černé (Přesné)", blacks_var, 4)
        create_stepper(stepper_frame, "Bílé (Barva)", whites_var, 4)

        # Tlačítko ttk
        self.eval_submit_btn = ttk.Button(
            eval_frame, 
            text="Odeslat hodnocení", 
            command=lambda: self._submit_evaluation(blacks_var.get(), whites_var.get()), 
            state=tk.DISABLED
        )
        self.eval_submit_btn.pack(pady=10, ipady=5)

        self._update_eval_submit_enabled(0, 0)
    
    def _update_eval_submit_enabled(self, blacks, whites):
        """Povolí tlačítko pro hodnocení, pokud je součet menší nebo roven 4."""
        try:
            if hasattr(self, 'eval_submit_btn') and blacks + whites <= 4:
                 self.eval_submit_btn.config(state=tk.NORMAL)
            elif hasattr(self, 'eval_submit_btn'):
                 self.eval_submit_btn.config(state=tk.DISABLED)
        except Exception:
            pass

    def _submit_evaluation(self, blacks, whites):
        """Odešle hodnocení serveru."""
        if blacks + whites > 4:
            messagebox.showerror("Chyba", "Součet černých a bílých kolíků nesmí přesáhnout 4.")
            return

        msg = f"{self.GAME_PREFIX}:EVALUATION:{blacks}:{whites}"
        try:
            self.send_evaluation(msg)
            
            self.addEvaluation((blacks, whites)) 
            
            if hasattr(self, 'input_frame') and self.input_frame:
                self.hideInputPanel(show_status=True, status_text="Hodnocení odesláno. Čekám na další tip od protihráče.", color="#4363d8")
            
            self.updateStatus("Hodnocení odesláno. Čekám na další tip...", "#3cb44b")
            
        except Exception as e:
            print(f"Chyba při odesílání hodnocení: {e}")
            self.updateStatus("Chyba při odesílání hodnocení", "#e6194b")

    def send_guess(self, colors_str):
        """Send GUESSING_COLORS message to server."""
        try:
            msg = f"{self.GAME_PREFIX}:GUESSING_COLORS:{colors_str}"
            sendMessage(self.socket, msg.encode())
            return True
        except Exception:
            return False

    def send_choice(self, colors_str):
        """Send CHOOSING_COLORS message to server."""
        try:
            msg = f"{self.GAME_PREFIX}:CHOOSING_COLORS:{colors_str}"
            sendMessage(self.socket, msg.encode())
            return True
        except Exception:
            return False

    def send_evaluation(self, msg):
        """Send EVALUATION message to server."""
        try:
            sendMessage(self.socket, msg.encode())
            return True
        except Exception:
            return False

    def addGuess(self, guess_data):
        """Přidá tip do aktuálního kola a obnoví desku."""
        if 0 <= self.currentRoundNumber < len(self.rounds):
            if isinstance(guess_data, list):
                guesses_list = guess_data
            elif isinstance(guess_data, str):
                 guesses_list = [int(ch) for ch in guess_data if ch.isdigit()][:self.num_pegs]
            else:
                 return

            self.rounds[self.currentRoundNumber].guesses = [guesses_list]
        
        self.master.after(0, self.drawBoard)

    def addEvaluation(self, evaluation_tuple):
        """Přidá hodnocení do aktuálního kola, obnoví desku."""
        if 0 <= self.currentRoundNumber < len(self.rounds):
            self.rounds[self.currentRoundNumber].evaluations.append(evaluation_tuple)
        
        self.master.after(0, self.drawBoard) 

    def nextRound(self):
        """Přesune hru do dalšího kola a aktualizuje UI."""
        if self.currentRoundNumber < 9:
            self.currentRoundNumber += 1
        
        self.master.after(0, self.drawBoard)

    def drawBoard(self):
        """Vykreslí hrací desku a tajnou kombinaci (pro Evaluatora)."""
        
        if not hasattr(self, 'game_frame') or not self.game_frame.winfo_exists(): return
        
        self._draw_secret_combination()

        if hasattr(self, 'e_board_frame') and self.e_board_frame:
            try:
                if self.e_board_frame.winfo_exists():
                    for w in self.e_board_frame.winfo_children(): w.destroy()
                else:
                    self.e_board_frame = tk.Frame(self.board_frame, bg="#fcfcfc")
                    self.e_board_frame.pack(padx=10, pady=8, fill=tk.BOTH, expand=True)
            except tk.TclError:
                self.e_board_frame = tk.Frame(self.board_frame, bg="#fcfcfc")
                self.e_board_frame.pack(padx=10, pady=8, fill=tk.BOTH, expand=True)
        else:
             self.e_board_frame = tk.Frame(self.board_frame, bg="#fcfcfc")
             self.e_board_frame.pack(padx=10, pady=8, fill=tk.BOTH, expand=True)

        container = tk.Frame(self.e_board_frame, bg="#ffffff", bd=1, relief=tk.RIDGE)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, bg="#ffffff", highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview) # ttk scrollbar
        
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.configure(yscrollcommand=vscroll.set)

        inner_frame = tk.Frame(canvas, bg="#ffffff")
        canvas.create_window((0, 0), window=inner_frame, anchor='nw')
        inner_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        self._draw_board_rows(inner_frame)

    def _draw_secret_combination(self):
        """Vykreslí tajnou kombinaci v horní části okna (pouze pro Hodnotitele)."""
        if self.role != 1 or not hasattr(self, 'secret_canvas') or not self.input_values:
            return
        
        self.secret_canvas.delete("all")
        r = 12
        spacing = 50
        margin_x = 10
        cy = 20
        
        palette = self.palette
        
        for i, color_idx in enumerate(self.input_values):
            cx = margin_x + i * spacing
            
            if color_idx == 6:
                fill_col = "#ffffff"
                outline = "#cccccc"
            elif 0 <= color_idx < len(palette):
                fill_col = palette[color_idx]
                outline = "#7a7a7a"
            else:
                fill_col = "#f0f0f0"
                outline = "#cccccc"
            
            self.secret_canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill=fill_col, outline=outline, width=2
            )

    def _draw_board_rows(self, inner_frame):
        """Vykresluje jednotlivé řádky desky do inner_frame."""
        
        palette = self.palette
        row_h = 40
        peg_r = 11
        
        def parse_guess(rnd):
            if rnd.guesses and isinstance(rnd.guesses[-1], list):
                return rnd.guesses[-1][:self.num_pegs]
            return [6] * self.num_pegs

        def parse_eval(rnd):
            if rnd.evaluations:
                ev = rnd.evaluations[-1]
                if isinstance(ev, tuple) and len(ev) >= 2:
                    return (int(ev[0]), int(ev[1]))
            return (0, 0)

        for idx, rnd in enumerate(self.rounds):
            row = tk.Frame(inner_frame, height=row_h)
            row.pack(fill=tk.X, padx=5, pady=2)
            
            bg_color = "#ffffff"
            if idx == self.currentRoundNumber:
                bg_color = "#fffac8"
            row.config(bg=bg_color)

            # 1. Číslo kola
            tk.Label(row, text=f"{idx+1}", font=("Arial", 10, "bold" if idx == self.currentRoundNumber else "normal"), 
                     bg=bg_color, width=4).pack(side=tk.LEFT, padx=5)

            # 2. Tip (4 velké kolíky)
            guess_frame = tk.Frame(row, bg=bg_color)
            guess_frame.pack(side=tk.LEFT, padx=10)
            
            guess_vec = parse_guess(rnd)
            
            for val in guess_vec:
                fill_col = palette[val] if 0 <= val < len(palette) else "#ffffff"
                outline_col = "#7a7a7a" if 0 <= val < len(palette) else "#cccccc"
                
                canvas = tk.Canvas(guess_frame, width=peg_r*2, height=peg_r*2, bg=bg_color, highlightthickness=0)
                canvas.pack(side=tk.LEFT, padx=3)
                canvas.create_oval(1, 1, peg_r*2-1, peg_r*2-1, fill=fill_col, outline=outline_col, width=2)

            # 3. Hodnocení (4 malé kolíky)
            eval_frame = tk.Frame(row, bg=bg_color)
            eval_frame.pack(side=tk.LEFT, padx=10) # Dříve bylo side=tk.RIGHT
            
            blacks, whites = parse_eval(rnd)
            k = 0
            
            for i in range(4):
                if k < blacks:
                    color = "#FF6C1D"
                    k += 1
                elif k < blacks + whites:
                    color = "#969696" 
                    k += 1
                else:
                    color = "#f0f0f0"
                
                canvas = tk.Canvas(eval_frame, width=12, height=12, bg=bg_color, highlightthickness=0)
                canvas.grid(row=i//2, column=i%2)
                canvas.create_oval(1, 1, 11, 11, fill=color, outline="#cccccc", width=1)
                
        inner_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

    # =========================================================================
    # Různé a pomocné funkce (Client/Game)
    # =========================================================================

    def updateStatus(self, text, color):
        """Aktualizace statusu v GUI (thread-safe)"""
        self.update_status_safely(self.status_label, text, color)
        
    def update_status_safely(self, label, text, color):
        """Aktualizace libovolného labelu (thread-safe)"""
        try:
            if hasattr(self, 'master') and self.master.winfo_exists() and label:
                def _upd():
                    try:
                        label.config(text=text, fg=color)
                    except Exception:
                        pass
                self.master.after(0, _upd)
        except Exception:
            pass
            
    def evaluate_message(self, message, STATE_PREFIX, PARTS_COUNT):
        """Zkontroluje formát a prefix zprávy."""
        parts = message.split(":")
        
        if parts[0] != self.GAME_PREFIX or parts[1] != STATE_PREFIX:
            return False
            
        if PARTS_COUNT != -1 and len(parts) != PARTS_COUNT:
            return False
            
        return True

    def on_close(self):
        """Zavře socket a ukončí aplikaci."""
        self.isRunning = False
        self.connected = False
        
        if self.socket:
            try:
                pass
            except Exception:
                pass
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except Exception:
                pass
            finally:
                self.socket = None

        try:
            self.master.destroy()
        except Exception:
            pass

        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

    # =========================================================================
    # Game - Komunikační Vlákna
    # =========================================================================

    def recvMessageThread(self):
        """Hlavní smyčka pro příjem zpráv od serveru"""
        while self.isRunning:
            try:
                data = recvMessage(self.socket)
                if not data:
                    self.master.after(0, self.handleDisconnect)
                    continue
                    
                message = data.decode()
                self.handleMessage(message)
            except Exception:
                self.master.after(0, self.handleDisconnect)
                time.sleep(0.1)

    def handleMessage(self, message):
        """Zpracování příchozích zpráv."""
        parts = message.split(":")
        
        if len(parts) < 2 or parts[0] != self.GAME_PREFIX:
            return
        
        msg_type = parts[1]
        
        if msg_type == "PING":
            pong_msg = f"{self.GAME_PREFIX}:PONG:{self.name}:{self.role}"
            try:
                sendMessage(self.socket, pong_msg.encode())
            except Exception:
                self.master.after(0, self.handleDisconnect)

        
        elif msg_type == "WIN_GAME":
            if(int(parts[2]) == self.role):
                self.updateStatus("Gratuluji! Vyhrál jsi hru!", "#ffe119") # Zlatá
            else:
                self.updateStatus("Bohužel, prohrál jsi.", "#e6194b")
            try:
                sendMessage(self.socket, f"{self.GAME_PREFIX}:WIN_GAME_ACK".encode())
            except Exception:
                pass
            self.isRunning = False
            self.reconnecting = False
            self.master.after(2000, self.returnToLobby)

        elif msg_type == "PERMANENT_DISCONNECT":
            opponent_name = parts[2] if len(parts) > 2 else self.opponent_name
            self.opponent_online = 0
            self.updatePresenceUI(opponent_name)
            respond_message = f"{self.GAME_PREFIX}:PERMANENT_DISCONNECT_CONFIRM:{self.name}:{self.role}"
            try:
                sendMessage(self.socket, respond_message.encode())
            except Exception:
                pass 
            self.isRunning = False
            self.master.after(2000, self.returnToLobby)

        elif msg_type == "TEMPORARY_DISCONNECT":
            opponent_name = parts[2] if len(parts) > 2 else self.opponent_name
            self.opponent_online = 0
            self.updatePresenceUI(opponent_name)
            respond_message = f"{self.GAME_PREFIX}:TEMPORARY_DISCONNECT_CONFIRM:{self.name}:{self.role}"
            try:
                sendMessage(self.socket, respond_message.encode())
            except Exception:
                pass

        elif msg_type == "RECONNECT_OTHER_PLAYER":
            opponent_name = parts[2] if len(parts) > 2 else self.opponent_name
            self.opponent_online = 1
            self.updatePresenceUI(opponent_name)
            respond_message = f"{self.GAME_PREFIX}:RECONNECT_OTHER_PLAYER_ACK"

            try:
                sendMessage(self.socket, respond_message.encode())
            except Exception:
                pass


        elif msg_type == "CHOOSING_COLORS_CONFIRM":
            if self.role == 0:
                self.updateStatus("Protihráč vybral kombinaci. Můžeš hádat!", "#3cb44b")
                self.master.after(0, lambda: self.showInputPanel(role='guesser'))
        
        elif msg_type == "GUESSING_COLORS_ACK":
            if len(parts) > 2:
                guess_str = parts[2]
                
                if self.role == 1:
                    self.addGuess(guess_str)
                    self.updateStatus("Protihráč tipoval! Ohodnoť jeho tip.", "#3cb44b")
                    self.master.after(0, lambda: self.showEvaluationPanel(guess_str))
                    
                elif self.role == 0:
                    self.addGuess(guess_str)
                    self.updateStatus("Tip odeslán. Čekám na hodnocení...", "#4363d8")
                    self.hideInputPanel(show_status=True, status_text="Tip odeslán. Čekám na hodnocení...", color="#4363d8")


        elif msg_type == "EVALUATION_ACK":
            if len(parts) > 3:
                try:
                    blacks = int(parts[2])
                    whites = int(parts[3])
                except ValueError:
                    return
                
                self.addEvaluation((blacks, whites)) 
                self.master.after(100, self.nextRound)
                    
                if self.role == 0:
                    self.updateStatus(f"Protihráč hodnotil. Hodnocení: {blacks} Černá, {whites} Bílá. Hádej znovu.", "#3cb44b")
                    self.master.after(200, lambda: self.showInputPanel(role='guesser'))
                        
                elif self.role == 1:
                    self.updateStatus("Hodnocení odesláno. Čekám na další tip...", "#4363d8")
                    self.hideInputPanel(show_status=True, status_text="Hodnocení odesláno. Čekám na další tip od protihráče.", color="#4363d8")

        elif msg_type == "GAME_OVER":
            self.updateStatus("Konec hry! " + parts[2] if len(parts) > 2 else "Hra skončila.", "#911eb4")
            self.isRunning = False
            self.master.after(5000, self.returnToLobby)


    def handleDisconnect(self):
        """Zpracování odpojení od serveru"""
        if not self.isRunning or not hasattr(self, 'master') or not self.master.winfo_exists():
            return
        if not self.reconnecting:
            self.reconnecting = True
            self.disconnected_time = time.time()
            self.me_online = 0
            self.updatePresenceUI()
            self.updateStatus("Odpojeno - pokus o reconnect...", "#e6194b")
    
    def reconnectMonitor(self):
        """Monitoruje stav připojení a pokouší se o reconnect"""
        while self.isRunning:
            if self.reconnecting:
                elapsed = time.time() - self.disconnected_time
                
                if elapsed > 7 and elapsed < 20:
                    self.updateStatus(f"Reconnecting... ({int(elapsed)}s)", "#f58231")
                    if self.attemptReconnect():
                        self.reconnecting = False
                        self.disconnected_time = None
                        self.me_online = 1
                        print("Reconnected successfully. Přes reconnectMonitor.")
                        self.updateStatus("Připojeno zpět - hra pokračuje", "#3cb44b")
                        self.updatePresenceUI()
                    else:
                        time.sleep(1)
                
                elif elapsed >= 20 and elapsed < 45:
                    self.updateStatus("Je třeba se znovu přihlásit (Reconnect v Login okně).", "#e6194b")
                    self.isRunning = False
                    self.master.after(0, self.show_login)
                    break
                
                elif elapsed >= 45:
                    self.updateStatus("Příliš dlouhé odpojení, hra končí.", "#e6194b")
                    self.isRunning = False
                    self.master.after(0, self.returnToLobby)
                    break
            
            time.sleep(0.5)
    
    def attemptReconnect(self):
        """Pokus o reconnect k serveru v Game fázi."""
        try:
            new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            new_socket.connect((self.host, self.port)) 
            
            reconnect_msg = f"{self.GAME_PREFIX}:RECONNECT_REQUEST:{self.name}:{self.role}"
            sendMessage(new_socket, reconnect_msg.encode())
            
            response = recvMessage(new_socket)
            if response:
                msg = response.decode()
                if "RECONNECT_CONFIRM" in msg:
                    try:
                        self.socket.close()
                    except:
                        pass
                    # DŮLEŽITÉ: Zastavit stará vlákna
                    self.isRunning = False
                    time.sleep(0.2)
                    self.socket = new_socket
                    self.reconnectData = msg
                    self.isRunning = True  # Vrátit zpět pro nová vlákna
                    self.master.after(0, self.continueGame)
                    return True
            
            new_socket.close()
            return False
            
        except Exception:
            return False

    def returnToLobby(self):
        """Zavře herní UI a vrátí hráče zpět do lobby (se stejným socketem)."""
        self.isRunning = False
        self.reconnecting = False
        self.currentRoundNumber = 0
        self._initialize_rounds()
        
        # Reset herních UI referencí
        self.e_board_frame = None
        self.input_values = None
        
        self.master.after(0, self.show_lobby)

# --- SPoušTěCÍ LOGIKA ---

def main():
    if len(sys.argv) < 2:
        print("Usage: python client2.py <port> [host]")
        print("       host default: 127.0.0.1")
        sys.exit(1)
        
    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Port musí být celé číslo.")
        sys.exit(1)
    
    host = sys.argv[2] if len(sys.argv) >= 3 else "127.0.0.1"
    
    root = tk.Tk()
    app = LogikApp(root, host, port)
    root.mainloop()

if __name__ == "__main__":
    main()