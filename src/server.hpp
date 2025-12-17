#pragma once
#include <iostream>
#include <thread>
#include <vector>
#include <functional>
#include <unordered_map>
#include <queue>
#include <mutex>
#include <chrono>
#include <condition_variable>
#include <cstring>
#include <memory>
#include <unordered_set>
#include "Player.hpp"
#include "Game.hpp"

/**
 * Stavy připojení klienta
 */
enum class ConnectClientState{
    Foreign, 
    Login,
    Lobby,
    Ready,
    Disconnect
};

/**
 * Hlavní serverová třída
 */
class Server{
public:
    /**
     * Konstruktor serveru
     * @param bindAddress Adresa, na které bude server naslouchat
     * @param port Port, na kterém bude server naslouchat
     * @param roomCount Počet herních místností
     */
    Server(const std::string& bindAddress, int port, int roomCount);
    
    /**
     * Spustí server
     */
    int runServer();

    /**
     * Postará se o klienta a pokud pošle nevalidní zprávu, odpojí ho
     * @param clientSocket Socket klienta
     */
    void handleClient(int clientSocket, ConnectClientState state);    
    
    /**
     * Zpracuje přihlášení nebo znovupřipojení klienta
     * @param message Přijatá zpráva od klienta
     * @param clientSocket Socket klienta
     * @return Nový stav připojení klienta
     */
    ConnectClientState handleLoginAndReconnect(const std::string& message, const int& clientSocket);
    
    /**
     * Zpracuje požadavek na místnosti v lobby
     * @param message Přijatá zpráva od klienta
     * @param clientSocket Socket klienta
     * @return Nový stav připojení klienta
     */
    ConnectClientState handleLobbyRequest(const std::string& message, const int& clientSocket);
    
    /**
     * Zpracuje požadavek na připojení do herní místnosti
     * @param message Přijatá zpráva od klienta
     * @param clientSocket Socket klienta
     * @return Nový stav připojení klienta
     */
    ConnectClientState handleRoomRequest(const std::string& message, const int& clientSocket);

    /**
     * Zpracuje přihlášení klienta
     * @param lm Přijatá přihlašovací zpráva
     * @param clientSocket Socket klienta
     * @return Nový stav připojení klienta
     */
    ConnectClientState handleLogin(LoginMessage lm, int clientSocket);
    
    /**
     * Zpracuje znovupřipojení klienta
     * @param rm Přijatá znovupřipojovací zpráva
     * @param clientSocket Socket klienta
     * @return Nový stav připojení klienta
     */
    ConnectClientState handleReconnect(ReconnectMessage rm, int clientSocket);

    /**
     * Spustí hru v herní místnosti
     * @param game Ukazatel na herní místnost
     */
    void startGame(std::unique_ptr<Game>& game);
    
    /**
     * Rozdělí zprávu na části podle ':' a vrátí je jako vektor řetězců
     * @param message Zpráva k rozdělení
     * @return Vektor částí zprávy
     */
    std::vector<std::string> parseMessage(const std::string& message);
    
    /**
     * Uzavře spojení s klientem a vyhodí ho ze hry/místnosti
     * @param clientSocket Socket klienta
     */
    void closeAndKickClient(int clientSocket);
    
    /**
     * Zpracuje odpojení klienta
     * @param message Přijatá zpráva od klienta
     * @return True pokud bylo zpracováno úspěšně, jinak false
     */
    bool handleDisconnect(const std::string& message);
    
    /**
     * Vrátí hráče do lobby
     * @param player Hráč k vrácení do lobby
     */
    void returnPlayerToLobby(Player& player);
    
    /**
     * Odebere hráče z herní místnosti podle jeho socketu
     * @param clientSocket Socket hráče k odebrání
     */
    void removePlayerFromRoom(int clientSocket);


    /*Atributy*/
    int serverSocket;
    std::string bindAddress;
    int port;
    std::unordered_map<ConnectClientState, std::function<ConnectClientState(const std::string&, const int&)>> stateHandlers;

    /*Zámky pro herní místnosti a hráče*/
    std::mutex rooms_mutex;
    std::mutex players_mutex;
    std::mutex closed_sockets_mutex;
    std::unordered_set<int> closedSockets;
    int roomCount;
    
    std::vector<Player> activePlayers;
    std::vector<std::unique_ptr<Game>> gameRooms;
};