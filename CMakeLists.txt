cmake_minimum_required(VERSION 3.10)
project(MyGameServer)

# Použijeme C++17
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Přidáme zdrojové soubory
set(SOURCES
    src/server.cpp
    src/Player.cpp
    src/Game.cpp
    src/Messages.cpp
    src/SocketLib.cpp
)

# Vytvoříme spustitelný soubor
add_executable(server ${SOURCES})