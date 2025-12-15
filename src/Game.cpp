#include <iostream>
#include <thread>
#include <vector>
#include <queue>
#include <mutex>
#include <condition_variable>
#include <cstring>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include "Game.hpp"
#include "server.hpp"

Game::Game(int serverSocket, int gameID, Server* server){
    this->serverSocket = serverSocket;
    this->gameID = gameID;
    this->server = server;
    this->kickedPlayers = 0;

    stateHandlers = {
        {GameState::Choosing, [this](const std::string& message, bool guesser) {  return this->manageMessageChoosing(message, guesser); }},
        {GameState::Evaluating, [this](const std::string& message, bool guesser) {  return this->manageMessageEvaluating(message, guesser); }},
        {GameState::Guessing, [this](const std::string& message, bool guesser) {  return this->manageMessageGuessing(message, guesser); }},
        {GameState::DissconnectedG, [this](const std::string& message, bool guesser) {  return this->manageMessageDissconnectedG(message, guesser); }},
        {GameState::DisconnectedE, [this](const std::string& message, bool guesser) {  return this->manageMessageDissconnectedE(message, guesser); }},
        {GameState::DisconnectedBoth, [this](const std::string& message, bool guesser) {  return this->manageMessageDissconnectedBoth(message, guesser); }},
    };
};

void Game::continueGame(Player& reconnectedPlayer){
    ReconnectOtherPlayerMessage ropm = ReconnectOtherPlayerMessage();
    std::cout << "Pokračuji ve hře pro hráče " << reconnectedPlayer.name << " s rolí " << reconnectedPlayer.role << std::endl;
    if(this->gameState != GameState::DisconnectedBoth){
        this->isPaused = false;
    }

    manageStateChange(lastValidState, reconnectedPlayer.role == 0);
    
    if(reconnectedPlayer.role == 0 && playerE.isValid){
        sendMessage(playerE.clientSocket, ropm.serialize());
    } 
    else if (reconnectedPlayer.role == 1 && playerG.isValid) {
        sendMessage(playerG.clientSocket, ropm.serialize());
    }

    if(reconnectedPlayer.role == 0){
        playerG.isValid = true;
        playerG = reconnectedPlayer;
        playerG.lastSeen = std::chrono::steady_clock::now();
    } 
    else {
        playerE.isValid = true;
        playerE = reconnectedPlayer;
        playerE.lastSeen = std::chrono::steady_clock::now();
    }
}


void Game::start(){
    std::cout << "Spouštím hru v místnosti " << this->gameID << std::endl;
    this->isRunning = true;
    this->isPaused = false;
    this->gameState = GameState::Choosing;
    this->lastValidState = GameState::Choosing;
    this->roundNumber = 0;
    this->kickedPlayers = 0;
    playerE.lastSeen = std::chrono::steady_clock::now();
    playerG.lastSeen = std::chrono::steady_clock::now();
    gameInfo.fill(RoundInfo());
    // Start main game loop
    this->gameThread = std::thread(&Game::game, this);
    this->gameThread.detach();

    // Start ping loops and receive loops
    this->sendThreadE = std::thread(&Game::sendPingLoopE, this);
    this->sendThreadE.detach();

    this->sendThreadG = std::thread(&Game::sendPingLoopG, this);
    this->sendThreadG.detach();

    this->recvThreadE = std::thread(&Game::receiveLoopE, this);
    this->recvThreadE.detach();

    this->recvThreadG = std::thread(&Game::receiveLoopG, this);
    this->recvThreadG.detach();

    // Additional thread to handle received pongs can be added here
    this->handleRecvPongThread = std::thread(&Game::handleReceivedPongs, this);
    this->handleRecvPongThread.detach();

    // Thread to check player timeouts
    this->checkTimeoutsThread = std::thread(&Game::checkPlayerTimeouts, this);
    this->checkTimeoutsThread.detach();
}

