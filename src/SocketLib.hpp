#pragma once
#include <cstdint>
#include <cstddef>
#include <sys/types.h>
#include <string>
#include <iostream>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <errno.h>

/*SocketLib.hpp*/
/*Pomocná knihovna pro odesílání a přijímání zpráv přes sockety, funguje na principu prefixu "ML" následovaného délkou zprávy.*/
/*Vše řešeno zde na úrovních obalových funkcí nad sockety. Maximální velikost zprávy je 10 MB. */
/*Príklad poslané zprávy "ML16LK:LOGIN_SUCCESS"*/

/* Autor: Pavel Kratochvíle 2025 */

static const uint32_t MAX_SIZE = 10 * 1024 * 1024;

/**
 * Přečte přesný počet bajtů ze socketu.
 * @param sock Socket, ze kterého se čte.
 * @param buf Cíl pro přečtená data.
 * @param count Počet bajtů k přečtení.
 * @return Počet přečtených bajtů nebo -1 při chybě
 */
ssize_t readAll(int sock, void* buf, size_t count);

/**
 * Zapíše přesný počet bajtů na socket.
 * @param sock Socket, na který se zapisuje.
 * @param buf Zdroj dat k zápisu.
 * @param count Počet bajtů k zápisu.
 * @return Počet zapsaných bajtů nebo -1 při chybě
 */
ssize_t writeAll(int sock, const void* buf, size_t count);

/**
 * Odesílá zprávu přes socket s prefixem "ML" a délkou zprávy.
 * @param sock Socket, na který se zpráva odesílá.
 * @param payload Zpráva k odeslání.
 * @return true pokud byla zpráva úspěšně odeslána, false při chybě.
 */
bool sendMessage(int sock, const std::string& payload);

/**
 * Přijímá zprávu ze socketu, očekává prefix "ML" a délku zprávy.
 * @param sock Socket, ze kterého se zpráva přijímá.
 * @param out Cíl pro přijatou zprávu.
 * @return true pokud byla zpráva úspěšně přijata, false při chybě.
 */
bool recvMessage(int sock, std::string& out);

/**
 * Kontroluje, zda je socket stále aktivní.
 * @param sock Socket k otestování.
 * @return true pokud je socket aktivní, false pokud je uzavřený.
 */
bool isSocketAlive(int sock);
