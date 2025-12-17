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

/**
 * Maximální počet kol v jedné hře
 */
constexpr int MAX_ROUNDS = 10;
class Server;

/**
 * Stavy hry
 */
enum class GameState{
    Choosing = 0,
    Guessing = 1,
    Evaluating = 2,
    DissconnectedG = 3,
    DisconnectedE = 4,
    DisconnectedBoth = 5,
};

/**
 * Třída reprezentující jednu herní místnost
 */
class Game{
    public:
        /**
         * Konstruktor herní místnosti
         * @param serverSocket Socket serveru pro komunikaci s klienty
         * @param gameID ID herní místnosti
         * @param server Ukazatel na hlavní serverovou třídu
         */
        Game(int serverSocket, int gameID, Server* server);
        
        /**
         * Destruktor herní místnosti
         */
        ~Game(){};
        
        /**
         * Spustí hru v místnosti
         */
        void start();

        /**
        * Pokračuje ve hře pro znovupřipojeného hráče
        * @param reconnectedPlayer Hráč, který se znovu připojil
        */
        void continueGame(Player& reconnectedPlayer);
        
        /**
         * 
         */
        void game();
        
        /**
         * Posílání ping zprávy hráči E
         */
        void sendPingLoopE();
        
        /**
         * Posílání ping zprávy hráči G
         */
        void sendPingLoopG();
        
        /**
         * Přijímací smyčka pro hráče E
         */
        void receiveLoopE();
        
        /**
         * Přijímací smyčka pro hráče G
         */
        void receiveLoopG();
        
        /**
         * Zpracování přijatých pong zpráv
         */
        void handleReceivedPongs();
        
        /**
         * Kontrola timeoutů hráčů
         */
        void checkPlayerTimeouts();
        
        /**
         * Zpracování herních zpráv od hráče E
         */
        void handleGameMessagesE();
        
        /**
         * Zpracování herních zpráv od hráče G
         */
        void handleGameMessagesG();

        /**
         * Resetuje místnost do výchozího stavu
         */
        void resetToDefaultState();
        
        /**
         * Vyčistí místnost a vrátí hráče do lobby
         */
        void cleanupAndReturnToLobby();
        
        /**
         * Spravuje změnu herního stavu
         * @param gameState Nový herní stav
         * @param isGuesserSetting True pokud nastavuje hádač, false pokud ohodnocovač
         */
        void manageStateChange(GameState gameState, bool isGuesserSetting);
        
        /**
         * Spravuje změnu posledního platného herního stavu
         * @param gameState Nový poslední platný herní stav
         */
        void manageLastValidStateChange(GameState gameState);

        /**
         * Oznámí druhému hráči, že první hráč se trvale odpojil
         * @param disconnectedPlayer Hráč, který se odpojil
         * @param activePlayer Aktivní hráč, kterému se oznamuje odpojení
         */
        void notifyPlayerPermanentDisconnect(Player& disconnectedPlayer, Player& activePlayer);
        
        /**
         * Oznámí druhému hráči, že první hráč se dočasně odpojil
         * @param disconnectedPlayer Hráč, který se odpojil
         * @param activePlayer Aktivní hráč, kterému se oznamuje odpojení
         */
        void notifyPlayerTemporaryDisconnect(Player& disconnectedPlayer, Player& activePlayer);
        
        /**
         * Vyprázdní místnost
         */
        void emptyRoom();
        
        /**
         * Vytiskne herní stav do konzole
         * @param gameState Herní stav k vytištění
         */
        void printGameState(GameState gameState);


        /*
        ATRIBUTY HERNÍ MÍSTNOSTI
        */
        
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

        /**
         * Fronta pro přijmuté ping zprávy od hráče E
         */
        std::queue<std::string> recvPingMessageQueueE;
        std::mutex recvQueueMutexE;

        /**
         * Fronta pro přijmuté herní zprávy od hráče 
         */
        std::queue<std::string> recvGameMessageQueueE;
        std::mutex recvGameQueueMutexE;

        /**
         * Fronta pro přijmuté ping zprávy od hráče G
         */
        std::queue<std::string> recvPingMessageQueueG;
        std::mutex recvQueueMutexG;

        /**
         * Fronta pro přijmuté herní zprávy od hráče G
         */
        std::queue<std::string> recvGameMessageQueueG;
        std::mutex recvGameQueueMutexG;

        /**
         * Fronta pro přijmuté disconnect potvrzení
         */
        std::queue<std::string> recvDisconnectMessageQueue;
        std::mutex recvDisconnectQueueMutex;

        /**
         * Mutex pro počet vykopnutých hráčů
         */
        std::mutex kickedPlayersMutex;
        std::atomic<bool> disconnectHandled{false};

        /* Snad nejdůležitější prvek zde, mapa pro jednotlivé stavy hry a jejich zpracování */
        std::unordered_map<GameState, std::function<bool(const std::string&, bool)>> stateHandlers;

        /**
         * Metody pro zpracování zpráv v jednotlivých stavech hry
         */

        bool manageMessageChoosing(const std::string& message, bool guesser);
        bool manageMessageEvaluating(const std::string& message, bool guesser);
        bool manageMessageGuessing(const std::string& message, bool guesser);
        bool manageMessageDissconnectedG(const std::string& message, bool guesser);
        bool manageMessageDissconnectedE(const std::string& message, bool guesser);
        bool manageMessageDissconnectedBoth(const std::string& message, bool guesser);

        /**
         * Vlákna pro jednotlivé části hry
         */
        std::thread gameThread, sendThreadE, sendThreadG, recvThreadE, recvThreadG, handleRecvPongThread, checkTimeoutsThread, handleGameMessagesThreadE, handleGameMessagesThreadG; 
        Player playerG, playerE;
};