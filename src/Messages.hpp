#pragma once
#include <iostream>
#include <vector>
#include <array>
#include <mutex>
#include "Player.hpp"

/*Jednoduchá struktura pro ukládání informací o kolech (bez závislosti na Game.hpp)*/
class RoundInfo{
public:
    RoundInfo();
    ~RoundInfo(){};
    std::array<int, 4> guesses;
    int blacks;
    int whites;
};

/*Pomocný enum pro barvy*/
enum class Color{
    Red = 0,
    Green = 1,
    Blue = 2,
    Yellow = 3,
    Orange = 4,
    Purple = 5
};

/*Prefixy. Detailně budou vysvětleny v dokumentaci (Nachází se ve složce doc)*/
inline constexpr const char* GAME_PREFIX = "LK";

inline constexpr const char* LOGIN_PREFIX = "LOGIN_SUCCESS";
inline constexpr const char* ROOM_LIST_PREFIX = "ROOM_LIST";
inline constexpr const char* ROOM_ENTRY_SUCCESS_PREFIX = "JOIN_SUCCESS";
inline constexpr const char* ROOM_ENTRY_FAIL_PREFIX = "JOIN_FAIL";
inline constexpr const char* GAME_START_PREFIX = "GAME_START";
inline constexpr const char* HEART_BEAT_PREFIX = "PING";
inline constexpr const char* PERMANENT_DISCONNECT_PREFIX = "PERMANENT_DISCONNECT";
inline constexpr const char* TEMPORARY_DISCONNECT_PREFIX = "TEMPORARY_DISCONNECT";
inline constexpr const char* RECONNECT_CONFIRM_PREFIX = "RECONNECT_CONFIRM";
inline constexpr const char* RECONNECT_FAIL_PREFIX = "RECONNECT_FAIL";
inline constexpr const char* CHOOSING_COLORS_PREFIX = "CHOOSING_COLORS";
inline constexpr const char* GUESSING_COLORS_PREFIX = "GUESSING_COLORS";
inline constexpr const char* EVALUATION_PREFIX = "EVALUATION";
inline constexpr const char* WIN_GAME_PREFIX = "WIN_GAME";
inline constexpr const char* RECONNECT_OTHER_PLAYER_PREFIX = "RECONNECT_OTHER_PLAYER";

inline constexpr const char* START_LOGIN_PREFIX = "START_LOGIN";
inline constexpr const char* REQUEST_ROOMS_PREFIX = "REQUEST_ROOMS";
inline constexpr const char* JOIN_ROOM_PREFIX = "JOIN_ROOM";
inline constexpr const char* READY_START_PREFIX = "READY_GAME_START";
inline constexpr const char* ALIVE_PREFIX = "PONG";
inline constexpr const char* PERMANENT_DISCONNECT_CONFIRM_PREFIX = "PERMANENT_DISCONNECT_CONFIRM";
inline constexpr const char* TEMPORARY_DISCONNECT_CONFIRM_PREFIX = "TEMPORARY_DISCONNECT_CONFIRM";
inline constexpr const char* RECONNECT_REQUEST_PREFIX = "RECONNECT_REQUEST";
inline constexpr const char* CHOOSING_COLORS_CONFIRM_PREFIX = "CHOOSING_COLORS_CONFIRM";
inline constexpr const char* GUESSING_COLORS_ACK_PREFIX = "GUESSING_COLORS_ACK";
inline constexpr const char* EVALUATION_PREFIX_ACK = "EVALUATION_ACK";
inline constexpr const char* WIN_GAME_PREFIX_ACK = "WIN_GAME_ACK";
inline constexpr const char* RECONNECT_OTHER_PLAYER_PREFIX_ACK = "RECONNECT_OTHER_PLAYER_ACK";

inline constexpr const char DELIM = ':';

const int LOGIN_PARTS_LENGTH = 4;
const int LOBBY_PARTS_LENGTH = 4;
const int ROOM_PARTS_LENGTH = 5;
const int START_GAME_PARTS_LENGTH = 4;
const int HEART_BEAT_PARTS_LENGTH = 4;
const int PERMANENT_DISCONNECT_PARTS_LENGTH = 4;
const int TEMPORARY_DISCONNECT_PARTS_LENGTH = 4;
const int RECONNECT_PARTS_LENGTH = 4;
const int CHOOSING_COLORS_PARTS_LENGTH = 3;
const int GUESSING_COLORS_PARTS_LENGTH = 3;
const int EVALUATION_PARTS_LENGTH = 4;
const int WIN_GAME_PARTS_LENGTH = 2;
const int RECONNECT_OTHER_PLAYER_PARTS_LENGTH = 2;


/**
 * Šablona základní třídy pro zprávy
 */
class Message {
public:
    virtual ~Message() = default;
    virtual std::string serialize() const = 0;
    virtual bool evaluate() { return true; }
};

// -------------------------------------------------
// LoginMessage
// - Zpráva pro přihlášení hráče
// -------------------------------------------------
class LoginMessage : public Message {
public:
    LoginMessage(std::vector<std::string>& parts);
    std::string serialize() const override;
    bool evaluate() override;
    std::vector<std::string> parts;

private:
    std::string name;
    int role;
};


