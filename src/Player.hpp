#pragma once
#include <iostream>
#include <chrono>

class Player{
    public:
        Player(int clientSocket);
        Player();
        ~Player();
        // 0 je hádač, 1 je ohodnocovač
        std::chrono::time_point<std::chrono::steady_clock> lastSeen;
        int clientSocket, role;
        std::string name; 
        bool isValid;
};