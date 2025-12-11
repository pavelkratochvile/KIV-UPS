import socket
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
import sys
import os
from GameSecond import Game
from SocketLib import *

class LogikClient:
    def __init__(self):
        self.name = None
        self.role = None
        self.socket = None
        self.connected = False
        self.GAME_PREFIX = "LK"
        self.game = None
        self.reconnected = False  
        self.reconnectData = None
    
    def connect(self, host, port):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            print("Connect - OK")
            self.connected = True
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect: {e}")
            self.socket = None
            
    def login(self):
        if not self.socket:
            messagebox.showerror("Error", "Not connected to server.")
            self.connected = False
            return

        self.login_window = tk.Tk()
        self.login_window.title("Login")

        tk.Label(self.login_window, text="Name:").grid(row=0, column=0)
        self.name_entry = tk.Entry(self.login_window)
        self.name_entry.grid(row=0, column=1)

        tk.Label(self.login_window, text="Role:").grid(row=1, column=0)
        self.role_entry = tk.Entry(self.login_window)
        self.role_entry.grid(row=1, column=1)

        self.status_label = tk.Label(self.login_window, text="", fg="blue")
        self.status_label.grid(row=3, columnspan=2, pady=5)
        
        self.login_window.protocol("WM_DELETE_WINDOW", self.on_close)
        
        tk.Button(self.login_window, text="Login", command=self.submit_login).grid(row=2, columnspan=2)
        tk.Button(self.login_window, text="Reconnect", command=self.handleReconnect).grid(row=3, columnspan=2)     
        self.login_window.mainloop()

    def handleReconnect(self):
        if(self.connected == False):
            return
        
        self.name = self.name_entry.get()
        self.role = self.role_entry.get()

        if not self.name or not self.role:
            self.status_label.config(text="Vyplň jméno i roli!", fg="red")
            return

        if(int(self.role) != 1 and int(self.role) != 0):
            self.status_label.config(text="Role musí být 0 nebo 1!", fg="red")
            return
        threading.Thread(target=self.send_and_receive_reconnect, daemon=True).start()

    def send_and_receive_reconnect(self):
        try:
            # --- krok 1: odeslání ---
            RECONNECT_PREFIX = "RECONNECT_REQUEST"
            msg = f"{self.GAME_PREFIX}:{RECONNECT_PREFIX}:{self.name}:{self.role}"
            print(msg)
            sendMessage(self.socket, msg.encode())

            # --- krok 2: čekání na odpověď ---
            self.update_status("Čekám na odpověď od serveru…", "blue")
            data_bytes = recvMessage(self.socket)
            
            if not data_bytes:
                self.connected = False
                self.update_status("❌ Server zavřel spojení.", "red")
                return
            
            data = data_bytes.decode()

            # --- krok 3: vyhodnocení ---
            if data and self.evaluate_message(data, "RECONNECT_CONFIRM", 14):
                print(f"Přihlášen jako: {self.name}")
                
                # Nastav flag aby se přeskočilo handleLobby a spustila hra
                self.reconnected = True
                
                # Vytvoř Game instanci (ale nespouštěj mainloop tady - to musí být v main threadu)
                self.game = Game(self.socket, self.name, self.role, self)
                self.reconnectData = data
                # Zavři login okno z main threadu - toto ukončí login mainloop a main() pokračuje
                self.login_window.after(0, self._close_login_window)

            elif data and self.evaluate_message(data, "RECONNECT_FAIL", 2):
                self.update_status("❌ Obnovení připojení selhalo. Jelikož asi hra neexistuje nebo ty v ni ne", "red")
                print(data)
            else:
                self.connected = False
                self.update_status("❌ Obnovení připojení selhalo nebo server neodpovídá.", "red")
                print(data)
                return
        
        except ConnectionError as e:
            self.connected = False
            self.update_status("❌ Spojení se serverem ztraceno.", "red")
            print(f"ConnectionError: {e}")
        except Exception as e:
            self.connected = False
            self.update_status(f"⚠️ Chyba: {e}", "red")
            print(f"Exception: {e}")

    def handleLobby(self):
        self.lobby_window = tk.Tk()
        self.lobby_window.title("Lobby")

        # ---- pevná velikost okna ----
        window_width = 600
        window_height = 400

        # zjištění velikosti obrazovky
        screen_width = self.lobby_window.winfo_screenwidth()
        screen_height = self.lobby_window.winfo_screenheight()

        # výpočet pozice (pro střed obrazovky)
        x_position = int((screen_width / 2) - (window_width / 2))
        y_position = int((screen_height / 2) - (window_height / 2))

        # nastavení pozice a velikosti okna
        self.lobby_window.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
        self.lobby_window.resizable(False, False)  # vypne změnu velikosti

        # ---- obsah ----
        self.status_label = tk.Label(
            self.lobby_window,
            text="Jsi v lobby a čekáš na seznam místností",
            fg="blue",
            font=("Arial", 12)
        )
        self.status_label.pack(pady=20)

        self.lobby_window.protocol("WM_DELETE_WINDOW", self.on_close)

        # spustíme načítání místností ve vlákně
        threading.Thread(target=self.choose_room, daemon=True).start()

        # ---- spustíme hlavní smyčku ----
        self.lobby_window.mainloop()


    def choose_room(self):
        try:
            # pošli žádost o seznam místností
            ROOM_REQUEST_PREFIX = "REQUEST_ROOMS"
            msg = f"{self.GAME_PREFIX}:{ROOM_REQUEST_PREFIX}:{self.name}:{self.role}"
            sendMessage(self.socket, msg.encode())

            # přijmi seznam místností
            rooms_bytes = recvMessage(self.socket)
            if not rooms_bytes:
                self.on_close()
                return

            rooms_str = rooms_bytes.decode()
            print(f"Received rooms: {rooms_str}")

            if not self.evaluate_message(rooms_str, "ROOM_LIST", -1):
                self.on_close()
                return

            # zpracování seznamu
            raw_parts = rooms_str.split(":")
            rooms_list = [p for p in raw_parts[2:] if p]
            if not rooms_list:
                self.update_status("Žádné místnosti nejsou dostupné.", "red")
                return

            # === VYČIŠTĚNÍ OKNA ===
            for widget in self.lobby_window.winfo_children():
                widget.destroy()

            # Nadpis
            tk.Label(self.lobby_window, text="Vyber místnost:", font=("Arial", 14, "bold")).pack(pady=10)

            # === SCROLL FRAME ===
            frame_container = tk.Frame(self.lobby_window)
            frame_container.pack(fill="both", expand=True, padx=10, pady=5)

            canvas = tk.Canvas(frame_container, highlightthickness=0)
            scrollbar = tk.Scrollbar(frame_container, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # === SCROLL NA KOLEČKO ===
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

            # přidáme binding
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

            # === TLAČÍTKA PRO MÍSTNOSTI ===
            for room_id in rooms_list:
                btn = tk.Button(
                    scrollable_frame,
                    text=f"Místnost {room_id}",
                    font=("Arial", 12),
                    width=25,
                    command=lambda rid=room_id: self.join_room(rid)
                )
                btn.pack(pady=5)

            # stavový text
            self.status_label = tk.Label(self.lobby_window, text="Čekám na výběr místnosti...", fg="blue")
            self.status_label.pack(pady=10)

        except Exception as e:
            self.update_status(f"⚠️ Chyba: {e}", "red")
            self.on_close()


    def join_room(self, room_id):
        try:
            JOIN_PREFIX = "JOIN_ROOM"
            join_msg = f"{self.GAME_PREFIX}:{JOIN_PREFIX}:{self.name}:{self.role}:{room_id}"
            sendMessage(self.socket, join_msg.encode())

            self.update_status(f"Čekám na potvrzení připojení k místnosti {room_id}...", "blue")

            # čekání na odpověď serveru
            data = recvMessage(self.socket)
            if not data:
                self.update_status("❌ Server neodpovídá.", "red")
                self.on_close()
                return

            data_str = data.decode()
            print(f"Join response: {data_str}")

            if "JOIN_SUCCESS" in data_str:
                self.update_status(f"✅ Připojen k místnosti {room_id}, čekáš na soupeře...", "green")
                threading.Thread(target=self.wait_for_game_start, daemon=True).start()

            elif "JOIN_FAIL" in data_str:
                self.update_status(f"⚠️ Místnost {room_id} je obsazena nebo je zde uživatel stejné role. Vyber jinou.", "orange")
                # krátká prodleva a pak znova načteme seznam místností
                self.lobby_window.after(1000, self.choose_room)

            else:
                self.update_status("❌ Neočekávaná odpověď od serveru.", "red")
                self.lobby_window.after(1500, self.choose_room)

        except Exception as e:
            self.update_status(f"⚠️ Nepodařilo se připojit: {e}", "red")
            self.lobby_window.after(1500, self.choose_room)

    def wait_for_game_start(self):
        try:
            data = recvMessage(self.socket)
            if not data:
                self.update_status("❌ Server neodpovídá.", "red")
                self.on_close()
                return
            data_str = data.decode()
            print(f"Game start message: {data_str}")
            if self.evaluate_message(data_str, "GAME_START", 2):
                message = f"{self.GAME_PREFIX}:READY_GAME_START:{self.name}:{self.role}"
                sendMessage(self.socket, message.encode())
                self.update_status("✅ Hra začíná!", "green")
                self.lobby_window.after(500, self._close_lobby_and_start_game)
            else:
                self.update_status("❌ Neočekávaná zpráva od serveru.", "red")
                self.on_close()
        except Exception as e:
            self.update_status(f"⚠️ Chyba při čekání na start hry: {e}", "red")
            self.on_close()
    
    def _close_login_window(self):
        """Pomocná metoda pro bezpečné zavření login okna z main threadu"""
        try:
            if hasattr(self, 'login_window') and self.login_window:
                self.login_window.quit()
                self.login_window.destroy()
                self.login_window = None
        except Exception as e:
            print(f"Chyba při zavírání login okna: {e}")
    
    def _close_lobby_and_start_game(self):
        """Pomocná metoda pro bezpečné zavření lobby a spuštění hry"""
        try:
            # Zavři lobby window
            if hasattr(self, 'lobby_window') and self.lobby_window:
                self.lobby_window.quit()  # Ukončí mainloop
                self.lobby_window.destroy()
                self.lobby_window = None
            
            # Krátká pauza
            import time
            time.sleep(0.1)
            
            # Spusť hru
            self.game = Game(self.socket, self.name, self.role, self)
            self.game.start()
        except Exception as e:
            print(f"Chyba při přechodu do hry: {e}")
            self.on_close()

    def submit_login(self):
        if(self.connected == False):
            return
        
        self.name = self.name_entry.get()
        self.role = self.role_entry.get()

        if not self.name or not self.role:
            self.status_label.config(text="Vyplň jméno i roli!", fg="red")
            return

        if(int(self.role) != 1 and int(self.role) != 0):
            self.status_label.config(text="Role musí být 0 nebo 1!", fg="red")
            return
        threading.Thread(target=self.send_and_receive_login, daemon=True).start()

    def send_and_receive_login(self):
        try:
            # --- krok 1: odeslání ---
            STATE_PREFIX = "START_LOGIN"
            msg = f"{self.GAME_PREFIX}:{STATE_PREFIX}:{self.name}:{self.role}"
            print(msg)
            sendMessage(self.socket, msg.encode())

            # --- krok 2: čekání na odpověď ---
            self.update_status("Čekám na odpověď od serveru…", "blue")
            data = recvMessage(self.socket).decode()

            # --- krok 3: vyhodnocení ---
            if data and self.evaluate_message(data, "LOGIN_SUCCESS", 4):
                self.update_status("✅ Přihlášení úspěšné! Jste v lobby", "green")
                print(f"Přihlášen jako: {self.name}")
                self.login_window.destroy()
            else:
                self.connected = False
                self.update_status("❌ Přihlášení selhalo nebo server neodpovídá.", "red")
                return
        except Exception as e:
            # schedule safe cleanup on GUI thread if possible
            try:
                if hasattr(self, 'login_window') and self.login_window:
                    self.login_window.after(0, self.on_close)
                elif hasattr(self, 'lobby_window') and self.lobby_window:
                    self.lobby_window.after(0, self.on_close)
                else:
                    threading.Thread(target=self.on_close, daemon=True).start()
            except Exception:
                threading.Thread(target=self.on_close, daemon=True).start()
            self.update_status(f"⚠️ Chyba: {e}", "red")

    def update_status(self, text, color):
        """Aktualizuje stavový label bezpečně z vlákna"""
        try:
            if self.status_label and hasattr(self, 'login_window') and self.login_window:
                self.status_label.after(0, lambda: self.status_label.config(text=text, fg=color))
        except:
            pass  # Okno už bylo zavřeno, ignoruj
        
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

    
    def on_close(self):
        # Označíme, že už nejsme připojeni
        self.connected = False
        # Zavřeme socket, pokud existuje
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)  # ukončí všechny směry komunikace
            except Exception:
                pass
            try:
                self.socket.close()
            except Exception:
                pass
            finally:
                self.socket = None

        # Zavřeme všechna okna pokud existují a ukončíme program
        try:
            if hasattr(self, 'login_window') and self.login_window:
                try:
                    self.login_window.destroy()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if hasattr(self, 'lobby_window') and self.lobby_window:
                try:
                    self.lobby_window.destroy()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            sys.exit(0)
        except SystemExit:
            try:
                os._exit(0)
            except Exception:
                pass

def main():
    host = "127.0.0.1"
    port = int(sys.argv[1])
    
    client = LogikClient()
    client.connect(host, port)
    client.login()
    
    # Pokud proběhl reconnect, spusť hru místo lobby
    if client.reconnected and client.game:
        client.game.continueGame(client.reconnectData)
    else:
        client.handleLobby()
    
    print("Client exited successfully.")
if __name__ == "__main__":
    main()