// -------------------------------------------------
// RoomListMessage
// - Zpráva pro seznam místností v lobby
// -------------------------------------------------
class RoomListMessage : public Message {
public:
    RoomListMessage(std::vector<std::string>& parts, std::vector<std::string>& roomList);
    std::string serialize() const override;
    bool evaluate() override;
private:
    std::vector<std::string> roomList;
    std::vector<std::string> parts;
};


// -------------------------------------------------
// RoomEntryMessage
// - Zpráva pro vstup do místnosti
// -------------------------------------------------
class RoomEntryMessage : public Message {
public:
    RoomEntryMessage(std::vector<std::string>& parts, bool type);
    std::string serialize() const override;
    bool evaluate() override;
private:
    std::vector<std::string> parts;
    bool type;
};

// -------------------------------------------------
// GameStartMessage
// - Zpráva pro start hry
// -------------------------------------------------
class GameStartMessage : public Message {
public:
    GameStartMessage(std::string otherPlayerName); 
    std::string serialize() const override;
    bool evaluate() override;
    std::vector<std::string> parts;
    std::string otherPlayerName;
};

// -------------------------------------------------
// HeartBeatMessage
// - Zpráva pro udržení spojení
// -------------------------------------------------
class HeartBeatMessage : public Message {
public:
    HeartBeatMessage(std::vector<std::string> parts);
    HeartBeatMessage();
    std::string serialize() const override;
    bool evaluate() override;
    std::vector<std::string> parts;
};

// -------------------------------------------------
// Permanent disconnect message
// - Zpráva pro trvalé odpojení hráče
// -------------------------------------------------
class PermanentDisconnectMessage : public Message {
public:
    PermanentDisconnectMessage(Player& disconnectedPlayer);
    PermanentDisconnectMessage(std::vector<std::string>& parts);
    std::string serialize() const override;
    bool evaluate() override;
    std::vector<std::string> parts;
    Player disconnectedPlayer;
};

// -------------------------------------------------
// Temporary disconnect message
// - Zpráva pro dočasné odpojení hráče
// -------------------------------------------------
class TemporaryDisconnectMessage : public Message {
public:
    TemporaryDisconnectMessage(Player& disconnectedPlayer);
    TemporaryDisconnectMessage(std::vector<std::string>& parts);
    std::string serialize() const override;
    bool evaluate() override;
    std::vector<std::string> parts;
    Player disconnectedPlayer;;
};

// -------------------------------------------------
// Reconnect message
// - Zpráva pro reconnect hráče
// -------------------------------------------------
class ReconnectMessage : public Message {
public:
    ReconnectMessage(std::vector<std::string>& parts);
    ReconnectMessage(){};
    ~ReconnectMessage() {}
    std::string serialize() const override;
    bool evaluate() override;
    bool confirm;
    std::vector<std::string> parts;
    std::array<RoundInfo, 10> gameInfo;
    int roundNumber;
    int state;
    std::string name;
    std::string otherPlayerName;
    std::array<Color, 4> secretColors;
    int role;
};

// -------------------------------------------------
// ChoosingColorsMessage message
// - Zpráva pro výběr barev hádačem
// -------------------------------------------------
class ChoosingColorsMessage : public Message {
public:    
    ChoosingColorsMessage(std::vector<std::string>& parts);
    ChoosingColorsMessage();
    ~ChoosingColorsMessage();
    std::string serialize() const override;
    bool evaluate() override;
    std::vector<std::string> parts;
    std::array<Color, 4> colors;
};

// -------------------------------------------------
// GuessingColorsMessage message
// - Zpráva pro hádání barev ohodnocovačem
// -------------------------------------------------
class GuessingColorsMessage : public Message {
public:    
    GuessingColorsMessage(std::vector<std::string>& parts);
    GuessingColorsMessage();
    ~GuessingColorsMessage();
    std::string serialize() const override;
    bool evaluate() override;
    std::vector<std::string> parts;
    std::array<int, 4> guessedColors;
};

// -------------------------------------------------
// EvaluationMessage message
// - Zpráva pro hodnocení hádání ohodnocovačem
// -------------------------------------------------
class EvaluationMessage : public Message {
public:    
    EvaluationMessage(std::vector<std::string>& parts);
    EvaluationMessage();
    ~EvaluationMessage();
    std::string serialize() const override;
    bool evaluate() override;
    std::vector<std::string> parts;
    int blacks;
    int whites;
};

// -------------------------------------------------
// WinGameMessage message
// - Zpráva při ukončení hry, posílá se jak výherci tak poraženému
// -------------------------------------------------
class WinGameMessage : public Message {
public:
    WinGameMessage(std::vector<std::string>& parts, bool isGuesser);
    WinGameMessage(std::vector<std::string>& parts);
    WinGameMessage(bool isGuesser);
    ~WinGameMessage();
    std::string serialize() const override;
    bool evaluate() override;
    std::vector<std::string> parts;
    bool isGuesser;
};

// -------------------------------------------------
// ReconnectOtherPlayer message
// - Zpráva pro reconnect druhého hráče
// -------------------------------------------------
class ReconnectOtherPlayerMessage : public Message {
public:
    ReconnectOtherPlayerMessage();
    ReconnectOtherPlayerMessage(std::vector<std::string>& parts);
    ~ReconnectOtherPlayerMessage();
    std::string serialize() const override;
    bool evaluate() override;
    std::vector<std::string> parts;
};