void Game::checkPlayerTimeouts(){
    while(this->isRunning){
        // If game is terminated or in a terminal state, stop watchdog
        if(!this->isRunning){
            break;
        }
        // Pokud někdo byl vykopnut, ignoruj timeouty (probíhá návrat do lobby)
        {
            std::lock_guard<std::mutex> lock(kickedPlayersMutex);
            if (kickedPlayers > 0) {
                std::this_thread::sleep_for(std::chrono::milliseconds(200));
                continue;
            }
        }
        auto now = std::chrono::steady_clock::now();
        auto diffE = std::chrono::duration_cast<std::chrono::seconds>(now - playerE.lastSeen).count();
        auto diffG = std::chrono::duration_cast<std::chrono::seconds>(now - playerG.lastSeen).count();
        
        if(diffE > 40){
            this->isRunning = false;
            Player playerGCopy = playerG;
            emptyRoom();
            std::cout << "Player E disconnected permanently (>40s). Ending game." << std::endl;
            {
                std::lock_guard<std::mutex> lock(gameStateMutex);
                if(gameState != GameState::DissconnectedG){
                    notifyPlayerPermanentDisconnect(this->playerE, playerGCopy);
                }
            }
        }
        else if(diffE > 7){
            if(playerE.isValid){
                manageLastValidStateChange(gameState);
                manageStateChange(GameState::DisconnectedE, false); 
                {
                    std::lock_guard<std::mutex> lock(gameStateMutex);
                    if(gameState != GameState::DissconnectedG){
                        notifyPlayerTemporaryDisconnect(playerE, playerG);
                    }
                }
                playerE.isValid = false;
                this->isPaused = true;
            }
        }
        else {
            if(!playerE.isValid && this->isRunning){
                playerE.isValid = true;
                std::cout << "✅ Player E reconnected a je znovu aktivní!" << std::endl;
            }
        }
        
        // Check Player G (stejná logika)
        if(diffG > 40){
            std::cout << "Player G disconnected permanently (>40s). Ending game." << std::endl;
            this->isRunning = false;
            Player playerEcopy = playerE;
            emptyRoom();
            {
                std::lock_guard<std::mutex> lock(gameStateMutex);
                if(gameState != GameState::DisconnectedE){
                    notifyPlayerPermanentDisconnect(this->playerG, playerEcopy);
                }
            }

        }
        else if(diffG > 7){
            if(playerG.isValid){
                manageLastValidStateChange(gameState);
                manageStateChange(GameState::DissconnectedG, true);
                {
                    std::lock_guard<std::mutex> lock(gameStateMutex);
                    if(gameState != GameState::DisconnectedE){
                        notifyPlayerTemporaryDisconnect(playerG, playerE);
                    }
                }
                playerG.isValid = false;
                this->isPaused = true;
            }
        }
        else {
            if(!playerG.isValid && this->isRunning){
                playerG.isValid = true;
                std::cout << "✅ Player G reconnected a je znovu aktivní!" << std::endl;
            }
        }
        
        // Unpause pokud oba hráči jsou zpět
        if(this->isPaused && playerE.isValid && playerG.isValid){
            this->isPaused = false;
            std::cout << "Both players active. Resuming game." << std::endl;
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
}

void Game::emptyRoom(){
    // Reset players to ensure server won't reuse sockets or consider them active
    // DŮLEŽITÉ: Neresetuj lastSeen - musí zůstat pro správný timeout detekci!
    std::cout << "⚠️  emptyRoom() volán - resetuji sockety, zachovávám lastSeen časy" << std::endl;
    
    Player reset;
    reset.clientSocket = -1;
    reset.isValid = false;
    
    // Zachovej původní lastSeen time pro oba hráče
    auto playerELastSeen = this->playerE.lastSeen;
    auto playerGLastSeen = this->playerG.lastSeen;
    
    reset.lastSeen = playerELastSeen;
    this->playerE = reset;
    
    reset.lastSeen = playerGLastSeen;
    this->playerG = reset;
}

void Game::notifyPlayerTemporaryDisconnect(Player& disconnectedPlayer, Player& activePlayer){
    TemporaryDisconnectMessage tdm = TemporaryDisconnectMessage(disconnectedPlayer);
    sendMessage(activePlayer.clientSocket, tdm.serialize());
    std::cout << "Odesílám TEMPORARY_DISCONNECT hráči " << (activePlayer.role == 0 ? "G" : "E") << std::endl;    
    bool gotConfirm = false;

    for(int i = 0; i < 20 && !gotConfirm; i++){
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        std::lock_guard<std::mutex> lock(recvDisconnectQueueMutex);
        if(!recvDisconnectMessageQueue.empty()){
            std::string responseMessage = recvDisconnectMessageQueue.front();
            recvDisconnectMessageQueue.pop();
            std::cout << "Přijato DISCONNECT_CONFIRM: " << responseMessage << std::endl;
                        
            std::vector<std::string> parts = server->parseMessage(responseMessage);
            tdm.parts = parts;
            gotConfirm = tdm.evaluate();
            if(gotConfirm){
                std::cout << "Potvrzení validní, stopuju hru." << std::endl;
            }
            break;
        }
    }
    std::cout << "Player disconnected (7-40s). Pausing, waiting for reconnect." << std::endl;
}


void Game::notifyPlayerPermanentDisconnect(Player& disconnectedPlayer, Player& activePlayer){
    PermanentDisconnectMessage pdm = PermanentDisconnectMessage(disconnectedPlayer);
    if(activePlayer.isValid && activePlayer.clientSocket > 0){
        std::cout << "Odesílám PERMANENT_DISCONNECT aktivnímu hráči" << std::endl;
        sendMessage(activePlayer.clientSocket, pdm.serialize());
    
        bool gotConfirm = false;
        for(int i = 0; i < 20 && !gotConfirm; i++){
            std::this_thread::sleep_for(std::chrono::milliseconds(30));
            std::lock_guard<std::mutex> lock(recvDisconnectQueueMutex);
            if(!recvDisconnectMessageQueue.empty()){
                std::string responseMessage = recvDisconnectMessageQueue.front();
                recvDisconnectMessageQueue.pop();
                std::cout << "Přijato DISCONNECT_CONFIRM: " << responseMessage << std::endl;

                std::vector<std::string> parts = server->parseMessage(responseMessage);
                pdm.parts = parts;
                gotConfirm = pdm.evaluate();
                this->isRunning = false;
                if(gotConfirm){
                    std::cout << "Potvrzení validní, vracím aktivního hráče do lobby" << std::endl;
                    server->returnPlayerToLobby(activePlayer);
                }
                break;
            }
        }
        if(!gotConfirm){
            std::cout << "Nepodařilo se přijmout potvrzení od aktivního hráče" << std::endl;
            server->returnPlayerToLobby(activePlayer);
        }
    }
}


bool Game::manageMessageChoosing(const std::string& message, bool guesser){
    std::vector<std::string> parts = server->parseMessage(message);
    HeartBeatMessage hbm = HeartBeatMessage(parts);
    ChoosingColorsMessage crm = ChoosingColorsMessage(parts);
    ReconnectOtherPlayerMessage ropm = ReconnectOtherPlayerMessage(parts);
    if(hbm.evaluate()){
        if(guesser){
            std::lock_guard<std::mutex> lock(recvQueueMutexG);
            recvPingMessageQueueG.push(message);
        } else {
            std::lock_guard<std::mutex> lock(recvQueueMutexE);
            recvPingMessageQueueE.push(message);
        }
        return true;
    }
    else if(crm.evaluate()){
        if(!sendMessage(playerE.clientSocket, crm.serialize())){
            std::cout << "Chyba při odesílání ChoosingColorsMessage hráči E" << std::endl;
            /* tady odpojim a ukoncim hru */
        }
        if(!sendMessage(playerG.clientSocket, crm.serialize())){
            std::cout << "Chyba při odesílání ChoosingColorsMessage hráči G" << std::endl;
            /* tady odpojim a ukoncim hru */
        }
        this->chosenColors = crm.colors;
        gameState = GameState::Guessing;
        return true;
    }
    else if(ropm.evaluate()){
        std::cout << "ReconnectOtherPlayerMessage received. From not disconnected player." << std::endl;
        return true;
    }
    return false;
}

bool Game::manageMessageGuessing(const std::string& message, bool guesser){
    std::vector<std::string> parts = server->parseMessage(message);
    HeartBeatMessage hbm = HeartBeatMessage(parts);
    GuessingColorsMessage gcm = GuessingColorsMessage(parts);
    WinGameMessage wgm = WinGameMessage(parts);
    ReconnectOtherPlayerMessage ropm = ReconnectOtherPlayerMessage(parts);
    if(hbm.evaluate()){
        if(guesser){
            std::lock_guard<std::mutex> lock(recvQueueMutexG);
            recvPingMessageQueueG.push(message);
        } else {
            std::lock_guard<std::mutex> lock(recvQueueMutexE);
            recvPingMessageQueueE.push(message);
        }
        return true;
    }

    else if(wgm.evaluate()){
        if(guesser){
            Player playerGCopy = playerG;
            this->playerG = Player();
            this->server->returnPlayerToLobby(playerGCopy);
            {
                std::lock_guard<std::mutex> lock(kickedPlayersMutex);
                kickedPlayers++;
                if (kickedPlayers >= 2) {
                    this->isRunning = false;
                }
            }
            return true;
        }
        else if(!guesser){
            Player playerECopy = playerE;
            this->playerE = Player();
            this->server->returnPlayerToLobby(playerECopy);
            {
                std::lock_guard<std::mutex> lock(kickedPlayersMutex);
                kickedPlayers++;
                if (kickedPlayers >= 2) {
                    this->isRunning = false;
                }
            }
            return true;
        }
    }

    else if(gcm.evaluate()){
        if(!sendMessage(playerE.clientSocket, gcm.serialize())){
            std::cout << "Chyba při odesílání GuessingColorsMessage hráči E" << std::endl;
            return false;
        }
        if(!sendMessage(playerG.clientSocket, gcm.serialize())){
            std::cout << "Chyba při odesílání GuessingColorsMessage hráči G" << std::endl;
            return false;
        }
        gameInfo[roundNumber].guesses = gcm.guessedColors;
        gameState = GameState::Evaluating;
        return true;
    }
    else if(ropm.evaluate()){
        std::cout << "ReconnectOtherPlayerMessage received. From not disconnected player." << std::endl;
        return true;
    }
    return false;
}

bool Game::manageMessageEvaluating(const std::string& message, bool guesser){
    std::vector<std::string> parts = server->parseMessage(message);
    HeartBeatMessage hbm = HeartBeatMessage(parts);
    EvaluationMessage em = EvaluationMessage(parts);
    ReconnectOtherPlayerMessage ropm = ReconnectOtherPlayerMessage(parts);
    if(hbm.evaluate()){
        if(guesser){
            std::lock_guard<std::mutex> lock(recvQueueMutexG);
            recvPingMessageQueueG.push(message);
        } else {
            std::lock_guard<std::mutex> lock(recvQueueMutexE);
            recvPingMessageQueueE.push(message);
        }
        return true;
    }
    else if(em.evaluate()){
        if(!sendMessage(playerE.clientSocket, em.serialize())){
            std::cout << "Chyba při odesílání EvaluationMessage hráči E" << std::endl;
            return false;
        }
        if(!sendMessage(playerG.clientSocket, em.serialize())){
            std::cout << "Chyba při odesílání EvaluationMessage hráči G" << std::endl;
            return false;
        }
        gameInfo[roundNumber].blacks = em.blacks;
        gameInfo[roundNumber].whites = em.whites;
        std::cout << "Hodnocení přijato: černých "<< em.blacks << ", bílých " << em.whites << std::endl;
        
        if(em.blacks == 4){
            WinGameMessage wgm = WinGameMessage(true);
            if(!sendMessage(playerE.clientSocket, wgm.serialize())){
                std::cout << "Chyba při odesílání WinGameMessage hráči E" << std::endl;
                return false;
            }
            if(!sendMessage(playerG.clientSocket, wgm.serialize())){
                std::cout << "Chyba při odesílání WinGameMessage hráči G" << std::endl;
                return false;
            }
        }
        else if(roundNumber > MAX_ROUNDS - 1 && em.blacks != 4){
            WinGameMessage wgm = WinGameMessage(false);
            if(!sendMessage(playerE.clientSocket, wgm.serialize())){
                std::cout << "Chyba při odesílání WinGameMessage hráči E" << std::endl;
                return false;
            }
            if(!sendMessage(playerG.clientSocket, wgm.serialize())){
                std::cout << "Chyba při odesílání WinGameMessage hráči G" << std::endl;
                return false;
            }
        }

        roundNumber++;
        gameState = GameState::Guessing;
        return true;
    }
    else if(ropm.evaluate()){
        std::cout << "ReconnectOtherPlayerMessage received. From not disconnected player." << std::endl;
        return true;
    }
    return false;
}

bool Game::manageMessageDissconnectedE(const std::string& message, bool guesser){
    std::vector<std::string> parts = server->parseMessage(message);
    GuessingColorsMessage gcm = GuessingColorsMessage(parts);
    
    if(message.find(ALIVE_PREFIX) != std::string::npos && guesser){
        std::lock_guard<std::mutex> lock(recvQueueMutexE);
        recvPingMessageQueueG.push(message);
        return true;
    }
    
    else if(message.find(PERMANENT_DISCONNECT_CONFIRM_PREFIX) != std::string::npos || 
        message.find(TEMPORARY_DISCONNECT_CONFIRM_PREFIX) != std::string::npos){
        std::lock_guard<std::mutex> lock(recvDisconnectQueueMutex);
        recvDisconnectMessageQueue.push(message);
        return true;
    }
    else if(gcm.evaluate()){
        // E je odpojený, neposíláme mu zprávu - jen G
        if(!sendMessage(playerG.clientSocket, gcm.serialize())){
            std::cout << "Chyba při odesílání GuessingColorsMessage hráči G" << std::endl;
            return false;
        }
        gameInfo[roundNumber].guesses = gcm.guessedColors;
        manageLastValidStateChange(GameState::Evaluating);
        return true;
    }
    return false;
}

bool Game::manageMessageDissconnectedG(const std::string& message, bool guesser){
    std::vector<std::string> parts = server->parseMessage(message);
    EvaluationMessage em = EvaluationMessage(parts);
    WinGameMessage wgm = WinGameMessage(parts);
    if(message.find(ALIVE_PREFIX) != std::string::npos && !guesser){
        std::lock_guard<std::mutex> lock(recvQueueMutexG);
        recvPingMessageQueueE.push(message);
        return true;
    }
    else if(message.find(PERMANENT_DISCONNECT_CONFIRM_PREFIX) != std::string::npos || 
        message.find(TEMPORARY_DISCONNECT_CONFIRM_PREFIX) != std::string::npos){
        std::lock_guard<std::mutex> lock(recvDisconnectQueueMutex);
        recvDisconnectMessageQueue.push(message);
        return true;
    }
    else if(em.evaluate()){
        if(!sendMessage(playerE.clientSocket, em.serialize())){
            std::cout << "Chyba při odesílání EvaluationMessage hráči E" << std::endl;
            return false;
        }
        gameInfo[roundNumber].blacks = em.blacks;
        gameInfo[roundNumber].whites = em.whites;
        std::cout << "Hodnocení přijato: černých "<< em.blacks << ", bílých " << em.whites << std::endl;
        
        if(em.blacks == 4){
            WinGameMessage wgm = WinGameMessage(true);
            if(!sendMessage(playerE.clientSocket, wgm.serialize())){
                std::cout << "Chyba při odesílání WinGameMessage hráči E" << std::endl;
                return false;
            }
        }
        else if(roundNumber > MAX_ROUNDS - 1 && em.blacks != 4){
            WinGameMessage wgm = WinGameMessage(false);
            if(!sendMessage(playerE.clientSocket, wgm.serialize())){
                std::cout << "Chyba při odesílání WinGameMessage hráči E" << std::endl;
                return false;
            }
        }

        roundNumber++;
        manageLastValidStateChange(GameState::Guessing);
        return true;
    }
    else if(wgm.evaluate()){
        if(!guesser){
            Player playerECopy = playerE;
            this->playerE = Player();
            this->server->returnPlayerToLobby(playerECopy);
            {
                std::lock_guard<std::mutex> lock(kickedPlayersMutex);
                kickedPlayers++;
                if (kickedPlayers >= 2) {
                    this->isRunning = false;
                }
            }
            return true;
        }
    }
    return false;
}

bool Game::manageMessageDissconnectedBoth(const std::string& message, bool guesser){
    if(message.find(PERMANENT_DISCONNECT_CONFIRM_PREFIX) != std::string::npos || 
        message.find(TEMPORARY_DISCONNECT_CONFIRM_PREFIX) != std::string::npos){
        std::lock_guard<std::mutex> lock(recvDisconnectQueueMutex);
        recvDisconnectMessageQueue.push(message);
        return true;
    }
    return false;
}

void Game::handleReceivedPongs(){
    while(this->isRunning){
        {
            std::lock_guard<std::mutex> lock(recvQueueMutexE);
            if(!recvPingMessageQueueE.empty()){
                std::string pongMessage = recvPingMessageQueueE.front();
                recvPingMessageQueueE.pop();
                this->playerE.lastSeen = std::chrono::steady_clock::now();
                std::cout << "PONG od Player E přijat, lastSeen aktualizován" << std::endl;
            }
        }
        {
            std::lock_guard<std::mutex> lock(recvQueueMutexG);
            if(!recvPingMessageQueueG.empty()){
                std::string pongMessage = recvPingMessageQueueG.front();
                recvPingMessageQueueG.pop();
                this->playerG.lastSeen = std::chrono::steady_clock::now();
                std::cout << "PONG od Player G přijat, lastSeen aktualizován" << std::endl;
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
}

void Game::sendPingLoopE(){
    while(this->isRunning){
        HeartBeatMessage hbm = HeartBeatMessage();
        if(!sendMessage(this->playerE.clientSocket, hbm.serialize())){
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            continue;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(5000));
    }
}

void Game::sendPingLoopG(){
    while(this->isRunning){
        HeartBeatMessage hbm = HeartBeatMessage();
        if(!sendMessage(this->playerG.clientSocket, hbm.serialize())){
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            continue;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(5000));
    }
}

void Game::receiveLoopE(){
    while(this->isRunning){
        std::string message;
        
        if(recvMessage(this->playerE.clientSocket, message)){
            if(message.empty()){
                continue;
            }
            bool rightReceive = stateHandlers[gameState](message, false);
            if(!rightReceive){
                this->gameState = GameState::DisconnectedE;
                this->isRunning = false;
                Player playerGcopy = playerG;
                emptyRoom();
                notifyPlayerPermanentDisconnect(this->playerE, playerGcopy);
            }
            
            {
                std::lock_guard<std::mutex> lock(kickedPlayersMutex);
                if (kickedPlayers >= 2) {
                    this->isRunning = false;
                    return;
                }
            }
        }
        else{
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
}

void Game::receiveLoopG(){
    while(this->isRunning){
        std::string message;
        if(recvMessage(this->playerG.clientSocket, message)){
            if(message.empty()){
                continue;
            }
            bool rightReceive = stateHandlers[gameState](message, true);
            if(!rightReceive){
                std::cout << "Chybná zpráva od hráče G v aktuálním stavu, ukončuji hru: "<< message << "Ve stavu: ";
                printGameState(gameState);
                std::cout << std::endl;
                this->gameState = GameState::DissconnectedG;
                this->isRunning = false;
                Player playerEcopy = playerE;
                emptyRoom();
                notifyPlayerPermanentDisconnect(this->playerG, playerEcopy);
            }
    
            {
                std::lock_guard<std::mutex> lock(kickedPlayersMutex);
                if (kickedPlayers >= 2) {
                    this->isRunning = false;
                    return;
                }
            }
        }
        else{
            // Recv selhal - watchdog to vyhodnotí podle lastSeen
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
}

void Game::manageStateChange(GameState gameState , bool isGuesserSetting){
    std::lock_guard<std::mutex> lock(gameStateMutex);
    
    if(gameState == GameState::DissconnectedG && this->gameState == GameState::DisconnectedE){
        this->gameState = GameState::DisconnectedBoth;
        return;
    }
    else if(gameState == GameState::DisconnectedE && this->gameState == GameState::DissconnectedG){
        this->gameState = GameState::DisconnectedBoth;
        return;
    }
    if(this->gameState == GameState::DisconnectedBoth && isGuesserSetting){
        std::cout << "Nastavuji stav na DisconnectedE" << std::endl;
        this->gameState = GameState::DisconnectedE;
        return;
    }
    if(this->gameState == GameState::DisconnectedBoth && !isGuesserSetting){
        std::cout << "Nastavuji stav na DissconnectedG" << std::endl;
        this->gameState = GameState::DissconnectedG;
        return;
    }
    std::cout << "Nastavuji herní stav na: ";
    printGameState(gameState);
    std::cout << std::endl;
    this->gameState = gameState;
}

void Game::manageLastValidStateChange(GameState state){
    std::lock_guard<std::mutex> lock(lastValidStateMutex);
    if(gameState != GameState::DisconnectedBoth){
        this->lastValidState = state;
    }
}

void Game::game(){
    int i = 0;
    while(this->isRunning){
        std::cout << "Current Game State: ";
        printGameState(gameState);
        std::cout << "Last Valid State: ";
        printGameState(lastValidState);
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        std::cout << "Game loop tick: " << i << std::endl;
        i++;
    }
}

void Game::printGameState(GameState gameState){
    switch(gameState){
        case GameState::Choosing:
            std::cout << "Choosing" << std::endl;
            break;
        case GameState::Guessing:
            std::cout << "Guessing" << std::endl;
            break;
        case GameState::Evaluating:
            std::cout << "Evaluating" << std::endl;
            break;
        case GameState::DissconnectedG:
            std::cout << "DissconnectedG" << std::endl;
            break;
        case GameState::DisconnectedE:
            std::cout << "DisconnectedE" << std::endl;
            break;
        case GameState::DisconnectedBoth:
            std::cout << "DisconnectedBoth" << std::endl;
            break;
        default:
            std::cout << "Unknown State" << std::endl;
            break;
    }
}
