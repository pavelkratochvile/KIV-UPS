#pragma once

#include <cstdint>
#include <cstddef>
#include <sys/types.h>
#include <string>

static const uint32_t MAX_SIZE = 10 * 1024 * 1024;

ssize_t readAll(int sock, void* buf, size_t count);
ssize_t writeAll(int sock, const void* buf, size_t count);

bool sendMessage(int sock, const std::string& payload);
bool recvMessage(int sock, std::string& out);

bool isSocketAlive(int sock);
