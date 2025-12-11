#include "Player.hpp"

Player::Player(int clientSocket){
    this->clientSocket = clientSocket;
    this->role = -1;
    this->name = "";
    this->isValid = true;
}

Player::Player(){
    this->clientSocket = 0;
    this->role = -1;
    this->name = "";
    this->isValid = false;
}

Player::~Player(){}