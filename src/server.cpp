#include <iostream>
#include <thread>
#include <vector>
#include <queue>
#include <algorithm>
#include <mutex>
#include <condition_variable>
#include <cstring>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <signal.h>
#include <random>
#include <sstream>
#include <iomanip>

#include "server.hpp"
#include "SocketLib.hpp"
#include "Messages.hpp"

Server::Server(int port, int roomCount) : port(port), roomCount(roomCount) {
    stateHandlers = {
        {ConnectClientState::Foreign, [this](const std::string& message, const int& clientSocket){ return this->handleLoginAndReconnect(message, clientSocket); }},
        {ConnectClientState::Login,   [this](const std::string& message, const int& clientSocket){ return this->handleLobbyRequest(message, clientSocket); }},
        {ConnectClientState::Lobby,   [this](const std::string& message, const int& clientSocket){ return this->handleRoomRequest(message, clientSocket); }},
    };
    gameRooms = std::vector<std::unique_ptr<Game>>();
    gameRooms.reserve(roomCount);
    for(int i = 1; i <= roomCount; ++i) {
        gameRooms.emplace_back(std::make_unique<Game>(this->serverSocket, i, this));
    }
}

void Server::removePlayerFromRoom(int clientSocket) {
    for (auto& game : this->gameRooms) {
        // Idempotentní - kontroluj jestli socket ještě není 0
        if(game->playerG.clientSocket == clientSocket && clientSocket != 0){
            std::cout << "odstraňuji G z roomky" << std::endl;
            game->playerG.isValid = false;
            // Zajisti že se hra nespustí znovu pokud ještě běží timeout thread
            game->playerG = Player();
            
            // Pokud je místnost prázdná, resetuj isRunning aby se mohla spustit znovu
            if(game->playerE.clientSocket == 0 && game->playerG.clientSocket == 0){
                std::cout << "Místnost " << game->gameID << " je prázdná, resetuji isRunning" << std::endl;
                game->isRunning = false;
            }
        }
        if(game->playerE.clientSocket == clientSocket && clientSocket != 0){
            std::cout << "odstraňuji E z roomky" << std::endl;
            game->playerE.isValid = false;
            // Zajisti že se hra nespustí znovu pokud ještě běží timeout thread
            game->playerE = Player();
            
            // Pokud je místnost prázdná, resetuj isRunning aby se mohla spustit znovu
            if(game->playerE.clientSocket == 0 && game->playerG.clientSocket == 0){
                std::cout << "Místnost " << game->gameID << " je prázdná, resetuji isRunning" << std::endl;
                game->isRunning = false;
            }
        }
    }
}


void Server::handleClient(int clientSocket, ConnectClientState state) {
    while (state != ConnectClientState::Disconnect && state != ConnectClientState::Ready) {
        std::string message;
        if (!recvMessage(clientSocket, message)) {
            std::cout << "Přijamání zprávy od klienta " << clientSocket << " selhalo." << std::endl;
            closeAndKickClient(clientSocket);
            return;
        }

        if(stateHandlers.find(state) != stateHandlers.end()){
            state = stateHandlers[state](message, clientSocket);
        }
        else{
            std::cout << "Pro tento stav neexistuje obslužná metoda. Stav: " << static_cast<int>(state) << std::endl;
            closeAndKickClient(clientSocket);
            return;
        }     
    }
    
    std::cout << "Klient " << clientSocket << " dokončil handshake, state: " << static_cast<int>(state) << std::endl;
}

ConnectClientState Server::handleLoginAndReconnect(const std::string& message, const int& clientSocket){
    std::vector<std::string> parts = parseMessage(message);
    LoginMessage lm = LoginMessage(parts);
    ReconnectMessage rm = ReconnectMessage(parts);
    ConnectClientState state;
    
    if(parts[1] == START_LOGIN_PREFIX){
        state = this->handleLogin(lm, clientSocket);
    }
    else if(parts[1] == RECONNECT_REQUEST_PREFIX){
        state = this->handleReconnect(rm, clientSocket);
    }
    else{
        closeAndKickClient(clientSocket);
        return ConnectClientState::Disconnect;
    }
    return state;
}

