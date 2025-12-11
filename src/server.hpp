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

enum class ConnectClientState{
    Foreign, 
    Login,
    Lobby,
    Ready,
    Disconnect
};

class Server{
public:
    Server(int port, int roomCount);
    int runServer();

    void handleClient(int clientSocket, ConnectClientState state);    
    ConnectClientState handleLoginAndReconnect(const std::string& message, const int& clientSocket);
    ConnectClientState handleLobbyRequest(const std::string& message, const int& clientSocket);
    ConnectClientState handleRoomRequest(const std::string& message, const int& clientSocket);

    ConnectClientState handleLogin(LoginMessage lm, int clientSocket);
    ConnectClientState handleReconnect(ReconnectMessage rm, int clientSocket);

    void handleLobbyRooms();
    void handleGameRooms();
    void startGame(std::unique_ptr<Game>& game);
    void lobbyLoop();
    std::vector<std::string> parseMessage(const std::string& message);
    void closeAndKickClient(int clientSocket);
    bool handleDisconnect(const std::string& message);
    void returnPlayerToLobby(Player& player);
    void removePlayerFromRoom(int clientSocket);

    int serverSocket;
    int port;
    std::unordered_map<ConnectClientState, std::function<ConnectClientState(const std::string&, const int&)>> stateHandlers;

    std::mutex rooms_mutex;
    std::mutex players_mutex;
    // Track sockets already closed to avoid double-close and races
    std::mutex closed_sockets_mutex;
    std::unordered_set<int> closedSockets;
    int roomCount;
    
    std::vector<Player> activePlayers;
    std::vector<std::unique_ptr<Game>> gameRooms;
};