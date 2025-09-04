// build with:
//   g++ -std=c++17 -lncurses -pthread -o dual_trend dual_trend.cpp

#include <ncurses.h>
#include <fstream>
#include <regex>
#include <vector>
#include <mutex>
#include <thread>
#include <chrono>
#include <algorithm>

//────────── Config ──────────
static constexpr const char* LOG_FILE    = "monitor.log";
static constexpr size_t       MAX_HISTORY = 2000;
static constexpr int          SAMPLE_SEC  = 10;

//────────── Globals ──────────
std::vector<std::pair<double,double>> history; // (memPct, cpuPct)
std::mutex                            histMtx;
std::streampos                       lastPos = -1;
static const std::regex              LINE_RX(
    R"(\[.*?\]\s*MEM\s*([0-9]+(?:\.[0-9]+)?)%.*?\|\s*CPU\s*([0-9]+(?:\.[0-9]+)?)%)"
);

//────────── Tail & Parse ──────────
void tailLog() {
    std::ifstream ifs(LOG_FILE);
    if (!ifs.is_open()) return;
    if (lastPos < 0) lastPos = 0;
    ifs.seekg(lastPos);
    std::string line;
    std::smatch m;
    std::lock_guard lk(histMtx);
    while (std::getline(ifs, line)) {
        if (std::regex_search(line, m, LINE_RX)) {
            double mem = std::stod(m[1]);
            double cpu = std::stod(m[2]);
            history.emplace_back(mem, cpu);
            if (history.size() > MAX_HISTORY)
                history.erase(history.begin(), history.begin() + (history.size() - MAX_HISTORY));
        }
    }
    lastPos = ifs.tellg();
}

//────────── Draw Scrolling Dual Bars ──────────
void drawTrend() {
    clear();
    int h, w;
    getmaxyx(stdscr, h, w);
    int barW = (w - 4) / 2; // two bars + spacing
    int maxLines = h - 2;   // leave bottom line for legend

    // compute range to display
    std::lock_guard lk(histMtx);
    int n = history.size();
    int start = n > maxLines ? n - maxLines : 0;

    for (int idx = start; idx < n; ++idx) {
        int row = idx - start;
        double memPct = history[idx].first;
        double cpuPct = history[idx].second;

        // determine color
        int memColor = (memPct < 50 ? 1 : (memPct < 75 ? 2 : 3));
        int cpuColor = (cpuPct < 50 ? 1 : (cpuPct < 75 ? 2 : 3));

        // memory bar
        int memLen = std::min(barW, std::max(0, int((memPct/100.0)*barW + 0.5)));
        attron(COLOR_PAIR(memColor));
        for (int x = 0; x < memLen; ++x) mvaddch(row, x, ACS_CKBOARD);
        attroff(COLOR_PAIR(memColor));
        // clear rest
        for (int x = memLen; x < barW; ++x) mvaddch(row, x, ' ');

        // separator
        mvaddch(row, barW, ' ');
        mvaddch(row, barW+1, '|');
        mvaddch(row, barW+2, ' ');

        // CPU bar
        int cpuLen = std::min(barW, std::max(0, int((cpuPct/100.0)*barW + 0.5)));
        attron(COLOR_PAIR(cpuColor));
        for (int x = 0; x < cpuLen; ++x) mvaddch(row, barW+3 + x, ACS_CKBOARD);
        attroff(COLOR_PAIR(cpuColor));
        for (int x = cpuLen; x < barW; ++x) mvaddch(row, barW+3 + x, ' ');

        // optional percentages at end
        mvprintw(row, w-8, "%3d%%", int(memPct+0.5));
        mvprintw(row, w-4, "%3d%%", int(cpuPct+0.5));
    }

    mvprintw(h-1, 0, "LEFT=MEM   RIGHT=CPU   SPACE=refresh   Q=quit");
    refresh();
}

//────────── Main Loop ──────────
int main() {
    // init ncurses
    initscr();
    cbreak();
    noecho();
    curs_set(0);
    start_color();
    init_pair(1, COLOR_GREEN,  COLOR_BLACK);
    init_pair(2, COLOR_YELLOW, COLOR_BLACK);
    init_pair(3, COLOR_RED,    COLOR_BLACK);
    nodelay(stdscr, TRUE);

    // initial load & draw
    tailLog();
    drawTrend();

    // periodic updater
    std::thread([&](){
        while (true) {
            std::this_thread::sleep_for(std::chrono::seconds(SAMPLE_SEC));
            tailLog();
            drawTrend();
        }
    }).detach();

    // input loop
    while (true) {
        int ch = getch();
        if (ch == 'q' || ch == 'Q') break;
        if (ch == ' ') {
            tailLog();
            drawTrend();
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    endwin();
    return 0;
}

