/*
 * sys_monitor.cpp  –  Android ADB 자원 모니터 (로그 파일 누적)
 *   • 15 초마다 메모리·CPU·최다 PSS 프로세스 수집 → 단일 로그 파일에 append
 *   • 임계값(메모리 70 %, CPU 50 %) 넘으면 콘솔에 [HIGH] 알림
 *   • 스페이스바 → 로딩 스피너 후 즉시 스냅샷 출력 + 로그 파일에도 append
 *
 * 빌드: g++ -std=c++17 -O2 -pthread sys_monitor.cpp -o sys_monitor
 */

#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <fstream>
#include <regex>
#include <string>
#include <thread>
#include <chrono>
#include <algorithm>
#include <iomanip>
#include <mutex>
#include <shared_mutex>
#include <sstream>
#include <atomic>
#include <ctime>

#ifdef _WIN32
  #include <conio.h>
#else
  #include <termios.h>
  #include <unistd.h>
  #include <fcntl.h>
#endif

constexpr double MEM_LIMIT_PCT = 70.0;
constexpr double CPU_LIMIT_PCT = 50.0;
constexpr int    POLL_SEC      = 15;
const std::string LOG_FILE    = "monitor2.log";
const std::string ADB_SERIAL  = "R9TR90M8TWZ";  // 고정 serial 번호

struct Usage {
    size_t usedMB = 0, totalMB = 0;
    double memPct = 0.0;
    size_t cpuSum = 0;
    double cpuPct = 0.0;
    std::string topPkg;
    double      topPct = 0.0;
};

Usage              latest;
std::shared_mutex  latestMtx;
std::atomic<bool>  busy{false}, stopSpinner{false};

std::string nowStr() {
    using namespace std::chrono;
    std::time_t t = system_clock::to_time_t(system_clock::now());
    std::tm lt{};
#ifdef _WIN32
    localtime_s(&lt, &t);
#else
    localtime_r(&t, &lt);
#endif
    char buf[20];
    strftime(buf, sizeof(buf), "%F %T", &lt);
    return buf;
}

size_t toKB(std::string s) {
    s.erase(std::remove(s.begin(), s.end(), ','), s.end());
    return std::stoul(s);
}

void parseMeminfo(const std::string& dump, Usage& u) {
    static const std::regex rTot(R"(Total RAM:\s+([\d,]+)K)", std::regex::icase);
    static const std::regex rUse(R"(Used RAM:\s+([\d,]+)K)",  std::regex::icase);
    std::smatch m;
    if (std::regex_search(dump, m, rTot)) u.totalMB = toKB(m[1]) / 1024;
    if (std::regex_search(dump, m, rUse)) u.usedMB  = toKB(m[1]) / 1024;
    if (u.totalMB) u.memPct = u.usedMB * 100.0 / u.totalMB;
}

bool parseMemFallback(const std::string& dump, Usage& u) {
    std::regex rTot(R"(MemTotal:\s+(\d+)\s+kB)"), rAva(R"(MemAvailable:\s+(\d+)\s+kB)");
    std::smatch m1, m2;
    if (std::regex_search(dump, m1, rTot) && std::regex_search(dump, m2, rAva)) {
        size_t totKB = std::stoul(m1[1]), avaKB = std::stoul(m2[1]);
        u.totalMB = totKB / 1024;
        u.usedMB  = (totKB - avaKB) / 1024;
        if (u.totalMB) u.memPct = u.usedMB * 100.0 / u.totalMB;
        return true;
    }
    return false;
}

void parseTopProcess(const std::string& dump, Usage& u) {
    static const std::regex rHdr(R"(Total PSS by process:)", std::regex::icase);
    static const std::regex rLine(R"(^\s*([\d,]+)K:\s+(\S+))");
    std::smatch m; bool in=false;
    size_t maxKB=0; std::string maxPkg;
    std::istringstream ss(dump); std::string line;
    while (std::getline(ss, line)) {
        if (!in) { if (std::regex_search(line, rHdr)) in = true; continue; }
        if (line.empty()) break;
        if (std::regex_search(line, m, rLine)) {
            size_t kb = toKB(m[1]);
            if (kb > maxKB) { maxKB = kb; maxPkg = m[2]; }
        }
    }
    if (maxKB && u.usedMB) {
        u.topPkg = maxPkg;
        u.topPct = (maxKB/1024.0) / u.usedMB * 100.0;
    }
}

void parseTopCPU(const std::string& dump, Usage& u) {
    static const std::regex rCPU(R"((\d+)%cpu\s+(\d+)%user\s+(\d+)%nice\s+(\d+)%sys)",
                                std::regex::icase);
    std::smatch m;
    if (std::regex_search(dump, m, rCPU)) {
        size_t cap = std::stoul(m[1]), usr = std::stoul(m[2]);
        size_t nic = std::stoul(m[3]), sys = std::stoul(m[4]);
        u.cpuSum = usr + nic + sys;
        if (cap) u.cpuPct = u.cpuSum * 100.0 / cap;
    }
}

