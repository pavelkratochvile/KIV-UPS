#include "Messages.hpp"
#include <cstring>

RoundInfo::RoundInfo(){
    guesses = {6,6,6,6};
    blacks = 0;
    whites = 0;
}

LoginMessage::LoginMessage(std::vector<std::string>& parts){
    this->parts = parts;
    this->name = std::string(parts[2]);
    this->role = std::stoi(parts[3]);
}

std::string LoginMessage::serialize() const{
    return (std::string(GAME_PREFIX) + DELIM + std::string(LOGIN_PREFIX) + DELIM + this->name + DELIM + std::to_string(this->role));
}

RoomListMessage::RoomListMessage(std::vector<std::string>& parts, std::vector<std::string>& roomList){
    this->parts = parts;
    this->roomList = roomList;
}

std::string RoomListMessage::serialize() const{
    std::string messageRooms = std::string(GAME_PREFIX) + DELIM + ROOM_LIST_PREFIX + DELIM;
    
    for(size_t i = 0; i < roomList.size(); ++i) {
        messageRooms += roomList[i];;
        if(i != roomList.size() - 1) {
            messageRooms += DELIM;
        }
    }
    return messageRooms;
}

RoomEntryMessage::RoomEntryMessage(std::vector<std::string>& parts, bool type){
    this->parts = parts;
    this->type = type;
}

std::string RoomEntryMessage::serialize() const{
    std::string fullMessage;
    if(this->type == true){
        fullMessage = std::string(GAME_PREFIX) + DELIM + std::string(ROOM_ENTRY_SUCCESS_PREFIX);
    }
    else if(this->type == false){
        fullMessage = std::string(GAME_PREFIX) + DELIM + std::string(ROOM_ENTRY_FAIL_PREFIX);
    }
    return fullMessage;
}

bool LoginMessage::evaluate(){
    if(parts.size() != LOGIN_PARTS_LENGTH){
        return false;
    }
    
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];
    std::string name = parts[2];
    int role = std::stoi(parts[3]);

    if(gamePrefix != GAME_PREFIX || statePrefix != START_LOGIN_PREFIX || (role !=0 && role !=1)){
        return false;
    }
    return true;
}

bool RoomListMessage::evaluate(){
    if(parts.size() != LOBBY_PARTS_LENGTH){
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];
    std::string name = parts[2];
    int roomID = std::stoi(parts[3]);

    if(gamePrefix != GAME_PREFIX || statePrefix != REQUEST_ROOMS_PREFIX){
        return false;
    }
    return true;
}

bool RoomEntryMessage::evaluate(){
    if (parts.size() != ROOM_PARTS_LENGTH) {
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];
    std::string name = parts[2];
    int role = std::stoi(parts[3]);
    int roomID = std::stoi(parts[4]);

    if (gamePrefix != GAME_PREFIX || statePrefix != JOIN_ROOM_PREFIX) {
        return false;
    }
    return true;
}

// -------------------------------------------------
// GameStartMessage
// -------------------------------------------------
GameStartMessage::GameStartMessage(std::string otherPlayerName){
    this->otherPlayerName = otherPlayerName;
}

std::string GameStartMessage::serialize() const{
    return std::string(GAME_PREFIX) + DELIM + std::string(GAME_START_PREFIX) + DELIM + this->otherPlayerName;
}

bool GameStartMessage::evaluate(){
    if(parts.size() != START_GAME_PARTS_LENGTH){
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];
    std::string name = parts[2];
    int role = std::stoi(parts[3]);

    if (gamePrefix != GAME_PREFIX || statePrefix != READY_START_PREFIX) {
        return false;
    }
    return true;
}

// -------------------------------------------------
// HeartBeatMessage
// -------------------------------------------------
HeartBeatMessage::HeartBeatMessage(std::vector<std::string> parts){
    this->parts = parts;
}

HeartBeatMessage::HeartBeatMessage(){
    
}

std::string HeartBeatMessage::serialize() const {
    return std::string(GAME_PREFIX) + DELIM + std::string(HEART_BEAT_PREFIX);
}

bool HeartBeatMessage::evaluate(){
    if(parts.size() != HEART_BEAT_PARTS_LENGTH){
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];
    std::string name = parts[2];
    int role = std::stoi(parts[3]);

    if (gamePrefix != GAME_PREFIX || statePrefix != ALIVE_PREFIX) {
        return false;
    }
    return true;
}

