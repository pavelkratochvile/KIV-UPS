import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
from random import randint

# Předpokládáme dostupnost modulů SocketLib a LogikClient
from SocketLib import sendMessage, recvMessage
# Předpokládáme, že LogikClientInstance má metodu handleLobby
# from LogikClient import LogikClient 

class RoundInfo:
    """Datová struktura pro uchování tipů a hodnocení jednoho kola."""
    def __init__(self, roundNumber, num_pegs=4):
        self.roundNumber = roundNumber
        # 6 = bílá / bez barvy - default hodnota místo prázdného seznamu
        self.guesses = [6] * num_pegs
        self.evaluations = [] # List hodnocení (tuple/str)

class Game:
    """Implementace klienta Mastermind/Logik s GUI v Tkinteru."""
    def __init__(self, playerSocket, playerName=None, playerRole=None, LogikClientInstance=None):
        self.isRunning = False
        self.isPaused = False
        self.playerSocket = playerSocket
        self.playerName = playerName
        self.round = 0
        try:
            self.playerRole = int(playerRole) # 0 = Guesser, 1 = Evaluator
        except Exception:
            self.playerRole = playerRole
            
        self.GAME_PREFIX = "LK"
        self.reconnecting = False
        self.disconnected_time = None
        self.client = LogikClientInstance # Instance LogikClient pro návrat do lobby
        
        # Nastavení hry - MUSÍ být PŘED inicializací self.rounds
        self.palette = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4"] # 6 barev
        self.num_pegs = 4
        
        # Přítomnost hráčů (0 = offline, 1 = online)
        self.me_online = 1
        self.opponent_online = 1
        self.opponent_name = "Protihráč"
        
        # Herní stav
        self.currentRoundNumber = 0 
        self.rounds = []
        # Inicializuj 10 kol (0-9) - každé kolo má defaultně bílé/empty sloty (index 6)
        for i in range(10):
            self.rounds.append(RoundInfo(i, self.num_pegs))
        
        # UI stav a prvky
        self._input_panel_initialized = False
        self.game_window = None
        self.status_label = None
        self.input_frame = None
        self.e_board_canvas = None
        self.presence_frame = None
        self.me_status_canvas = None
        self.opponent_status_canvas = None
        self.me_status_label = None
        self.opponent_status_label = None

    def start(self):
        """Inicializuje GUI a spouští vlákna pro příjem zpráv a reconnect."""
        self.isRunning = True
        self.isPaused = False
        self.game_window = tk.Tk()
        self.game_window.geometry("500x700") 
        self.game_window.title(f"Hra - {self.playerName}")

        # --- Main layout frames ---
        self.top_frame = tk.Frame(self.game_window)
        self.top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        self.input_frame = tk.Frame(self.game_window)
        self.input_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        self.board_frame = tk.Frame(self.game_window)
        self.board_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # --------------------------
        
        self.status_label = tk.Label(self.top_frame, text="Hra běží", fg="green", font=("Arial", 14))
        self.status_label.pack(pady=10)
        
        role_text = "Hodnotitel (Vybírá barvy)" if self.playerRole == 1 else "Tipující (Hádá barvy)"
        self.info_label = tk.Label(self.top_frame, text=f"Hráč: {self.playerName} | Role: {role_text}")
        self.info_label.pack(pady=5)
        self.buildPresenceBar()
        
        self.drawBoard()

        # Pokud je hráč Evaluator (role==1), zobrazí panel pro volbu hned
        if isinstance(self.playerRole, int) and self.playerRole == 1:
            self.showInputPanel(role='evaluator')

        threading.Thread(target=self.recvMessageThread, daemon=True).start()
        threading.Thread(target=self.reconnectMonitor, daemon=True).start()
        
        self.game_window.mainloop()

    def continueGame(self, reconnectData):
        """Inicializuje GUI a spouští vlákna pro příjem zpráv a reconnect. Poté co se klient znovu připojil"""
        print(f"[{self.playerName}] Continuing game with reconnect data: {reconnectData}")
        self.isRunning = True
        self.isPaused = False
        
        # Parsuj a obnov herní data z reconnect zprávy
        game_state = self.parseAndAttachReconnectData(reconnectData)
        
        self.game_window = tk.Tk()
        self.game_window.geometry("500x700") 
        self.game_window.title(f"Hra - {self.playerName}")

        # --- Main layout frames ---
        self.top_frame = tk.Frame(self.game_window)
        self.top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        self.input_frame = tk.Frame(self.game_window)
        self.input_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        self.board_frame = tk.Frame(self.game_window)
        self.board_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # --------------------------
        
        self.status_label = tk.Label(self.top_frame, text="Hra běží", fg="green", font=("Arial", 14))
        self.status_label.pack(pady=10)
        
        role_text = "Hodnotitel (Vybírá barvy)" if self.playerRole == 1 else "Tipující (Hádá barvy)"
        self.info_label = tk.Label(self.top_frame, text=f"Hráč: {self.playerName} | Role: {role_text}")
        self.info_label.pack(pady=5)
        self.buildPresenceBar()

        if(game_state == 0 and self.playerRole == 1):
            self.showInputPanel(role='evaluator')
        elif(game_state == 0 and self.playerRole == 0):
            self.updateStatus("Čekáš na tajnou kombinaci", color="blue")
        elif(game_state == 1 and self.playerRole == 1):
            self.updateStatus("Hodnocení odesláno. Čekám na další tip...", "blue")
        elif(game_state == 1 and self.playerRole == 0):
            self.showInputPanel(role='guesser')
        elif(game_state == 2 and self.playerRole == 0):
            self.updateStatus("Tip odeslán. Čekám na hodnocení...", "blue")
        elif(game_state == 2 and self.playerRole == 1):
            print("Zobrazit panel pro hodnocení")
            self.showEvaluationPanel(self.currentRound.guesses[-1])
        
        # Obnoví desku s historií her
        self.drawBoard()
        
        threading.Thread(target=self.recvMessageThread, daemon=True).start()
        threading.Thread(target=self.reconnectMonitor, daemon=True).start()
        
        self.game_window.mainloop()

    def buildPresenceBar(self):
        """Vykreslí indikátory online/offline pro mě i protihráče."""
        if not hasattr(self, 'top_frame'):
            return
        if self.presence_frame and self.presence_frame.winfo_exists():
            return

        self.presence_frame = tk.Frame(self.top_frame)
        self.presence_frame.pack(pady=2, fill=tk.X)

        # Já
        me_frame = tk.Frame(self.presence_frame)
        me_frame.pack(side=tk.LEFT, padx=8)
        self.me_status_canvas = tk.Canvas(me_frame, width=16, height=16, highlightthickness=0, bd=0)
        self.me_status_canvas.pack(side=tk.LEFT, padx=4)
        self.me_status_label = tk.Label(me_frame, text=f"Já: {self.playerName}")
        self.me_status_label.pack(side=tk.LEFT)

        # Protihráč
        opp_frame = tk.Frame(self.presence_frame)
        opp_frame.pack(side=tk.LEFT, padx=12)
        self.opponent_status_canvas = tk.Canvas(opp_frame, width=16, height=16, highlightthickness=0, bd=0)
        self.opponent_status_canvas.pack(side=tk.LEFT, padx=4)
        self.opponent_status_label = tk.Label(opp_frame, text=f"Protihráč: {self.opponent_name}")
        self.opponent_status_label.pack(side=tk.LEFT)

        self.updatePresenceUI()

    def updatePresenceUI(self, opponent_name=None):
        """Obnoví barvy koleček podle online/offline stavů."""
        if opponent_name:
            self.opponent_name = opponent_name
        if not hasattr(self, 'game_window') or not self.game_window:
            return

        def _draw():
            def paint(canvas, status):
                if not canvas:
                    return
                canvas.delete("all")
                col = "#3cb44b" if status else "#d9534f"
                canvas.create_oval(2, 2, 14, 14, fill=col, outline=col)

            if self.me_status_label:
                self.me_status_label.config(text=f"Já: {self.playerName}")
            if self.opponent_status_label:
                self.opponent_status_label.config(text=f"Protihráč: {self.opponent_name}")

            paint(self.me_status_canvas, self.me_online)
            paint(self.opponent_status_canvas, self.opponent_online)

        try:
            self.game_window.after(0, _draw)
        except Exception:
            _draw()

    # =========================================================================
    # UI: INPUT A HODNOCENÍ
    # =========================================================================

    def printRounds(self):
        """Debug funkce pro výpis kol do konzole."""
        for round_info in self.rounds:
            print(f"Kolo {round_info.roundNumber}: Tipy={round_info.guesses}, Hodnocení={round_info.evaluations}")

    def parseAndAttachReconnectData(self, data):
        try:
            parts = data.split(":")
            if len(parts) < 4 or parts[1] != "RECONNECT_CONFIRM":
                print("Chybný formát RECONNECT_CONFIRM zprávy")
                return
            
            current_round_num = int(parts[2])
            game_state = int(parts[-1]) if parts[-1].isdigit() else 0
            
            # Zrekonstruuj kola z parts[3:-1] (vše mezi roundNumber a gameState)
            round_data_parts = parts[3:-1] if len(parts) > 4 else []
            
            for i, round_str in enumerate(round_data_parts):
                if len(round_str) < 4:  # Minimálně 4 barvy + 2 hodnocení
                    continue
                
                # Rozlož: guesses = vše mimo poslední 2 znaky, blacks = -2, whites = -1
                guesses_str = round_str[:-2]
                try:
                    blacks = int(round_str[-2])
                    whites = int(round_str[-1])
                except (ValueError, IndexError):
                    continue
                
                # Vlož do rounds
                if i < len(self.rounds):
                    round_obj = self.rounds[i]
                else:
                    round_obj = RoundInfo(i, self.num_pegs)
                    self.rounds.append(round_obj)
                
                # Parsuj guesses_str na seznam čísel
                guesses_list = [int(ch) for ch in guesses_str if ch.isdigit()]
                
                # Nastavíme guesses a evaluation
                round_obj.guesses = [guesses_list]  # Poslední tip v kole (seznam čísel)
                round_obj.evaluations = [(blacks, whites)]
            
            # Nastav aktuální kolo
            self.currentRoundNumber = current_round_num
            if current_round_num < len(self.rounds):
                self.currentRound = self.rounds[current_round_num]
            else:
                self.currentRound = RoundInfo(current_round_num, self.num_pegs)
                self.rounds.append(self.currentRound)

        except Exception as e:
            print(f"Chyba při parsování reconnect dat: {e}")
        
        return game_state

    def showInputPanel(self, role):
        """Zobrazí unifikovaný panel pro výběr barev (Evaluator) nebo tipování (Guesser)."""
        if self._input_panel_initialized:
            return

        if hasattr(self, 'input_frame') and self.input_frame:
            for widget in self.input_frame.winfo_children():
                widget.destroy()
        
        self.is_evaluator_mode = (role == 'evaluator')
        self.current_palette = self.palette
        # Výchozí vstupní hodnoty (6 = bílá / prázdné)
        self.input_values = [6] * self.num_pegs
        self.input_slot_ids = []
        self.input_sent = False

        try:
            title_text = "Vyber tajnou kombinaci (kliknutím cykluj barvy)" if self.is_evaluator_mode else "Hádej 4 barvy (kliknutím cykluj barvy)"
            tk.Label(self.input_frame, text=title_text, font=("Arial", 10, "bold")).pack(pady=4)

            self.input_canvas = tk.Canvas(self.input_frame, width=320, height=70, bg=self.game_window.cget('bg'), highlightthickness=0)
            self.input_canvas.pack()

            margin_x = 30
            spacing = 60
            cy = 35
            r = 14 

            for i in range(self.num_pegs):
                cx = margin_x + i * spacing
                # Výchozí barva je bílá (index 6 = prázdné)
                oid = self.input_canvas.create_oval(
                    cx - r, cy - r, cx + r, cy + r,
                    fill="#ffffff", outline="#333333", width=2
                )
                self.input_slot_ids.append(oid)
                self.input_canvas.tag_bind(oid, "<Button-1>", lambda e, idx=i: self._on_input_slot_click(idx))

            ctrl = tk.Frame(self.input_frame)
            ctrl.pack(pady=6)

            self.input_submit_btn = tk.Button(
                ctrl, 
                text="Odeslat výběr" if self.is_evaluator_mode else "Odeslat tip", 
                command=self._submit_input, 
                state=tk.DISABLED,
                bg="#4CAF50", fg="white", font=("Arial", 10, "bold")
            )
            self.input_submit_btn.pack(side=tk.LEFT, padx=10)

            self.input_reset_btn = tk.Button(ctrl, text="Vymazat", command=self._reset_input, bg="#f44336", fg="white")
            self.input_reset_btn.pack(side=tk.LEFT, padx=10)

            self._input_panel_initialized = True
            self._update_input_submit_enabled()

        except Exception as e:
            print(f"showInputPanel UI error: {e}")
            self._input_panel_initialized = False

    def _on_input_slot_click(self, slot_idx):
        """Cykluje barvy pro daný slot."""
        try:
            cur = self.input_values[slot_idx]
            # Pro Evaluatora: cykluj jen přes paletu (0..len-1), ne na bílou (6)
            # Pro Guessera: cykluj 6 -> 0 -> 1 -> ... -> (len-1) -> 6
            if self.is_evaluator_mode:
                # Evaluator: jen barvy z palety, bez bílé
                if cur == 6:
                    new = 0
                else:
                    try:
                        ival = int(cur)
                    except Exception:
                        ival = 0
                    new = (ival + 1) % len(self.current_palette)
            else:
                # Guesser: 6 -> 0 -> 1 -> ... -> (len-1) -> 6
                if cur == 6:
                    new = 0
                else:
                    try:
                        ival = int(cur)
                    except Exception:
                        ival = 6
                    if 0 <= ival < len(self.current_palette) - 1:
                        new = ival + 1
                    else:
                        new = 6
            self.input_values[slot_idx] = new

            oid = self.input_slot_ids[slot_idx]
            # Pokud je nová hodnota 6, vykreslíme bílou; jinak barvu z palety
            if new == 6:
                fill_col = "#ffffff"
            else:
                fill_col = self.current_palette[new]
            self.input_canvas.itemconfig(oid, fill=fill_col)
            self._update_input_submit_enabled()
        except Exception as e:
            print(f"_on_input_slot_click error: {e}")

    def _update_input_submit_enabled(self):
        """Povolí tlačítko, pokud jsou vyplněny všechny sloty a vstup ještě nebyl odeslán."""
        try:
            if getattr(self, 'input_sent', False):
                self.input_submit_btn.config(state=tk.DISABLED)
                return
            # sentinel 6 = bílá/prázdné -> považujeme za NEvyplněné
            all_set = all((v is not None and int(v) != 6) for v in self.input_values)
            if hasattr(self, 'input_submit_btn'):
                self.input_submit_btn.config(state=(tk.NORMAL if all_set else tk.DISABLED))
        except Exception:
            pass

    def _reset_input(self):
        """Vymaže všechny sloty."""
        try:
            # reset na bílé (sentinel 6)
            self.input_values = [6] * self.num_pegs
            for oid in self.input_slot_ids:
                # vykreslíme bílé kolečko pro prázdný slot
                try:
                    self.input_canvas.itemconfig(oid, fill="#ffffff")
                except Exception:
                    pass
            self._update_input_submit_enabled()
        except Exception:
            pass

    def _submit_input(self):
        """Sestaví zprávu a odešle ji na server (pro tip i volbu)."""
        try:
            if getattr(self, 'input_sent', False):
                self.updateStatus("Vstup již odeslán", "orange")
                return
            # sentinel 6 = bílá/prázdné -> nedovolíme odeslat
            if any(int(v) == 6 for v in self.input_values):
                messagebox.showerror("Chyba", "Vyplň všech 4 slotů před odesláním")
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
                self.updateStatus(f"{action.capitalize()} odeslán", "green")
                
                try:
                    self.input_submit_btn.config(state=tk.DISABLED)
                    self.input_reset_btn.config(state=tk.DISABLED)
                    if not self.is_evaluator_mode:
                        self.hideInputPanel()
                    else:
                         self.hideInputPanel(show_status=True, status_text="Tajná kombinace odeslána. Čekám na tip protihráče.", color="#0056b3")
                    
                except Exception:
                    pass
            else:
                self.updateStatus(f"Chyba: nepodařilo se odeslat {action}", "red")
        except Exception as e:
            print(f"_submit_input error: {e}")

    def hideInputPanel(self, show_status=False, status_text="", color=""):
        """Skryje panel pro vstup a volitelně zobrazí status (pro Guessera/Evaluatora)."""
        try:
            if hasattr(self, 'input_frame') and self.input_frame:
                for widget in self.input_frame.winfo_children():
                    widget.destroy()
                if show_status:
                    tk.Label(self.input_frame, text=status_text, fg=color, font=("Arial", 12)).pack(pady=20)
                
                self._input_panel_initialized = False
        except Exception:
            pass

    def showEvaluationPanel(self, guess_str):
        """UI pro Hodnotitele (role 1): Vybrat počet černých a bílých kolíků."""
        if hasattr(self, 'eval_frame') and self.eval_frame:
            self.eval_frame.destroy()
        
        # Zničí starý input frame, ať se nepletu s Evaluatorem
        self.hideInputPanel() 

        self.eval_frame = tk.Frame(self.input_frame, bd=2, relief=tk.SUNKEN)
        self.eval_frame.pack(pady=10, fill=tk.X)

        tk.Label(self.eval_frame, text="Ohodnoť tip:", font=("Arial", 10, "bold")).pack(pady=5)

        blacks_var = tk.IntVar(value=0)
        whites_var = tk.IntVar(value=0)

        def create_stepper(parent, label_text, var, max_val):
            frame = tk.Frame(parent)
            frame.pack(side=tk.LEFT, padx=15)
            tk.Label(frame, text=label_text).pack()
            
            def change_val(delta):
                new_val = var.get() + delta
                if 0 <= new_val <= max_val and (new_val + whites_var.get() <= 4 if var == blacks_var else new_val + blacks_var.get() <= 4):
                    var.set(new_val)
                    self._update_eval_submit_enabled(blacks_var.get(), whites_var.get())

            tk.Button(frame, text="+", command=lambda: change_val(1), width=3).pack()
            tk.Label(frame, textvariable=var, font=("Arial", 12)).pack()
            tk.Button(frame, text="-", command=lambda: change_val(-1), width=3).pack()
            return var
        
        create_stepper(self.eval_frame, "Černé", blacks_var, 4)
        create_stepper(self.eval_frame, "Bílé", whites_var, 4)

        self.eval_submit_btn = tk.Button(
            self.eval_frame, 
            text="Odeslat hodnocení", 
            command=lambda: self._submit_evaluation(blacks_var.get(), whites_var.get()), 
            state=tk.DISABLED,
            bg="#2196F3", fg="white", font=("Arial", 10, "bold")
        )
        self.eval_submit_btn.pack(pady=10)

        self._update_eval_submit_enabled(0, 0)

    def _update_eval_submit_enabled(self, blacks, whites):
        """Povolí tlačítko pro hodnocení, pokud je součet menší nebo roven 4."""
        try:
            if blacks + whites <= 4:
                 self.eval_submit_btn.config(state=tk.NORMAL)
            else:
                 self.eval_submit_btn.config(state=tk.DISABLED)
        except Exception:
            pass

    def _submit_evaluation(self, blacks, whites):
        """Odešle hodnocení serveru a aktualizuje lokální stav."""
        if blacks + whites > 4:
            messagebox.showerror("Chyba", "Součet černých a bílých kolíků nesmí přesáhnout 4.")
            return

        # Odeslání zprávy: LK:EVALUATION:<černé>,<bílé>
        msg = f"{self.GAME_PREFIX}:EVALUATION:{blacks}:{whites}"
        try:
            sendMessage(self.playerSocket, msg.encode())
            print(f"Odesláno EVALUATION: {blacks},{whites}")
            
            # Hodnotitel aktualizuje lokální stav a čeká na konec hry/další tip
            self.addEvaluation((blacks, whites)) 
            
            if hasattr(self, 'eval_frame'):
                self.eval_frame.destroy()

            self.updateStatus("Hodnocení odesláno. Čekám na další tip...", "green")
            
        except Exception as e:
            print(f"Chyba při odesílání hodnocení: {e}")
            self.updateStatus("Chyba při odesílání hodnocení", "red")

    # =========================================================================
    # KOMUNIKACE SE SERVEREM
    # =========================================================================

    def send_guess(self, colors_str):
        """Send GUESSING_COLORS message to server."""
        try:
            msg = f"{self.GAME_PREFIX}:GUESSING_COLORS:{colors_str}"
            sendMessage(self.playerSocket, msg.encode())
            print(f"Odesláno GUESSING_COLORS: {colors_str}")
            return True
        except Exception as e:
            print(f"Nepodařilo se odeslat tip: {e}")
            return False

    def send_choice(self, colors_str):
        """Send CHOOSING_COLORS message to server."""
        try:
            msg = f"{self.GAME_PREFIX}:CHOOSING_COLORS:{colors_str}"
            sendMessage(self.playerSocket, msg.encode())
            print(f"Odesláno CHOOSING_COLORS: {colors_str}")
            return True
        except Exception as e:
            print(f"Nepodařilo se odeslat výběr barev: {e}")
            return False

    def recvMessageThread(self):
        """Hlavní smyčka pro příjem zpráv od serveru"""
        print(f"[{self.playerName}] Game loop started")
        while self.isRunning:
            try:
                data = recvMessage(self.playerSocket)
                if not data:
                    print(f"[{self.playerName}] Socket closed")
                    self.handleDisconnect()
                    continue
                    
                message = data.decode()
                print(f"[{self.playerName}] Received: {message}")
                self.handleMessage(message)
            except Exception as e:
                print(f"Error in gameLoop: {e}")
                self.handleDisconnect()
                time.sleep(0.1)

    def handleMessage(self, message):
        """Zpracování příchozích zpráv, s logikou synchronizace serveru (Choosing, Guessing, Evaluating)."""
        parts = message.split(":")
        
        if len(parts) < 2 or parts[0] != self.GAME_PREFIX:
            return
        
        msg_type = parts[1]
        
        if msg_type == "PING":
            random_num = randint(1, 7)
            if(random_num == 3):
                pong_msg = f"{self.GAME_PREFIX}:GGALKANE:{self.playerName}:{self.playerRole}"
            else:
                pong_msg = f"{self.GAME_PREFIX}:PONG:{self.playerName}:{self.playerRole}"
            pong_msg = f"{self.GAME_PREFIX}:PONG:{self.playerName}:{self.playerRole}"
            try:
                sendMessage(self.playerSocket, pong_msg.encode())
            except Exception:
                self.handleDisconnect()
        
        elif msg_type == "WIN_GAME":
            if(int(parts[2]) == self.playerRole):
                self.updateStatus("Gratuluji! Vyhrál jsi hru!", "gold")
            else:
                self.updateStatus("Bohužel, prohrál jsi. Protihráč vyhrál hru.", "red")
            try:
                sendMessage(self.playerSocket, f"{self.GAME_PREFIX}:WIN_GAME_ACK".encode())
            except Exception:
                pass
            # Stop all threads and prevent reconnect attempts
            self.isRunning = False
            self.reconnecting = False
            # After a short delay, return to lobby (show message first)
            if hasattr(self, 'game_window') and self.game_window:
                self.game_window.after(2000, self.returnToLobby)
            else:
                self.returnToLobby()

    
        # --- OBSLUHA ODPOJENÍ (Zůstává) ---
        elif msg_type == "PERMANENT_DISCONNECT":
            # ... (Logika odpojení zůstává stejná) ...
            opponent_name = parts[2] if len(parts) > 2 else "Protihráč"
            self.opponent_online = 0
            self.updatePresenceUI(opponent_name)
            respond_message = f"{self.GAME_PREFIX}:PERMANENT_DISCONNECT_CONFIRM:{self.playerName}:{self.playerRole}"
            try:
                sendMessage(self.playerSocket, respond_message.encode())
            except Exception:
                pass 
            self.isRunning = False
            self.game_window.after(2000, self.returnToLobby)

        elif msg_type == "TEMPORARY_DISCONNECT":
            # ... (Logika odpojení zůstává stejná) ...
            opponent_name = parts[2] if len(parts) > 2 else "Protihráč"
            self.opponent_online = 0
            self.updatePresenceUI(opponent_name)
            respond_message = f"{self.GAME_PREFIX}:TEMPORARY_DISCONNECT_CONFIRM:{self.playerName}:{self.playerRole}"
            try:
                sendMessage(self.playerSocket, respond_message.encode())
            except Exception:
                pass

        # --- FÁZE 1: VÝBĚR BAREV ---
        elif msg_type == "CHOOSING_COLORS_CONFIRM":
            # Server potvrdil, že Hodnotitel vybral (Server je ve stavu Guessing)
            if self.playerRole == 0:
                self.updateStatus("Protihráč vybral kombinaci. Můžeš hádat!", "green")
                self.game_window.after(0, lambda: self.showInputPanel(role='guesser'))
        
        # --- FÁZE 2: HÁDÁNÍ (GUESSING_COLORS_ACK - Tip odeslán/doručen) ---
        elif msg_type == "GUESSING_COLORS_ACK":
            if len(parts) > 2:
                guess_str = parts[2]
                
                if self.playerRole == 1:
                    # Hodnotitel: Server poslal PUSH zprávu s tipem. Zaznamená tip, zobrazí Hodnocení.
                    self.addGuess(guess_str)
                    self.updateStatus("Protihráč tipoval! Ohodnoť jeho tip.", "green")
                    self.game_window.after(0, lambda: self.showEvaluationPanel(guess_str))
                    
                elif self.playerRole == 0:
                    # Tipující: Server potvrdil příjem tipu. Zaznamená tip, skryje UI.
                    self.addGuess(guess_str)
                    self.updateStatus("Tip odeslán. Čekám na hodnocení...", "blue")
                    self.hideInputPanel(show_status=True, status_text="Tip odeslán. Čekám na hodnocení...", color="blue")

        elif msg_type == "RECONNECT_OTHER_PLAYER":
            opponent_name = parts[2] if len(parts) > 2 else self.opponent_name
            self.opponent_online = 1
            self.updatePresenceUI(opponent_name)
            print(f"[{self.playerName}] Opponent reconnected.")

        # --- FÁZE 3: HODNOCENÍ (EVALUATION_ACK - Hodnocení odesláno/doručeno) ---
        elif msg_type == "EVALUATION_ACK":
            # Server potvrdil EVALUATION a změnil stav zpět na CHOOSING (nové kolo)
            if len(parts) > 3:
                try:
                    blacks = int(parts[2])
                    whites = int(parts[3])
                except ValueError:
                    print("Chybný formát hodnocení.")
                    return
                
                # V obou rolích: Ulož hodnocení do aktuálního kola.
                self.addEvaluation((blacks, whites)) # TADY UŽ NEVOLÁME nextRound!

                # Pokud hra nekončí, posuneme se do dalšího kola a zobrazíme další tah.
                self.game_window.after(100, self.nextRound)
                    
                if self.playerRole == 0:
                    # Tipující: Je v novém kole. Zobrazí input.
                    self.updateStatus(f"Protihráč hodnotil. Hodnocení: {blacks} Černá, {whites} Bílá. Hádej znovu.", "green")
                    self.game_window.after(200, lambda: self.showInputPanel(role='guesser'))
                        
                elif self.playerRole == 1:
                    # Hodnotitel: Je v novém kole. Čeká na tip od Guessera.
                    self.updateStatus("Hodnocení odesláno. Čekám na další tip...", "blue")
                    self.hideInputPanel(show_status=True, status_text="Hodnocení odesláno. Čekám na další tip od protihráče.", color="blue")

        elif msg_type == "GAME_OVER":
            self.updateStatus("Konec hry! " + parts[2] if len(parts) > 2 else "Hra skončila.", "purple")
            self.isRunning = False
            self.game_window.after(5000, self.returnToLobby)
    # =========================================================================
    # RECONNECT LOGIKA
    # =========================================================================

    def handleDisconnect(self):
        """Zpracování odpojení od serveru"""
        # Pokud hra už skončila nebo okno bylo zničeno, neukazuj reconnect status
        if not self.isRunning or not hasattr(self, 'game_window') or not self.game_window.winfo_exists():
            return
        if not self.reconnecting:
            self.reconnecting = True
            self.disconnected_time = time.time()
            self.me_online = 0
            self.updatePresenceUI()
            self.updateStatus("Odpojeno - pokus o reconnect...", "red")
    
    def reconnectMonitor(self):
        """Monitoruje stav připojení a pokouší se o reconnect"""
        while self.isRunning:
            if self.reconnecting:
                elapsed = time.time() - self.disconnected_time
                
                if elapsed > 7 and elapsed < 20:
                    self.updateStatus(f"Reconnecting... ({int(elapsed)}s)", "orange")
                    if self.attemptReconnect():
                        self.reconnecting = False
                        self.disconnected_time = None
                        self.me_online = 1
                        self.updateStatus("Připojeno zpět - hra pokračuje", "green")
                        self.updatePresenceUI()
                    else:
                        time.sleep(1)
                
                elif elapsed >= 20 and elapsed < 45:
                    self.updateStatus("Znovu se prihlaš a potvrď reconnect v dialogu", "red")
                    break
                
                elif elapsed >= 45:
                    self.updateStatus("Příliš dlouhé odpojení, hra končí.", "red")
                    self.isRunning = False
                    try:
                        self.game_window.after(2000, self.returnToLobby)
                    except Exception:
                        pass
                    break
            
            time.sleep(0.5)
    
    def attemptReconnect(self):
        """Pokus o reconnect k serveru"""
        try:
            # PŘEDPOKLAD: server běží na localhost:10000
            new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            new_socket.connect(("localhost", 10000)) 
            
            reconnect_msg = f"{self.GAME_PREFIX}:RECONNECT_REQUEST:{self.playerName}:{self.playerRole}"
            sendMessage(new_socket, reconnect_msg.encode())
            
            response = recvMessage(new_socket)
            if response:
                msg = response.decode()
                if "RECONNECT_CONFIRM" in msg:
                    try:
                        self.playerSocket.close()
                    except:
                        pass
                    print(f"[{self.playerName}] Reconnected successfully")
                    self.playerSocket = new_socket
                    self.me_online = 1
                    self.updatePresenceUI()
                    return True
            
            new_socket.close()
            return False
            
        except Exception as e:
            print(f"Reconnect failed: {e}")
            return False

    # =========================================================================
    # HERNÍ DESKA A STAV
    # =========================================================================

    def addGuess(self, guess_str):
        """Přidá tip do aktuálního kola a obnoví desku."""
        if 0 <= self.currentRoundNumber < len(self.rounds):
            # Parsuj guess_str na seznam čísel a nahraď guesses (ne append)
            if isinstance(guess_str, list):
                guesses_list = guess_str
            else:
                guesses_list = [int(ch) for ch in guess_str if ch.isdigit()]
            self.rounds[self.currentRoundNumber].guesses = [guesses_list]
        
        if self.playerRole == 0:
            self.game_window.after(0, lambda: self.hideInputPanel(show_status=True, status_text="Tip odeslán. Čekám na hodnocení...", color="blue"))
        
        self.game_window.after(0, self.drawBoard)

    def addEvaluation(self, evaluation_tuple):
        """Přidá hodnocení do aktuálního kola, obnoví desku. NEVOLÁ nextRound."""
        # POZNÁMKA: nextRound se musí volat AŽ po addEvaluation v handleMessage.
        if 0 <= self.currentRoundNumber < len(self.rounds):
            self.rounds[self.currentRoundNumber].evaluations.append(evaluation_tuple)
        
        # Okamžité vykreslení (ještě ve starém kole, které má teď hodnocení)
        self.game_window.after(0, self.drawBoard) 

    def nextRound(self):
        """Přesune hru do dalšího kola a aktualizuje UI."""
        # TATA METODA VŽDY JEN INKREMENTUJE KOLO (jsou již inicializované).
        if self.currentRoundNumber < 9:
            self.currentRoundNumber += 1
        
        self.game_window.after(0, self.drawBoard)
    def drawBoard(self):
        """Vykreslí hrací desku na základě obsahu self.rounds."""
        try:
            palette = self.palette
            
            # Pokud je hráč Evaluator (role 1), zobraz jeho tajnou kombinaci
            if self.playerRole == 1 and hasattr(self, 'input_values') and self.input_values:
                # Zkontroluj, jestli secret_frame už existuje
                if not hasattr(self, 'secret_frame') or not self.secret_frame.winfo_exists():
                    self.secret_frame = tk.Frame(self.board_frame)
                    self.secret_frame.pack(side=tk.TOP, fill=tk.X, padx=12, pady=5)
                    
                    tk.Label(self.secret_frame, text="Vaše tajná kombinace:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)
                    
                    self.secret_canvas = tk.Canvas(self.secret_frame, width=250, height=40, bg=self.game_window.cget('bg'), highlightthickness=0)
                    self.secret_canvas.pack(side=tk.LEFT, padx=40)
                
                # Vykresli tajnou kombinaci (input_values)
                try:
                    self.secret_canvas.delete("all")
                    r = 12
                    spacing = 50
                    margin_x = 10
                    cy = 20
                    
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
                except Exception as e:
                    print(f"Chyba při vykreslování tajné kombinace: {e}")
            
            if hasattr(self, 'e_board_frame') and self.e_board_frame:
                try:
                    self.e_board_frame.destroy()
                except Exception:
                    pass

            self.e_board_frame = tk.Frame(self.board_frame)
            self.e_board_frame.pack(padx=12, pady=8, fill=tk.BOTH, expand=True)

            container = tk.Frame(self.e_board_frame, bg="#e0e0e0", bd=2, relief=tk.RIDGE)
            container.pack(fill=tk.BOTH, expand=True)

            vscroll = tk.Scrollbar(container, orient=tk.VERTICAL)
            vscroll.pack(side=tk.RIGHT, fill=tk.Y)

            self.e_board_canvas = tk.Canvas(container, bg="#f7f7f7", height=420)
            self.e_board_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.e_board_canvas.configure(yscrollcommand=vscroll.set)
            vscroll.configure(command=self.e_board_canvas.yview)

            # Rozměry
            top_margin = 10
            row_h = 38
            left_margin = 60
            peg_r = 11
            peg_spacing = 36
            inter_gap = 24
            eval_r = 5
            eval_gap = 14

            max_rows = max(len(self.rounds), 10)
            total_w = left_margin + 4 * peg_spacing + inter_gap + 2 * eval_gap + 40
            total_h = top_margin + max_rows * row_h + 10
            self.e_board_canvas.configure(scrollregion=(0, 0, total_w, total_h))
            
            # Helper funkce pro parsování tipu (6 = white/empty)
            def parse_guess(obj):
                if obj is None:
                    return None
                if isinstance(obj, (list, tuple)):
                    out = []
                    for g in obj:
                        if isinstance(g, int):
                            out.append(g)
                        elif isinstance(g, str) and g.lstrip('-').isdigit():
                            out.append(int(g))
                    return out[:self.num_pegs] if out else None
                if isinstance(obj, str):
                    s = obj.strip()
                    # support comma-separated
                    if ',' in s:
                        parts = [p.strip() for p in s.split(',') if p.strip()]
                        out = []
                        for p in parts:
                            if p.lstrip('-').isdigit():
                                out.append(int(p))
                        return out[:self.num_pegs] if out else None
                    # otherwise parse sequential digits
                    out = []
                    i = 0
                    while i < len(s) and len(out) < self.num_pegs:
                        if s[i] == '-' and i+1 < len(s) and s[i+1].isdigit():
                            out.append(-int(s[i+1]))
                            i += 2
                        elif s[i].isdigit():
                            out.append(int(s[i]))
                            i += 1
                        else:
                            i += 1
                    return out if out else None
                return None

            # Helper funkce pro parsování hodnocení
            def parse_eval(obj):
                if obj is None: 
                    return (0, 0)
                
                # Pokud je obj seznam (seznam evaluací), vezmi poslední
                if isinstance(obj, list) and obj:
                    value = obj[-1]
                else:
                    value = obj
                
                # Teď by měl být value tuple (blacks, whites)
                if isinstance(value, (list, tuple)):
                    if len(value) >= 2:
                        return (int(value[0] or 0), int(value[1] or 0))
                    return (0, 0)
                if isinstance(value, str):
                    s = value.strip()
                    if ',' in s:
                        parts = s.split(',')
                        if len(parts) >= 2:
                            try:
                                return (int(parts[0]), int(parts[1]))
                            except Exception:
                                return (0, 0)
                return (0, 0)

            # Vykreslení řádků (od nejstaršího po nejnovější)
            for idx, rnd in enumerate(self.rounds):
                y = top_margin + idx * row_h + row_h // 2
                rnd_no = getattr(rnd, 'roundNumber', idx)
                
                # Zvýraznění aktuálního kola
                line_color = "#333333" if rnd_no == self.currentRoundNumber else "#999999"
                if rnd_no == self.currentRoundNumber:
                    self.e_board_canvas.create_rectangle(0, y - row_h//2, total_w, y + row_h//2, fill="#fffac8", outline="")
                
                self.e_board_canvas.create_text(8, y, anchor='w',
                                                text=str(rnd_no), font=("Arial", 10, "bold" if rnd_no == self.currentRoundNumber else "normal"), fill=line_color)

                last_guess = rnd.guesses[-1] if rnd.guesses else None
                if isinstance(last_guess, list):
                    guess_vec = last_guess
                else:
                    guess_vec = parse_guess(last_guess) or [6] * self.num_pegs
                # ensure length
                guess_vec = (list(guess_vec) + [6] * self.num_pegs)[:self.num_pegs]

                # 4 velké kolíky (Tip)
                for i in range(self.num_pegs):
                    cx = left_margin + i * peg_spacing
                    fill = ""
                    outline = "#bdbdbd"
                    val = guess_vec[i]
                    if val == 6:
                        fill = "#ffffff"
                        outline = "#cccccc"
                    elif 0 <= val < len(palette):
                        fill = palette[val]
                        outline = "#7a7a7a"
                    self.e_board_canvas.create_oval(
                        cx - peg_r, y - peg_r, cx + peg_r, y + peg_r,
                        fill=fill, outline=outline, width=2
                    )

                # EVAL (Hodnocení)
                evals = rnd.evaluations[-1] if rnd.evaluations else None
                blacks, whites = parse_eval(evals)

                eval_left = left_margin + 4 * peg_spacing + inter_gap
                positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
                k = 0
                
                # Černé kolíky
                for _ in range(min(4, max(0, int(blacks)))):
                    col, row = positions[k]; k += 1
                    cx = eval_left + col * eval_gap
                    cy = y - eval_gap // 2 + row * eval_gap
                    self.e_board_canvas.create_oval(
                        cx - eval_r, cy - eval_r, cx + eval_r, cy + eval_r,
                        fill="#FF6C1D", outline="#333333", width=1
                    )
                # Bílé kolíky
                for _ in range(min(4 - k, max(0, int(whites)))):
                    col, row = positions[k]; k += 1
                    cx = eval_left + col * eval_gap
                    cy = y - eval_gap // 2 + row * eval_gap
                    self.e_board_canvas.create_oval(
                        cx - eval_r, cy - eval_r, cx + eval_r, cy + eval_r,
                        fill="#969696", outline="#999999", width=1
                    )
                # Prázdné kolíky
                while k < 4:
                    col, row = positions[k]; k += 1
                    cx = eval_left + col * eval_gap
                    cy = y - eval_gap // 2 + row * eval_gap
                    self.e_board_canvas.create_oval(
                        cx - eval_r, cy - eval_r, cx + eval_r, cy + eval_r,
                        fill="#f0f0f0", outline="#cccccc", width=1
                    )

            # Doplnění prázdnými řádky (pro plnou desku)
            for pad_idx in range(len(self.rounds), max_rows):
                y = top_margin + pad_idx * row_h + row_h // 2
                self.e_board_canvas.create_text(8, y, anchor='w', text=str(pad_idx + 1), font=("Arial", 10), fill="#cccccc")
                # Vykreslení prázdných kolíků (bílé - sentinel 6)
                for i in range(self.num_pegs):
                     cx = left_margin + i * peg_spacing
                     self.e_board_canvas.create_oval(cx - peg_r, y - peg_r, cx + peg_r, y + peg_r, fill="#ffffff", outline="#cccccc", width=2)
                eval_left = left_margin + 4 * peg_spacing + inter_gap
                positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
                for col, row in positions:
                    cx = eval_left + col * eval_gap
                    cy = y - eval_gap // 2 + row * eval_gap
                    self.e_board_canvas.create_oval(cx - eval_r, cy - eval_r, cx + eval_r, cy + eval_r, fill="", outline="#e0e0e0", width=1)
            
            # Rolovat na konec
            if len(self.rounds) > 10:
                self.e_board_canvas.yview_moveto(1.0)
            
            
        except Exception as e:
            print(f"drawBoard error: {e}")

    # =========================================================================
    # RŮZNÉ A CLEANUP
    # =========================================================================

    def updateStatus(self, text, color):
        """Aktualizace statusu v GUI (thread-safe)"""
        try:
            if hasattr(self, 'game_window') and self.game_window:
                def _upd():
                    try:
                        if hasattr(self, 'status_label'):
                            self.status_label.config(text=text, fg=color)
                    except Exception:
                        pass
                try:
                    self.game_window.after(0, _upd)
                except Exception:
                    _upd()
        except Exception:
            pass
    
    def returnToLobby(self):
        """Zavře herní okno a vrátí hráče zpět do lobby"""
        try:
            if hasattr(self, 'game_window') and self.game_window:
                self.game_window.destroy()
            
            if self.client and hasattr(self.client, 'handleLobby'):
                self.client.handleLobby()
            else:
                print("Chyba: Není reference na klienta, nelze vrátit do lobby")
        except Exception as e:
            print(f"Chyba při návratu do lobby: {e}")