Usage collect(const Usage& prev) {
    Usage u;

    if (FILE* fp = popen(("adb -s " + ADB_SERIAL + " shell dumpsys meminfo").c_str(), "r")) {
        std::string out; char buf[512];
        while (fgets(buf, sizeof(buf), fp)) out += buf;
        pclose(fp);
        parseMeminfo(out, u);
        parseTopProcess(out, u);
    }

    if (u.totalMB == 0 || u.usedMB == 0) {
        if (FILE* fp = popen(("adb -s " + ADB_SERIAL + " shell cat /proc/meminfo").c_str(), "r")) {
            std::string out; char buf[512];
            while (fgets(buf, sizeof(buf), fp)) out += buf;
            pclose(fp);
            if (!parseMemFallback(out, u)) u = prev;
        } else {
            u = prev;
        }
    }

    if (FILE* fp = popen(("adb -s " + ADB_SERIAL + " shell top -n 1 -b").c_str(), "r")) {
        std::string out; char buf[512];
        while (fgets(buf, sizeof(buf), fp)) out += buf;
        pclose(fp);
        parseTopCPU(out, u);
    }

    return u;
}

void writeLog(const Usage& u) {
    std::ofstream ofs(LOG_FILE, std::ios::app);
    if (!ofs) {
        std::cerr << "Failed to open log file\n";
        return;
    }
    ofs << "[" << nowStr() << "] MEM "
        << std::fixed << std::setprecision(1) << u.memPct << "% ("
        << u.usedMB << "/" << u.totalMB << " MB, "
        << u.topPkg << ", "
        << std::fixed << std::setprecision(1) << u.topPct << "%) | CPU "
        << u.cpuPct << "% per‑core (" << u.cpuSum << "% sum)\n";
}

void alertMem(const Usage& u) {
    std::cerr << "[" << nowStr() << "] MEM HIGH "
              << std::fixed << std::setprecision(4) << u.memPct
              << "% (" << u.usedMB << "/" << u.totalMB << " MB)\n";
}
void alertCPU(const Usage& u) {
    std::cerr << "[" << nowStr() << "] CPU HIGH "
              << std::fixed << std::setprecision(4) << u.cpuPct
              << "% per‑core (" << u.cpuSum << "% sum)\n";
}

void spinnerThread() {
    const char glyph[4] = {'|','/','-','\\'};
    size_t idx = 0;
    while (!stopSpinner.load()) {
        std::cout << '\r' << "[LOADING] " << glyph[idx++ % 4] << std::flush;
        std::this_thread::sleep_for(std::chrono::milliseconds(120));
    }
    std::cout << '\r' << std::string(20, ' ') << '\r' << std::flush;
}

void keyListener() {
#ifndef _WIN32
    termios orig, raw;
    tcgetattr(STDIN_FILENO, &orig);
    raw = orig;
    raw.c_lflag &= ~(ICANON | ECHO);
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw);
    fcntl(STDIN_FILENO, F_SETFL,
          fcntl(STDIN_FILENO, F_GETFL) | O_NONBLOCK);
#endif
    while (true) {
#ifdef _WIN32
        if (_kbhit() && _getch()==' ')
#else
        char c;
        if (read(STDIN_FILENO, &c, 1)==1 && c==' ')
#endif
        {
            if (busy.exchange(true)) continue;
            stopSpinner = false;
            std::thread(spinnerThread).detach();

            std::thread([]{
                Usage prev;
                { std::shared_lock lk(latestMtx); prev = latest; }
                Usage u = collect(prev);
                { std::unique_lock lk(latestMtx); latest = u; }

                stopSpinner = true;
                std::this_thread::sleep_for(std::chrono::milliseconds(150));

                std::cout << "["<<nowStr()<<"] MEM "
                          << std::fixed<<std::setprecision(1)<<u.memPct<<"% ("
                          <<u.usedMB<<"/"<<u.totalMB<<" MB, "
                          <<u.topPkg<<", "
                          <<std::fixed<<std::setprecision(1)<<u.topPct<<"%) | CPU "
                          <<u.cpuPct<<"% per‑core ("<<u.cpuSum<<"% sum)\n";

                writeLog(u);
                busy = false;
            }).detach();
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(30));
    }
}

void sampler() {
    bool memHigh=false, cpuHigh=false;
    Usage prev{};
    while (true) {
        Usage u = collect(prev);
        { std::unique_lock lk(latestMtx); latest = u; }

        if (u.memPct >= MEM_LIMIT_PCT && !memHigh) {
            alertMem(u);
            memHigh = true;
        }
        if (u.memPct < MEM_LIMIT_PCT) memHigh = false;

        if (u.cpuPct >= CPU_LIMIT_PCT && !cpuHigh) {
            alertCPU(u);
            cpuHigh = true;
        }
        if (u.cpuPct < CPU_LIMIT_PCT) cpuHigh = false;

        writeLog(u);
        prev = u;
        std::this_thread::sleep_for(std::chrono::seconds(POLL_SEC));
    }
}

int main() {
    std::thread(sampler).detach();
    keyListener();
    return 0;
}