ConnectClientState Server::handleLogin(LoginMessage lm, int clientSocket){
    if(!lm.evaluate()){
        closeAndKickClient(clientSocket);
        return ConnectClientState::Disconnect;
    }

    Player newPlayer = Player(clientSocket);
    newPlayer.name = std::string(lm.parts[2]);
    newPlayer.role = std::stoi(lm.parts[3]);
    {
        std::lock_guard<std::mutex> lock(players_mutex);
        activePlayers.push_back(newPlayer);
    }

    if(!sendMessage(clientSocket, lm.serialize())){
        closeAndKickClient(clientSocket);
        return ConnectClientState::Disconnect;
    }

    std::cout << "Přihlášen hráč." << std::endl;
    return ConnectClientState::Login;
}

ConnectClientState Server::handleReconnect(ReconnectMessage rm, int clientSocket){
    if(!rm.evaluate()){
        std::cout << "Neplatná reconnect zpráva." << std::endl;
        closeAndKickClient(clientSocket);
        return ConnectClientState::Disconnect;
    }

    std::cout << "Reconnect zpráva odeslána zpět klientovi." << std::endl;
    {
        std::lock_guard<std::mutex> lock(rooms_mutex);
        for(auto& game : gameRooms) {
            if(game->playerG.name == rm.name && game->playerG.role == rm.role && game->playerG.isValid == false && game->isRunning){
                std::cout << "Nastavuji nový socket pro hráče G při reconnectu." << std::endl;
                Player playerG = Player();
                playerG.clientSocket = clientSocket;
                playerG.role = game->playerG.role;
                playerG.name = game->playerG.name;
                game->continueGame(playerG);
                rm.confirm = true;
                rm.gameInfo = game->gameInfo;
                rm.roundNumber = game->roundNumber;
                rm.state = static_cast<int>(game->lastValidState);
            }
            if(game->playerE.name == rm.name && game->playerE.role == rm.role && game->playerE.isValid == false && game->isRunning){
                std::cout << "Nastavuji nový socket pro hráče E při reconnectu." << std::endl;
                Player playerE = Player();
                playerE.clientSocket = clientSocket;
                playerE.role = game->playerE.role;
                playerE.name = game->playerE.name;
                game->continueGame(playerE);
                rm.confirm = true;
                rm.gameInfo = game->gameInfo;
                rm.roundNumber = game->roundNumber;
                rm.state = static_cast<int>(game->lastValidState);
            }
        }
    }
    if(!sendMessage(clientSocket, rm.serialize())){
        closeAndKickClient(clientSocket);
        return ConnectClientState::Disconnect;
    }
    if(rm.confirm){
        return ConnectClientState::Ready;
    } else {
        return ConnectClientState::Foreign;
    }
}