// -------------------------------------------------
// PermanentDisconnectMessage
// -------------------------------------------------
PermanentDisconnectMessage::PermanentDisconnectMessage(Player& disconnectedPlayer){
    this->disconnectedPlayer = disconnectedPlayer;
}

std::string PermanentDisconnectMessage::serialize() const{
    return std::string(GAME_PREFIX) + DELIM + std::string(PERMANENT_DISCONNECT_PREFIX) + DELIM + disconnectedPlayer.name + DELIM + std::to_string(disconnectedPlayer.role);
}

bool PermanentDisconnectMessage::evaluate(){
    if(parts.size() != PERMANENT_DISCONNECT_PARTS_LENGTH){
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];
    std::string name = parts[2];
    int role = std::stoi(parts[3]);

    if (gamePrefix != GAME_PREFIX || statePrefix != PERMANENT_DISCONNECT_CONFIRM_PREFIX) {
        return false;
    }
    return true;
}

// -------------------------------------------------
// TemporaryDisconnectMessage
// -------------------------------------------------
TemporaryDisconnectMessage::TemporaryDisconnectMessage(Player& disconnectedPlayer){
    this->disconnectedPlayer = disconnectedPlayer;
}

std::string TemporaryDisconnectMessage::serialize() const{
    return std::string(GAME_PREFIX) + DELIM + std::string(TEMPORARY_DISCONNECT_PREFIX) + DELIM + disconnectedPlayer.name + DELIM + std::to_string(disconnectedPlayer.role);
}

bool TemporaryDisconnectMessage::evaluate(){
    if(parts.size() != TEMPORARY_DISCONNECT_PARTS_LENGTH){
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];
    std::string name = parts[2];
    int role = std::stoi(parts[3]);

    if (gamePrefix != GAME_PREFIX || statePrefix != TEMPORARY_DISCONNECT_CONFIRM_PREFIX) {
        return false;
    }
    return true;
}

// -------------------------------------------------
// ReconnectMessage
// -------------------------------------------------
ReconnectMessage::ReconnectMessage(std::vector<std::string>& parts){
    this->parts = parts;
    this->confirm = false;
}

std::string ReconnectMessage::serialize() const{
    if(this->confirm){
        std::string message = std::string(GAME_PREFIX) + DELIM + std::string(RECONNECT_CONFIRM_PREFIX) + DELIM + std::to_string(this->roundNumber) + DELIM;
        for(size_t i = 0; i < this->gameInfo.size(); i++){
            const RoundInfo& ri = this->gameInfo[i];
            for(size_t j = 0; j < ri.guesses.size(); j++){
                message += std::to_string(ri.guesses[j]);
            }
            message += std::to_string(ri.blacks) + std::to_string(ri.whites);
            message += DELIM;
        }
        message += std::to_string(this->state) + DELIM + this->otherPlayerName + DELIM;
        
        for(Color c : this->secretColors){
            message += std::to_string(static_cast<int>(c));
        }

        return message;
    }
    else{
        return std::string(GAME_PREFIX) + DELIM + std::string(RECONNECT_FAIL_PREFIX);
    }
   // pak jeste poslu nekdy stav hry atd... ale tedka fakt ne
}

bool ReconnectMessage::evaluate(){
    if(parts.size() != RECONNECT_PARTS_LENGTH){
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];
    this->name = parts[2];
    this->role = std::stoi(parts[3]);

    if (gamePrefix != GAME_PREFIX || statePrefix != RECONNECT_REQUEST_PREFIX) {
        return false;
    }
    return true;
}

// -------------------------------------------------
// ChoosingColorsMessage message
// -------------------------------------------------

ChoosingColorsMessage::ChoosingColorsMessage(std::vector<std::string>& parts){
    this->parts = parts;
}

ChoosingColorsMessage::ChoosingColorsMessage(){

}

ChoosingColorsMessage::~ChoosingColorsMessage(){

}
std::string ChoosingColorsMessage::serialize() const{
    return std::string(GAME_PREFIX) + DELIM + std::string(CHOOSING_COLORS_CONFIRM_PREFIX) + DELIM;
}

bool ChoosingColorsMessage::evaluate(){
    if(parts.size() != CHOOSING_COLORS_PARTS_LENGTH){
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];
    std::string colors = parts[2];

    if (gamePrefix != GAME_PREFIX || statePrefix != CHOOSING_COLORS_PREFIX) {
        return false;
    }
    if(colors.length() != 4){
        return false;
    }
    for (int i = 0; i < 4; ++i) {
        unsigned char c = static_cast<unsigned char>(colors[i]);
        if (c < '0' || c > '5') {
            return false;
        }
        int colorInt = c - '0';
        this->colors[i] = static_cast<Color>(colorInt);
    }
    return true;
}

