#pragma once
#include <iostream>
#include <unordered_map>
#include <thread>
#include <queue>
#include <functional>
#include <unordered_map>
#include "Player.hpp"
#include "Messages.hpp"
#include "SocketLib.hpp"
#include <atomic>

constexpr int MAX_ROUNDS = 10;

class Server;

enum class GameState{
    Choosing = 0,
    Guessing = 1,
    Evaluating = 2,
    DissconnectedG = 3,
    DisconnectedE = 4,
    DisconnectedBoth = 5,
};

class Game{
    public:
        Game(int serverSocket, int gameID, Server* server);
        ~Game(){};
        void start();
        void continueGame(Player& reconnectedPlayer);
        void game();
        void sendPingLoopE();
        void sendPingLoopG();
        void receiveLoopE();
        void receiveLoopG();
        void handleReceivedPongs();
        void checkPlayerTimeouts();
        void handleGameMessagesE();
        void handleGameMessagesG();

        void resetToDefaultState();
        void cleanupAndReturnToLobby();
        void manageStateChange(GameState gameState, bool isGuesserSetting);
        void manageLastValidStateChange(GameState gameState);

        void notifyPlayerPermanentDisconnect(Player& disconnectedPlayer, Player& activePlayer);
        void notifyPlayerTemporaryDisconnect(Player& disconnectedPlayer, Player& activePlayer);
        void emptyRoom();
        void printGameState(GameState gameState);

        int gameID;
        int roundNumber;
        int kickedPlayers;
        std::atomic<bool> isRunning, isPaused;
        std::mutex gameStateMutex;
        std::mutex lastValidStateMutex;
        std::array<Color, 4> chosenColors;
        GameState gameState;
        GameState lastValidState;
        int serverSocket;
        Server* server;
        std::array<RoundInfo, 10> gameInfo;
    
        std::queue<std::string> recvPingMessageQueueE;
        std::mutex recvQueueMutexE;

        std::queue<std::string> recvGameMessageQueueE;
        std::mutex recvGameQueueMutexE;

        std::queue<std::string> recvPingMessageQueueG;
        std::mutex recvQueueMutexG;

        std::queue<std::string> recvGameMessageQueueG;
        std::mutex recvGameQueueMutexG;

        std::queue<std::string> recvDisconnectMessageQueue;
        std::mutex recvDisconnectQueueMutex;

        std::mutex kickedPlayersMutex;
        std::atomic<bool> disconnectHandled{false};

        std::unordered_map<GameState, std::function<bool(const std::string&, bool)>> stateHandlers;

        bool manageMessageChoosing(const std::string& message, bool guesser);
        bool manageMessageEvaluating(const std::string& message, bool guesser);
        bool manageMessageGuessing(const std::string& message, bool guesser);
        bool manageMessageDissconnectedG(const std::string& message, bool guesser);
        bool manageMessageDissconnectedE(const std::string& message, bool guesser);
        bool manageMessageDissconnectedBoth(const std::string& message, bool guesser);

        std::thread gameThread, sendThreadE, sendThreadG, recvThreadE, recvThreadG, handleRecvPongThread, checkTimeoutsThread, handleGameMessagesThreadE, handleGameMessagesThreadG; 
        Player playerG, playerE;
};