ConnectClientState Server::handleLobbyRequest(const std::string& message, const int& clientSocket){
    std::vector<std::string> parts = parseMessage(message);
    
    std::vector<std::string> roomList;
    {
        std::lock_guard<std::mutex> lock(rooms_mutex);
        for(auto& gameptr : gameRooms) {
            roomList.push_back(std::to_string(gameptr->gameID));
        }
    }
    
    RoomListMessage rlm = RoomListMessage(parts, roomList);
    
    if(!rlm.evaluate()){
        closeAndKickClient(clientSocket);
        return ConnectClientState::Disconnect;
    }

    if(!sendMessage(clientSocket, rlm.serialize())){
        closeAndKickClient(clientSocket);
        return ConnectClientState::Disconnect;
    }

    return ConnectClientState::Lobby;
}
ConnectClientState Server::handleRoomRequest(const std::string& message, const int& clientSocket) {
    std::vector<std::string> parts = parseMessage(message);
    RoomEntryMessage remt = RoomEntryMessage(parts, true);
    RoomEntryMessage remf = RoomEntryMessage(parts, false);
    
    if (!remt.evaluate()) { 
        closeAndKickClient(clientSocket);
        std::cout << "1" << std::endl;
        return ConnectClientState::Disconnect;
    }
    int roomID = std::stoi(parts[4]);
    int role = std::stoi(parts[3]);
    {
        std::lock_guard<std::mutex> lock(rooms_mutex);
        for(auto& game : gameRooms) {
            if(game->gameID == roomID) {
                if(game->isRunning) {
                    sendMessage(clientSocket, remf.serialize());
                    std::cout << "Game is running, cant join room." << std::endl;
                    return ConnectClientState::Login;
                }
                if(role == 0 && game->playerG.isValid){
                    sendMessage(clientSocket, remf.serialize());
                    std::cout << "Cant join as player G" << std::endl;
                    return ConnectClientState::Login;
                }
                else if(role == 1 && game->playerE.isValid){
                    sendMessage(clientSocket, remf.serialize());
                    std::cout << "Cant join as player E" << std::endl;
                    return ConnectClientState::Login;
                }
                
            }
        }
    }
    {
        std::lock_guard<std::mutex> lock(rooms_mutex);
        for(auto& game : gameRooms) {
            if(game->gameID == roomID) {
                Player joiningPlayer;
                {
                    std::lock_guard<std::mutex> pl_lock(players_mutex);
                    for(int i = 0; i < activePlayers.size(); ++i) {
                        if (activePlayers[i].clientSocket == clientSocket) {
                            joiningPlayer = activePlayers[i];
                            activePlayers.erase(activePlayers.begin() + i);
                            break;
                        }
                    }
                    if(joiningPlayer.clientSocket == 0) {
                        closeAndKickClient(clientSocket);
                        std::cout << "4" << std::endl;
                        return ConnectClientState::Disconnect;
                    }
                }
                if(joiningPlayer.role == 0){
                    game->playerG = joiningPlayer;
                }
                else if(joiningPlayer.role == 1){
                    game->playerE = joiningPlayer;
                }
                sendMessage(clientSocket, remt.serialize()); 
            }
        }
    }
    return ConnectClientState::Ready;
}

std::vector<std::string> Server::parseMessage(const std::string& message){
    char delimiter = ':';
    size_t pos = 0;
    std::string token;
    std::vector<std::string> tokens;
    std::string msg = message;
    while ((pos = msg.find(delimiter)) != std::string::npos) {
        token = msg.substr(0, pos);
        tokens.push_back(token);
        msg.erase(0, pos + 1);
    }
    tokens.push_back(msg);
    return tokens;
}

void Server::handleLobbyRooms() {
    // Collect sockets to close outside of locks to avoid holding locks while closing
    std::vector<int> socketsToClose;

    {
        // Lock both players and rooms while mutating them
        std::lock_guard<std::mutex> pl_lock(players_mutex);
        std::lock_guard<std::mutex> rm_lock(rooms_mutex);

        for (auto it = activePlayers.begin(); it != activePlayers.end(); ) {
            int sock = it->clientSocket;
            if (!isSocketAlive(sock)) {
                std::cout << "Detekováno uzavřené spojení pro socket: " << sock << ", odstraňuji hráče." << std::endl;
                // remove player from any room they were in (doesn't erase rooms)
                removePlayerFromRoom(sock);
                // schedule socket to be closed outside the lock
                socketsToClose.push_back(sock);
                // remove from activePlayers
                it = activePlayers.erase(it);
            } else {
                ++it;
            }
        }
    }

    // Close sockets without holding mutexes
    for (int s : socketsToClose) {
        closeAndKickClient(s);
    }
}

void Server::handleGameRooms(){
    std::vector<std::unique_ptr<Game>*> gamesToStart;
    
    // Najdi hry ready to start - RYCHLE, s mutexem
    {
        std::lock_guard<std::mutex> roomlck(rooms_mutex);
        for(std::unique_ptr<Game>& game : gameRooms){
            if(game->isRunning == false &&
               game->playerG.isValid == true && game->playerG.clientSocket > 0 &&
               game->playerE.isValid == true && game->playerE.clientSocket > 0){
                gamesToStart.push_back(&game);
            }
        }
    }  // Mutex se uvolní tady!
    
    // Spusť hry BEZ mutexu - v separátních threadech
    for(auto* gamePtr : gamesToStart){
        std::thread gameStartThread([this, gamePtr](){
            startGame(*gamePtr);
        });
        gameStartThread.detach();
    }
}

