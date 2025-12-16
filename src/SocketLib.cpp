#include<iostream>
#include <cstdint>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <errno.h>
#include <string>

static const uint32_t MAX_SIZE = 10 * 1024 * 1024;

ssize_t readAll(int sock, void* buf, size_t count){
    char* p = (char*)buf;
    size_t left = count;
    while(left){
        ssize_t n = recv(sock, p, left, 0);
        if(n == 0) return 0;
        if(n < 0){
            if(errno == EINTR) continue;
            return -1;
        }
        left -= n;
        p += n;
    }
    return count;
}

ssize_t writeAll(int sock, const void* buf, size_t count){
    const char* p = (const char*)buf;
    size_t left = count;
    while(left){
        ssize_t n = send(sock, p, left, 0);
        if(n <= 0){
            if(errno == EINTR) continue;
            return -1;
        }
        left -= n;
        p += n;
    }
    return count;
}

bool sendMessage(int sock, const std::string& payload) {
    uint32_t length = payload.size();
    if (length > MAX_SIZE) return false;

    std::string header = std::string("ML") + std::to_string(length);

    if (writeAll(sock, header.c_str(), header.size()) != (ssize_t)header.size())
        return false;

    if (writeAll(sock, payload.data(), payload.size()) != (ssize_t)payload.size())
        return false;

    return true;
}


bool recvMessage(int sock, std::string& out) {
    out.clear();

    // 1) Přijmout prefix "ML"
    char prefix[2];
    if (readAll(sock, prefix, 2) != 2)
        return false;

    if (prefix[0] != 'M' || prefix[1] != 'L') {
        std::cout << "Invalid prefix!" << std::endl;
        return false;
    }

    // 2) Číst textovou délku (neznámý počet znaků)
    std::string lenStr;
    char ch;

    // čteme dokud nenarazíme na znak, který není číslice
    while (true) {
        ssize_t r = read(sock, &ch, 1);
        if (r <= 0) return false;

        if (std::isdigit(ch)) {
            lenStr.push_back(ch);
        } else {
            // narazili jsme na první znak payloadu
            break;
        }
    }

    if (lenStr.empty()) return false;

    uint32_t length = std::stoi(lenStr);
    if (length > MAX_SIZE) return false;

    // payload = první přečtený znak + zbytek
    out.reserve(length);
    out.push_back(ch);

    // už jsme přečetli 1 znak, zbývá (length - 1)
    uint32_t remaining = length - 1;
    if (remaining > 0) {
        std::string rest(remaining, '\0');
        if (readAll(sock, &rest[0], remaining) != (ssize_t)remaining)
            return false;
        out += rest;
    }

    return true;
}

bool isSocketAlive(int sock) {
    if (sock < 0) return false;

    char buffer;
    int result = recv(sock, &buffer, 1, MSG_PEEK | MSG_DONTWAIT);

    if (result == 0) {
        return false;
    } else if (result < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            return true;
        } else {
            return false;
        }
    }
    return true;
}