// -------------------------------------------------
// GuessingColorsMessage message
// -------------------------------------------------
GuessingColorsMessage::GuessingColorsMessage(std::vector<std::string>& parts){
    this->parts = parts;
}
GuessingColorsMessage::GuessingColorsMessage(){

}
GuessingColorsMessage::~GuessingColorsMessage(){}

std::string GuessingColorsMessage::serialize() const{
    std::string message = "";
    for (const auto& color : guessedColors){
        message += std::to_string(static_cast<int>(color));
    }
    return std::string(GAME_PREFIX) + DELIM + std::string(GUESSING_COLORS_ACK_PREFIX) + DELIM + message;
}   
bool GuessingColorsMessage::evaluate(){
    if(parts.size() != GUESSING_COLORS_PARTS_LENGTH){
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];
    std::string guessed = parts[2];

    if (gamePrefix != GAME_PREFIX || statePrefix != GUESSING_COLORS_PREFIX) {
        return false;
    }
    if(guessed.length() != 4){
        return false;
    }
    for (int i = 0; i < 4; ++i) {
        unsigned char c = static_cast<unsigned char>(guessed[i]);
        if (c < '0' || c > '5') {
            return false;
        }
        int colorInt = c - '0';
        this->guessedColors[i] = colorInt;
    }
    return true;
}

// -------------------------------------------------
// EvaluationMessage message
// -------------------------------------------------
EvaluationMessage::EvaluationMessage(std::vector<std::string>& parts){
    this->parts = parts;
}
EvaluationMessage::EvaluationMessage(){
}
EvaluationMessage::~EvaluationMessage(){}   

std::string EvaluationMessage::serialize() const{
    return std::string(GAME_PREFIX) + DELIM + std::string(EVALUATION_PREFIX_ACK) + DELIM + std::to_string(blacks) + DELIM + std::to_string(whites);
}

bool EvaluationMessage::evaluate(){
    if(parts.size() != EVALUATION_PARTS_LENGTH){
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];
    this->blacks = std::stoi(parts[2]);
    this->whites = std::stoi(parts[3]);

    if (gamePrefix != GAME_PREFIX || statePrefix != EVALUATION_PREFIX) {
        return false;
    }
    return true;
}

// -------------------------------------------------
// WinGameMessage message
// -------------------------------------------------
WinGameMessage::WinGameMessage(std::vector<std::string>& parts, bool isGuesser){
    this->parts = parts;
}
WinGameMessage::WinGameMessage(bool isGuesser){
    this->isGuesser = isGuesser;
}
WinGameMessage::WinGameMessage(std::vector<std::string>& parts){
    this->parts = parts;
}
WinGameMessage::~WinGameMessage(){}

std::string WinGameMessage::serialize() const{
    return std::string(GAME_PREFIX) + DELIM + std::string(WIN_GAME_PREFIX) + DELIM + (isGuesser ? "0" : "1");
}

bool WinGameMessage::evaluate(){
    if(parts.size() != WIN_GAME_PARTS_LENGTH){
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];

    if (gamePrefix != GAME_PREFIX || statePrefix != WIN_GAME_PREFIX_ACK) {
        return false;
    }
    return true;
}

// -------------------------------------------------
// ReconnectOtherPlayer message
// -------------------------------------------------
ReconnectOtherPlayerMessage::ReconnectOtherPlayerMessage(){

}
ReconnectOtherPlayerMessage::ReconnectOtherPlayerMessage(std::vector<std::string>& parts){
    this->parts = parts;
}
ReconnectOtherPlayerMessage::~ReconnectOtherPlayerMessage(){}
std::string ReconnectOtherPlayerMessage::serialize() const{
    return std::string(GAME_PREFIX) + DELIM + std::string(RECONNECT_OTHER_PLAYER_PREFIX);
}

bool ReconnectOtherPlayerMessage::evaluate(){
    if(parts.size() != RECONNECT_OTHER_PLAYER_PARTS_LENGTH){
        return false;
    }
    std::string gamePrefix = parts[0];
    std::string statePrefix = parts[1];

    std::cout << "Evaluating ReconnectOtherPlayerMessage se vole nekde udelala: " << gamePrefix << " , " << statePrefix << std::endl;

    if (gamePrefix != GAME_PREFIX || statePrefix != RECONNECT_OTHER_PLAYER_PREFIX_ACK) {
        return false;
    }
    return true;
}