void Server::startGame(std::unique_ptr<Game>& game){
    GameStartMessage gsmE = GameStartMessage();
    GameStartMessage gsmG = GameStartMessage();
    
    // Pošli start messages
    if(!sendMessage(game->playerE.clientSocket, gsmE.serialize())){
        closeAndKickClient(game->playerE.clientSocket);
        return;
    }
    if(!sendMessage(game->playerG.clientSocket, gsmG.serialize())){
        closeAndKickClient(game->playerG.clientSocket);
        return;
    }
    
    std::string messE, messG;
    
    // Čekej na odpovědi - NEBLOKUJE rooms_mutex!
    if(!recvMessage(game->playerE.clientSocket, messE)){
        closeAndKickClient(game->playerE.clientSocket);
        return;
    }
    if(!recvMessage(game->playerG.clientSocket, messG)){
        closeAndKickClient(game->playerG.clientSocket);
        return;
    }
    
    std::vector<std::string> partsE = parseMessage(messE);
    std::vector<std::string> partsG = parseMessage(messG);
    
    gsmE.parts = partsE;
    gsmG.parts = partsG;
    
    if(gsmG.evaluate() && gsmE.evaluate()){
        game->start();
    }
}

void Server::lobbyLoop() {
    while(true) {
        handleGameRooms();
        handleLobbyRooms();
        std::this_thread::sleep_for(std::chrono::milliseconds(50)); 
    }
}

int Server::runServer(){
    this->serverSocket = socket(AF_INET, SOCK_STREAM, 0);
    if(this->serverSocket < 0) {
        perror("socket");
        return 1;
    }

    sockaddr_in addr;
    std::memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(this->port);
    addr.sin_addr.s_addr = INADDR_ANY;

    if(bind(serverSocket, (sockaddr*)&addr, sizeof(addr)) < 0){
        perror("bind");
        return 1;
    }

    listen(serverSocket, 10);
    std::cout << "Server běží na portu " << this->port << std::endl;

    std::thread lobbyThread(&Server::lobbyLoop, this);
    lobbyThread.detach();

    

    while(true){
        int clientSocket = accept(serverSocket, nullptr, nullptr);
        if(clientSocket < 0){
            perror("accept");
            continue;
        };
        std::cout << "Nové připojení na socketu " << clientSocket << std::endl;
        std::thread clientThread(&Server::handleClient, this, clientSocket, ConnectClientState::Foreign);
        clientThread.detach();
    }
    close(serverSocket);
    return 0;
}

void Server::closeAndKickClient(int clientSocket){
    // Validace socketu
    if (clientSocket <= 0) {
        std::cout << "⚠️ Pokus o zavření neplatného socketu: " << clientSocket << std::endl;
        return;
    }
    {
        std::lock_guard<std::mutex> rm(rooms_mutex);
        removePlayerFromRoom(clientSocket);
    }
    
    std::cout << "Uzavírám spojení s klientským socketem: " << clientSocket << std::endl;
    close(clientSocket);
    return;
}

void Server::returnPlayerToLobby(Player& player) {
    {
        std::lock_guard<std::mutex> lock(players_mutex);
        activePlayers.push_back(player);
    }
    std::cout << "Hráč " << player.name << " vrácen do lobby, čeká na REQUEST_ROOMS" << std::endl;
    // Spustí handleClient se stavem Login, který očekává REQUEST_ROOMS zprávu
    std::thread clientThread(&Server::handleClient, this, player.clientSocket, ConnectClientState::Login);
    clientThread.detach();
}

int main(int argc, char* argv[]){
    // Ignore SIGPIPE so that writing to closed sockets does not terminate the process.
    signal(SIGPIPE, SIG_IGN);
    int roomCount = std::stoi(argv[1]);
    Server server(std::stoi(argv[2]), roomCount);
    server.runServer();
    return 0;
}

 