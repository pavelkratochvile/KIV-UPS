#include "Player.hpp"

/*Defaultní konstruktor*/
Player::Player(int clientSocket){
    this->clientSocket = clientSocket;
    this->role = -1;
    this->name = "";
    this->isValid = true;
}

/*Defaultní konstruktor bez parametrů*/
Player::Player(){
    this->clientSocket = 0;
    this->role = -1;
    this->name = "";
    this->isValid = false;
}

/*Destruktor*/
Player::~Player(){}