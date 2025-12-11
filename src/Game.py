import socket
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
from SocketLib import *
from LogikClient import *
from random import randint

class RoundInfo:
    def __init__(self, roundNumber):
        self.roundNumber = roundNumber
        self.guesses = []  # List of color guesses
        self.evaluations = []  # List of evaluations corresponding to guesses

class Game:
    def __init__(self, playerSocket, playerName=None, playerRole=None, LogikClientInstance=None):
        self.isRunning = False
        self.isPaused = False
        self.playerSocket = playerSocket
        self.playerName = playerName
        try:
            self.playerRole = int(playerRole)
        except Exception:
            self.playerRole = playerRole
        self.GAME_PREFIX = "LK"
        self.color_combinations = []
        self.reconnecting = False
        self.disconnected_time = None
        self.client = LogikClientInstance
        self.rounds = []
        self.currentRound = None
        self._guess_panel_initialized = False

    
    def start(self):
        self.isRunning = True
        self.isPaused = False
        self.game_window = tk.Tk()
        self.game_window.geometry("500x600")
        self.game_window.title(f"Hra - {self.playerName}")

        # --- Main layout frames ---
        self.top_frame = tk.Frame(self.game_window)
        self.top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        self.board_frame = tk.Frame(self.game_window)
        self.board_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # --------------------------
        
        self.status_label = tk.Label(self.top_frame, text="Hra běží", fg="green", font=("Arial", 14))
        self.status_label.pack(pady=10)
        
        self.info_label = tk.Label(self.top_frame, text=f"Hráč: {self.playerName} | Role: {self.playerRole}")
        self.info_label.pack(pady=5)
        # Pokud je hráč Evaluator (role==1), zobrazit kruhový výběr barev
        if isinstance(self.playerRole, int) and self.playerRole == 1:
            self.choose()
        
        self.drawBoard()


        #threading.Thread(target=self.gameLoopDraw, daemon=True).start()

        threading.Thread(target=self.recvMessageThread, daemon=True).start()
        
        # Start reconnect monitor
        threading.Thread(target=self.reconnectMonitor, daemon=True).start()
        
        self.game_window.mainloop()
    
    def continueGame(self, state):
        self.isRunning = True
        self.isPaused = False
        self.game_window = tk.Tk()
        self.game_window.geometry("500x600")
        self.game_window.title(f"Hra - {self.playerName}")

        # --- Main layout frames ---
        self.top_frame = tk.Frame(self.game_window)
        self.top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        self.board_frame = tk.Frame(self.game_window)
        self.board_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # --------------------------
        
        self.status_label = tk.Label(self.top_frame, text="Hra běží", fg="green", font=("Arial", 14))
        self.status_label.pack(pady=10)
        
        self.info_label = tk.Label(self.top_frame, text=f"Hráč: {self.playerName} | Role: {self.playerRole}")
        self.info_label.pack(pady=5)
        # Pokud je hráč Evaluator (role==1), zobrazit kruhový výběr barev
        if isinstance(self.playerRole, int) and self.playerRole == 1:
            self.choose()
        
        self.drawBoard()


        #threading.Thread(target=self.gameLoopDraw, daemon=True).start()

        threading.Thread(target=self.recvMessageThread, daemon=True).start()
        
        # Start reconnect monitor
        threading.Thread(target=self.reconnectMonitor, daemon=True).start()
        
        self.game_window.mainloop()
            

    def guessPanel(self):
        """UI for Guesser: 4 small clickable circles cycling colors + submit button."""
        try:
            self.guess_palette = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4"]
            self.guess_values = [None, None, None, None]
            self.guess_slot_ids = []
            self.guess_sent = False

            self.guess_frame = tk.Frame(self.top_frame)
            self.guess_frame.pack(pady=10, fill=tk.X)

            tk.Label(self.guess_frame, text="Hádej 4 barvy (kliknutím cykluj barvy)").pack(pady=4)

            self.guess_canvas = tk.Canvas(self.guess_frame, width=320, height=70, bg=self.game_window.cget('bg'), highlightthickness=0)
            self.guess_canvas.pack()

            margin_x = 30
            spacing = 60
            cy = 35
            r = 12

            for i in range(4):
                cx = margin_x + i * spacing
                oid = self.guess_canvas.create_oval(
                    cx - r, cy - r, cx + r, cy + r,
                    fill=self.game_window.cget('bg'), outline="#7a7a7a", width=2
                )
                self.guess_slot_ids.append(oid)
                self.guess_canvas.tag_bind(oid, "<Button-1>", lambda e, idx=i: self._on_guess_slot_click(idx))

            ctrl = tk.Frame(self.guess_frame)
            ctrl.pack(pady=6)

            self.guess_submit_btn = tk.Button(ctrl, text="Odeslat tip", command=self._submit_guess, state=tk.DISABLED)
            self.guess_submit_btn.pack(side=tk.LEFT, padx=6)

            self.guess_reset_btn = tk.Button(ctrl, text="Vymazat", command=self._reset_guess)
            self.guess_reset_btn.pack(side=tk.LEFT, padx=6)

        except Exception as e:
            print(f"guessPanel UI error: {e}")

    def _on_guess_slot_click(self, slot_idx):
        try:
            cur = self.guess_values[slot_idx]
            new = 0 if cur is None else (cur + 1) % len(self.guess_palette)
            self.guess_values[slot_idx] = new
            oid = self.guess_slot_ids[slot_idx]
            self.guess_canvas.itemconfig(oid, fill=self.guess_palette[new])
            self._update_guess_submit_enabled()
        except Exception as e:
            print(f"_on_guess_slot_click error: {e}")

    def _update_guess_submit_enabled(self):
        try:
            if getattr(self, 'guess_sent', False):
                self.guess_submit_btn.config(state=tk.DISABLED)
                return
            all_set = all(v is not None for v in self.guess_values)
            self.guess_submit_btn.config(state=(tk.NORMAL if all_set else tk.DISABLED))
        except Exception:
            pass

    def _reset_guess(self):
        try:
            self.guess_values = [None, None, None, None]
            for oid in self.guess_slot_ids:
                self.guess_canvas.itemconfig(oid, fill=self.game_window.cget('bg'))
            self._update_guess_submit_enabled()
        except Exception as e:
            print(f"_reset_guess error: {e}")

    def _submit_guess(self):
        try:
            if getattr(self, 'guess_sent', False):
                self.updateStatus("Tip již odeslán", "orange")
                return
            for v in self.guess_values:
                if v is None:
                    messagebox.showerror("Chyba", "Vyplň všech 4 slotů před odesláním")
                    return
            s = ''.join(str(v) for v in self.guess_values)
            ok = self.send_guess(s)
            if ok:
                self.guess_sent = True
                try:
                    self.guess_submit_btn.config(state=tk.DISABLED)
                    self.guess_reset_btn.config(state=tk.DISABLED)
                except Exception:
                    pass
                try:
                    if hasattr(self, 'guess_frame') and self.guess_frame:
                        self.guess_frame.destroy()
                        # Allow recreation next round
                        self._guess_panel_initialized = False
                except Exception:
                    pass
            else:
                self.updateStatus("Chyba: nepodařilo se odeslat tip", "red")
        except Exception as e:
            print(f"_submit_guess error: {e}")

    def send_guess(self, colors_str):
        """Send GUESSING_COLORS message to server."""
        try:
            msg = f"{self.GAME_PREFIX}:GUESSING_COLORS:{colors_str}"
            sendMessage(self.playerSocket, msg.encode())
            print(f"Odesláno GUESSING_COLORS: {colors_str}")
            self.updateStatus("Tip odeslán", "green")
            return True
        except Exception as e:
            print(f"Nepodařilo se odeslat tip: {e}")
            self.updateStatus("Chyba při odesílání tipu", "red")
            return False

    def drawBoard(self):
        try:
            # Paleta 0..5 → barvy
            palette = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4"]

            # Znič předchozí board, ať se neduplikuje
            if hasattr(self, 'e_board_frame') and self.e_board_frame:
                try:
                    self.e_board_frame.destroy()
                except Exception:
                    pass

            # Kontejner + scrollbar + canvas
            self.e_board_frame = tk.Frame(self.board_frame)
            self.e_board_frame.pack(padx=12, pady=8, fill=tk.BOTH, expand=True)

            container = tk.Frame(self.e_board_frame)
            container.pack(fill=tk.BOTH, expand=True)

            vscroll = tk.Scrollbar(container, orient=tk.VERTICAL)
            vscroll.pack(side=tk.RIGHT, fill=tk.Y)

            self.e_board_canvas = tk.Canvas(container, bg="#f7f7f7", height=420)
            self.e_board_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.e_board_canvas.configure(yscrollcommand=vscroll.set)
            vscroll.configure(command=self.e_board_canvas.yview)

            # Rozvržení
            top_margin = 10
            row_h = 38
            left_margin = 60
            peg_r = 11
            peg_spacing = 36
            inter_gap = 24
            eval_r = 5
            eval_gap = 14

            max_rows = max(len(self.rounds), 12)
            total_h = top_margin + max_rows * row_h + 10
            total_w = left_margin + 4 * peg_spacing + inter_gap + 2 * eval_gap + 40
            self.e_board_canvas.configure(scrollregion=(0, 0, total_w, total_h))

            # Hlavička
            self.e_board_canvas.create_text(8, top_margin - 2, anchor='nw',
                                            text="Kolo", font=("Arial", 10, "bold"))

            # Pomocné funkce pro parsování
            def parse_guess(obj):
                # Vrátí list[int] 0..5, max 4 kusy
                if obj is None:
                    return None
                if isinstance(obj, (list, tuple)):
                    out = []
                    for g in obj:
                        if isinstance(g, int):
                            out.append(g)
                        elif isinstance(g, str) and g.isdigit():
                            out.append(int(g))
                    return out[:4] if out else None
                if isinstance(obj, str):
                    return [int(ch) for ch in obj if ch.isdigit()][:4] or None
                return None

            def parse_eval(obj):
                # Vrátí (blacks, whites)
                if obj is None:
                    return (0, 0)
                # výběr poslední hodnoty, pokud je list/tuple
                value = obj
                if isinstance(obj, (list, tuple)) and obj:
                    value = obj[-1]

                if isinstance(value, (list, tuple)):
                    if len(value) >= 2:
                        return (int(value[0] or 0), int(value[1] or 0))
                    return (0, 0)
                if isinstance(value, dict):
                    return (int(value.get('blacks', 0)), int(value.get('whites', 0)))
                if isinstance(value, str):
                    s = value.strip()
                    if ',' in s:
                        parts = s.split(',')
                        if len(parts) >= 2:
                            try:
                                return (int(parts[0]), int(parts[1]))
                            except Exception:
                                return (0, 0)
                    # např. "BBWW" => B/b = black, W/w = white
                    b = s.count('B') + s.count('b')
                    w = s.count('W') + s.count('w')
                    return (b, w)
                return (0, 0)

            # Vykreslení řádků
            for idx, rnd in enumerate(self.rounds):
                y = top_margin + idx * row_h + row_h // 2
                # číslo kola
                rnd_no = getattr(rnd, 'roundNumber', idx + 1)
                self.e_board_canvas.create_text(8, y, anchor='w',
                                                text=str(rnd_no), font=("Arial", 10))

                # GUESS: vezmi poslední z rnd.guesses
                last_guess = None
                guesses = getattr(rnd, 'guesses', None)
                if isinstance(guesses, (list, tuple)) and guesses:
                    last_guess = guesses[-1]
                elif isinstance(guesses, str):
                    last_guess = guesses

                guess_vec = parse_guess(last_guess) or []

                # 4 velké kolíky
                for i in range(4):
                    cx = left_margin + i * peg_spacing
                    fill = ""
                    outline = "#bdbdbd"
                    if i < len(guess_vec) and 0 <= guess_vec[i] <= 5:
                        fill = palette[guess_vec[i]]
                        outline = "#7a7a7a"
                    self.e_board_canvas.create_oval(
                        cx - peg_r, y - peg_r, cx + peg_r, y + peg_r,
                        fill=fill, outline=outline, width=2
                    )

                # EVAL: poslední z rnd.evaluations
                evals = getattr(rnd, 'evaluations', None)
                blacks, whites = parse_eval(evals)

                # 2×2 malé kolíky: nejdřív černé, pak bílé
                eval_left = left_margin + 4 * peg_spacing + inter_gap
                positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
                k = 0
                for _ in range(min(4, max(0, int(blacks)))):
                    col, row = positions[k]
                    k += 1
                    cx = eval_left + col * eval_gap
                    cy = y - eval_gap // 2 + row * eval_gap
                    self.e_board_canvas.create_oval(
                        cx - eval_r, cy - eval_r, cx + eval_r, cy + eval_r,
                        fill="#000000", outline="#333333", width=1
                    )
                for _ in range(min(4 - k, max(0, int(whites)))):
                    col, row = positions[k]
                    k += 1
                    cx = eval_left + col * eval_gap
                    cy = y - eval_gap // 2 + row * eval_gap
                    self.e_board_canvas.create_oval(
                        cx - eval_r, cy - eval_r, cx + eval_r, cy + eval_r,
                        fill="#ffffff", outline="#999999", width=1
                    )
                # zbytek prázdné kontury
                while k < 4:
                    col, row = positions[k]
                    k += 1
                    cx = eval_left + col * eval_gap
                    cy = y - eval_gap // 2 + row * eval_gap
                    self.e_board_canvas.create_oval(
                        cx - eval_r, cy - eval_r, cx + eval_r, cy + eval_r,
                        fill="", outline="#bdbdbd", width=1
                    )

            # Pokud rounds je kratší než 12, vykresli prázdné řádky až do 12
            for pad_idx in range(len(self.rounds), 12):
                y = top_margin + pad_idx * row_h + row_h // 2
                self.e_board_canvas.create_text(8, y, anchor='w',
                                                text=str(pad_idx + 1), font=("Arial", 10))
                # prázdné guess kolíky
                for i in range(4):
                    cx = left_margin + i * peg_spacing
                    self.e_board_canvas.create_oval(
                        cx - peg_r, y - peg_r, cx + peg_r, y + peg_r,
                        fill="", outline="#bdbdbd", width=2
                    )
                # prázdné eval kolíky
                eval_left = left_margin + 4 * peg_spacing + inter_gap
                positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
                for col, row in positions:
                    cx = eval_left + col * eval_gap
                    cy = y - eval_gap // 2 + row * eval_gap
                    self.e_board_canvas.create_oval(
                        cx - eval_r, cy - eval_r, cx + eval_r, cy + eval_r,
                        fill="", outline="#bdbdbd", width=1
                    )

        except Exception as e:
            print(f"drawBoardE error: {e}")
    
    def gameLoopDraw(self):
        """Periodic UI updater: schedule draws and (for Guesser) show guess panel once."""
        print(f"[{self.playerName}] UI draw loop started")
        while self.isRunning:
            try:
                if hasattr(self, 'game_window') and self.game_window:
                    # Schedule board redraw on Tk main thread
                    try:
                        self.game_window.after(0, self.drawBoard)
                    except Exception:
                        pass
            except Exception as e:
                print(f"gameLoopDraw scheduling error: {e}")
            time.sleep(0.5)

    def recvMessageThread(self):
        """Hlavní smyčka pro příjem zpráv od serveru"""
        print(f"[{self.playerName}] Game loop started")
        while self.isRunning:
            try:
                data = recvMessage(self.playerSocket)
                if not data:
                    # Socket zavřen
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
        """Zpracování příchozích zpráv"""
        parts = message.split(":")
        
        if len(parts) < 2:
            return
        
        msg_type = parts[1]
        
        if msg_type == "PING":
            # Odpověz s PONG
            
            pong_msg = f"{self.GAME_PREFIX}:PONG:{self.playerName}:{self.playerRole}"
            
            print(f"[{self.playerName}] Sending PONG: {pong_msg}")
            try:
                sendMessage(self.playerSocket, pong_msg.encode())
                print(f"[{self.playerName}] PONG sent successfully")
            except Exception as e:
                print(f"[{self.playerName}] Failed to send PONG: {e}")
                self.handleDisconnect()
        
        elif msg_type == "PERMANENT_DISCONNECT":
            opponent_name = parts[2] if len(parts) > 2 else "Protihráč"
            self.updateStatus(f"{opponent_name} se odpojil na dobro, vracím tě do lobby.", "red")
            respond_message = f"{self.GAME_PREFIX}:PERMANENT_DISCONNECT_CONFIRM:{self.playerName}:{self.playerRole}"
            try:
                sendMessage(self.playerSocket, respond_message.encode())
                print(f"[{self.playerName}] Sent PERMANENT_DISCONNECT_CONFIRM")
            except Exception as e:
                print(f"[{self.playerName}] Failed to send PERMANENT_DISCONNECT_CONFIRM: {e}")

            self.isRunning = False
            self.game_window.after(2000, self.returnToLobby)

        elif msg_type == "TEMPORARY_DISCONNECT":
            opponent_name = parts[2] if len(parts) > 2 else "Protihráč"
            self.updateStatus(f"{opponent_name} se dočasně odpojil, čekám na jeho návrat...", "orange")
            respond_message = f"{self.GAME_PREFIX}:TEMPORARY_DISCONNECT_CONFIRM:{self.playerName}:{self.playerRole}"
            try:
                sendMessage(self.playerSocket, respond_message.encode())
                print(f"[{self.playerName}] Sent TEMPORARY_DISCONNECT_CONFIRM")
            except Exception as e:
                print(f"[{self.playerName}] Failed to send TEMPORARY_DISCONNECT_CONFIRM: {e}")
        elif msg_type == "CHOOSING_COLORS_CONFIRM":
            # Server confirms that Evaluator has chosen colors. Guesser should now see the guess panel.
            try:
                role_int = int(self.playerRole)
            except (ValueError, TypeError):
                role_int = -1 # Invalid role

            # Only the Guesser (role 0) should see the guess panel.
            if isinstance(role_int, int) and role_int == 0:
                # Check if the panel is already shown to avoid duplicates
                if not getattr(self, '_guess_panel_initialized', False):
                    # Ensure we have a window to draw on
                    if hasattr(self, 'game_window') and self.game_window:
                        
                        def _show_guess_panel():
                            """Wrapper to create panel and set flag, ensuring it runs on main thread."""
                            try:
                                print("DEBUG: Executing _show_guess_panel on main thread.")
                                self.guessPanel()
                                self._guess_panel_initialized = True
                                print("DEBUG: guessPanel created and flag set.")
                            except Exception as e:
                                print(f"ERROR: creating guessPanel from after(): {e}")

                        # Schedule the UI update on the main Tkinter thread
                        try:
                            print("DEBUG: Scheduling guessPanel creation.")
                            self.game_window.after(0, _show_guess_panel)
                        except Exception as e:
                            print(f"ERROR: scheduling guessPanel with after(): {e}")
                    
        else:
            # Jiné herní zprávy - zpracuj zde podle potřeby
            print(f"Received game message: {message}")
    
    def handleDisconnect(self):
        """Zpracování odpojení od serveru"""
        if not self.reconnecting:
            self.reconnecting = True
            self.disconnected_time = time.time()
            self.updateStatus("Odpojeno - pokus o reconnect...", "red")
    
    def reconnectMonitor(self):
        """Monitoruje stav připojení a pokouší se o reconnect"""
        while self.isRunning:
            if self.reconnecting:
                elapsed = time.time() - self.disconnected_time
                
                if elapsed > 7 and elapsed < 20:
                    # Krátké odpojení - automatický reconnect
                    self.updateStatus(f"Reconnecting... ({int(elapsed)}s)", "orange")
                    if self.attemptReconnect():
                        self.reconnecting = False
                        self.disconnected_time = None
                        self.updateStatus("Připojeno zpět - hra pokračuje", "green")
                    else:
                        time.sleep(1)
                
                elif elapsed >= 20 and elapsed < 45:
                    # Delší odpojení - vyžaduje potvrzení uživatele
                    self.updateStatus("Znovu se prihlaš a potvrď reconnect v dialogu", "red")
                    break
                
                elif elapsed >= 45:
                    # Příliš dlouhé odpojení - ukonči hru
                    self.updateStatus("Příliš dlouhé odpojení, hra končí.", "red")
                    self.isRunning = False
                    self.game_window.after(2000, self.client.on_close())
                    break
            
            time.sleep(0.5)
    
    def attemptReconnect(self):
        """Pokus o reconnect k serveru"""
        try:
            # Vytvoř nový socket
            new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            new_socket.connect(("localhost", 10000))
            
            # Pošli RECONNECT zprávu se jménem a rolí
            reconnect_msg = f"{self.GAME_PREFIX}:RECONNECT_REQUEST:{self.playerName}:{self.playerRole}"
            sendMessage(new_socket, reconnect_msg.encode())
            
            # Čekej na odpověď
            response = recvMessage(new_socket)
            if response:
                msg = response.decode()
                if "RECONNECT_CONFIRM" in msg:
                    # Úspěšný reconnect - zaměň socket
                    try:
                        self.playerSocket.close()
                    except:
                        pass
                    print(f"[{self.playerName}] Reconnected successfully")
                    self.playerSocket = new_socket
                    return True
            
            new_socket.close()
            return False
            
        except Exception as e:
            print(f"Reconnect failed: {e}")
            return False
    
    def updateStatus(self, text, color):
        """Aktualizace statusu v GUI (thread-safe)"""
        # Schedule GUI update on main thread
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
            else:
                # Fallback
                if hasattr(self, 'status_label'):
                    self.status_label.config(text=text, fg=color)
        except Exception as e:
            print(f"updateStatus error: {e}")

    def _on_choose_colors(self):
        """Prompt user for 4-digit color string (0..5) and send to server using CHOOSING_COLORS prefix."""
        try:
            s = simpledialog.askstring("Vybrat barvy", "Zadej 4 čísla 0-5 (např. 0123):", parent=self.game_window)
            if s is None:
                return
            s = s.strip()
            if len(s) != 4:
                messagebox.showerror("Chyba", "Zadej přesně 4 znaky (0-5)")
                return
            for ch in s:
                if ch < '0' or ch > '5':
                    messagebox.showerror("Chyba", "Každý znak musí být v rozsahu 0-5")
                    return
            # send using server expected prefix
            self.send_choice(s)
        except Exception as e:
            print(f"Chyba při výběru barev: {e}")

    def _build_color_chooser(self, parent):
        """Moderní volba barev: 4 velké sloty mění barvu kliknutím (bez palety)."""
        self.palette_colors = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4"]
        self.slots_values = [None, None, None, None]
        self.colors_sent = False

        # Root frame for chooser (so it can be hidden later)
        self.chooser_frame = tk.Frame(parent)
        self.chooser_frame.pack(pady=10, fill=tk.X)

        title = tk.Label(self.chooser_frame, text="Vyber 4 barvy (levý klik = další barva, pravý klik = smazat)")
        title.pack(fill=tk.X)

        slots_frame = tk.Frame(self.chooser_frame)
        slots_frame.pack(pady=10)

        self.slot_buttons = []
        for i in range(4):
            sb = tk.Button(slots_frame, text=f"Slot {i+1}", width=12, height=4, relief=tk.FLAT,
                           bg=self.game_window.cget('bg'), bd=2, highlightthickness=1)
            sb.grid(row=0, column=i, padx=10, pady=6)
            sb.config(command=lambda idx=i: self._on_slot_click(idx))
            sb.bind('<Button-3>', lambda e, idx=i: self._clear_slot(idx))
            self.slot_buttons.append(sb)

        ctrl_frame = tk.Frame(self.chooser_frame)
        ctrl_frame.pack(pady=8)

        self.confirm_btn = tk.Button(ctrl_frame, text="Potvrdit výběr", command=self._confirm_colors, state=tk.DISABLED)
        self.confirm_btn.pack(side=tk.LEFT, padx=8)

        self.reset_btn = tk.Button(ctrl_frame, text="Vymazat", command=self._reset_slots)
        self.reset_btn.pack(side=tk.LEFT, padx=8)

        hint = tk.Label(self.chooser_frame, text="Tip: klikáním na sloty přepínáš barvy")
        hint.pack(pady=4)

        self._update_confirm_enabled()

    def _on_palette_click(self, idx):
        # Bez palety v moderní verzi
        return

    def _on_slot_click(self, slot_idx):
        """Levy klik: cykluje barvy v daném slotu."""
        try:
            cur = self.slots_values[slot_idx]
            new = 0 if cur is None else (cur + 1) % len(self.palette_colors)
            self.slots_values[slot_idx] = new
            self.slot_buttons[slot_idx].config(text="", bg=self.palette_colors[new])
            self._update_confirm_enabled()
        except Exception as e:
            print(f"_on_slot_click error: {e}")

    def _clear_slot(self, slot_idx):
        """Pravý klik: smaže barvu ve slotu."""
        try:
            self.slots_values[slot_idx] = None
            self.slot_buttons[slot_idx].config(text=f"Slot {slot_idx+1}", bg=self.game_window.cget('bg'))
            self._update_confirm_enabled()
        except Exception as e:
            print(f"_clear_slot error: {e}")

    def _confirm_colors(self):
        """Assemble 4-digit string and send to server if valid."""
        try:
            if getattr(self, 'colors_sent', False):
                # Already sent once, ignore further confirms
                self.updateStatus("Barvy již odeslány", "orange")
                return
            for v in self.slots_values:
                if v is None:
                    messagebox.showerror("Chyba", "Vyplň všech 4 slotů před potvrzením")
                    return
            s = ''.join(str(v) for v in self.slots_values)
            # Validate just in case
            if len(s) != 4:
                messagebox.showerror("Chyba", "Neplatná kombinace")
                return
            ok = self.send_choice(s)
            if ok:
                # disable and hide chooser UI
                self.colors_sent = True
                self.updateStatus("Barvy odeslány", "green")
                try:
                    self._hide_color_chooser()
                except Exception:
                    pass
            else:
                # No popup, just inline status
                self.updateStatus("Chyba: nepodařilo se odeslat kombinaci", "red")
        except Exception as e:
            print(f"_confirm_colors error: {e}")

    def _reset_slots(self):
        self.slots_values = [None, None, None, None]
        for i, sb in enumerate(self.slot_buttons):
            sb.config(text=f"Slot {i+1}", bg=self.game_window.cget('bg'))
        self._update_confirm_enabled()

    def _update_confirm_enabled(self):
        """Povolí tlačítko Potvrdit, až když jsou vyplněny všechny 4 sloty."""
        try:
            if getattr(self, 'colors_sent', False):
                self.confirm_btn.config(state=tk.DISABLED)
                return
            all_set = all(v is not None for v in self.slots_values)
            self.confirm_btn.config(state=(tk.NORMAL if all_set else tk.DISABLED))
        except Exception:
            pass

    def _disable_color_chooser(self):
        """Disable palette, slots and control buttons after successful send."""
        try:
            for sb in getattr(self, 'slot_buttons', []):
                try:
                    sb.config(state=tk.DISABLED)
                except Exception:
                    pass
            if hasattr(self, 'confirm_btn'):
                try:
                    self.confirm_btn.config(state=tk.DISABLED)
                except Exception:
                    pass
            if hasattr(self, 'reset_btn'):
                try:
                    self.reset_btn.config(state=tk.DISABLED)
                except Exception:
                    pass
        except Exception as e:
            print(f"_disable_color_chooser error: {e}")

    def _hide_color_chooser(self):
        """Remove chooser UI after sending to match no-popup, clean design."""
        try:
            self._disable_color_chooser()
            if hasattr(self, 'chooser_frame') and self.chooser_frame:
                self.chooser_frame.destroy()
                # Optionally show a subtle inline note (not a popup)
                done = tk.Label(self.game_window, text="Výběr odeslán.")
                done.pack(pady=8)
        except Exception as e:
            print(f"_hide_color_chooser error: {e}")

    # --- New Evaluator chooser with small clickable circles ---
    def choose(self):
        """UI for Evaluator: 4 small clickable circles cycling colors + submit button."""
        try:
            # Palette 0..5
            self.choose_palette = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4"]
            self.choose_values = [None, None, None, None]
            self.choose_slot_ids = []
            self.choose_sent = False

            self.choose_frame = tk.Frame(self.top_frame)
            self.choose_frame.pack(pady=10, fill=tk.X)

            tk.Label(self.choose_frame, text="Vyber 4 barvy (kliknutím cykluj barvy)").pack(pady=4)

            # Canvas with 4 small circles
            self.choose_canvas = tk.Canvas(self.choose_frame, width=320, height=70, bg=self.game_window.cget('bg'), highlightthickness=0)
            self.choose_canvas.pack()

            margin_x = 30
            spacing = 60
            cy = 35
            r = 12

            for i in range(4):
                cx = margin_x + i * spacing
                oid = self.choose_canvas.create_oval(
                    cx - r, cy - r, cx + r, cy + r,
                    fill=self.game_window.cget('bg'), outline="#7a7a7a", width=2, tags=(f"slot{i}",)
                )
                self.choose_slot_ids.append(oid)
                # Bind left click directly to the item id for reliable hits
                self.choose_canvas.tag_bind(oid, "<Button-1>", lambda e, idx=i: self._on_choose_slot_click(idx))

            ctrl = tk.Frame(self.choose_frame)
            ctrl.pack(pady=6)

            self.choose_submit_btn = tk.Button(ctrl, text="Odeslat výběr", command=self._submit_choose, state=tk.DISABLED)
            self.choose_submit_btn.pack(side=tk.LEFT, padx=6)

            self.choose_reset_btn = tk.Button(ctrl, text="Vymazat", command=self._reset_choose)
            self.choose_reset_btn.pack(side=tk.LEFT, padx=6)

        except Exception as e:
            print(f"choose UI error: {e}")

    def _on_choose_slot_click(self, slot_idx):
        try:
            cur = self.choose_values[slot_idx]
            new = 0 if cur is None else (cur + 1) % len(self.choose_palette)
            self.choose_values[slot_idx] = new
            # update fill color
            oid = self.choose_slot_ids[slot_idx]
            self.choose_canvas.itemconfig(oid, fill=self.choose_palette[new])
            self._update_choose_submit_enabled()
        except Exception as e:
            print(f"_on_choose_slot_click error: {e}")

    def _update_choose_submit_enabled(self):
        try:
            if getattr(self, 'choose_sent', False):
                self.choose_submit_btn.config(state=tk.DISABLED)
                return
            all_set = all(v is not None for v in self.choose_values)
            self.choose_submit_btn.config(state=(tk.NORMAL if all_set else tk.DISABLED))
        except Exception:
            pass

    def _reset_choose(self):
        try:
            self.choose_values = [None, None, None, None]
            for oid in self.choose_slot_ids:
                self.choose_canvas.itemconfig(oid, fill=self.game_window.cget('bg'))
            self._update_choose_submit_enabled()
        except Exception as e:
            print(f"_reset_choose error: {e}")

    def _submit_choose(self):
        try:
            if getattr(self, 'choose_sent', False):
                self.updateStatus("Barvy již odeslány", "orange")
                return
            for v in self.choose_values:
                if v is None:
                    messagebox.showerror("Chyba", "Vyplň všech 4 slotů před odesláním")
                    return
            s = ''.join(str(v) for v in self.choose_values)
            ok = self.send_choice(s)
            if ok:
                self.choose_sent = True
                # Disable and hide UI after successful send
                try:
                    self.choose_submit_btn.config(state=tk.DISABLED)
                    self.choose_reset_btn.config(state=tk.DISABLED)
                except Exception:
                    pass
                try:
                    if hasattr(self, 'choose_frame') and self.choose_frame:
                        # Don't destroy, just hide children
                        for widget in self.choose_frame.winfo_children():
                            widget.destroy()
                        # Add a label indicating the choice was sent
                        tk.Label(self.choose_frame, text="Kombinace byla odeslána.").pack(pady=20)
                except Exception:
                    pass
            else:
                self.updateStatus("Chyba: nepodařilo se odeslat kombinaci", "red")
        except Exception as e:
            print(f"_submit_choose error: {e}")

    def send_choice(self, colors_str):
        """Send CHOOSING_COLORS message to server."""
        try:
            msg = f"{self.GAME_PREFIX}:CHOOSING_COLORS:{colors_str}"
            sendMessage(self.playerSocket, msg.encode())
            print(f"Odesláno CHOOSING_COLORS: {colors_str}")
            self.updateStatus("Barvy odeslány", "green")
            return True
        except Exception as e:
            print(f"Nepodařilo se odeslat výběr barev: {e}")
            self.updateStatus("Chyba při odesílání barev", "red")
            return False
    
    def returnToLobby(self):
        """Zavře herní okno a vrátí hráče zpět do lobby"""
        try:
            # Zavři game window
            if hasattr(self, 'game_window') and self.game_window:
                self.game_window.destroy()
            
            # Pokud máme referenci na client, znovu otevři lobby
            if self.client:
                self.client.handleLobby()
            else:
                print("Chyba: Není reference na klienta, nelze vrátit do lobby")
        except Exception as e:
            print(f"Chyba při návratu do lobby: {e}")
    
    def evaluate_message(self, message, STATE_PREFIX, PARTS_COUNT):
        parts = message.split(":")
        if(PARTS_COUNT != -1):
            if len(parts) != PARTS_COUNT or parts[1] != STATE_PREFIX or parts[0] != self.GAME_PREFIX:
                return False
            return True
        else:
            if(parts[1] != STATE_PREFIX or parts[0] != self.GAME_PREFIX):
                return False
            return True