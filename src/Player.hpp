#pragma once
#include <iostream>
#include <chrono>

/**
 * Třída reprezentující hráče
 */
class Player{
    public:
        /**
         * Konstruktor hráče
         * @param clientSocket Socket hráče
         */
        Player(int clientSocket);
        
        /**
         * Defaultní konstruktor
         */
        Player();
        
        /**
         * Destruktor hráče
         */
        ~Player();
        
        /*Atributy hráče*/
        std::chrono::time_point<std::chrono::steady_clock> lastSeen;
        int clientSocket, role;
        std::string name; 
        bool isValid;
};