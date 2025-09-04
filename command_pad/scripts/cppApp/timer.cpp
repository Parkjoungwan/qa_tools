#include <iostream>
#include <chrono>
#include <cmath>       // <-- floor 함수를 사용하기 위함
#include <iomanip>     // <-- setprecision, fixed 사용을 위함

#ifdef _WIN32
    #include <conio.h>
#else
    #include <termios.h>
    #include <unistd.h>
    #include <cstdio>
    // 비 Windows 환경에서 _getch()와 유사한 기능 구현
    int _getch() {
        struct termios oldt, newt;
        int ch;
        tcgetattr(STDIN_FILENO, &oldt);
        newt = oldt;
        newt.c_lflag &= ~(ICANON | ECHO);
        tcsetattr(STDIN_FILENO, TCSANOW, &newt);
        ch = getchar();
        tcsetattr(STDIN_FILENO, TCSANOW, &oldt);
        return ch;
    }
#endif

using namespace std;
using namespace std::chrono;

int main() {
    cout << "타이머 프로그램 시작 (종료: 'q' 누르기).\n";
    cout << "타이머 시작/정지는 스페이스바로 진행합니다.\n";

    while (true) {
        char ch;
        // 대기 상태: 스페이스바 입력을 기다림 (종료는 q 입력)
        while (true) {
            ch = _getch();
            if (ch == ' ') break;           // 스페이스바 누르면 타이머 시작
            if (ch == 'q' || ch == 'Q') return 0; // 'q' 입력 시 프로그램 종료
        }
        
        // 타이머 시작
        auto start = high_resolution_clock::now();
        cout << "\n타이머 시작...\n";
        
        // 두 번째 스페이스바 입력 대기 (또는 q 입력 시 종료)
        while (true) {
            ch = _getch();
            if (ch == ' ') break;           // 두 번째 스페이스바 누르면 타이머 정지
            if (ch == 'q' || ch == 'Q') return 0;
        }
        auto end = high_resolution_clock::now();
        
        // 경과 시간 계산 후 소수점 둘째 자리까지(셋째 자리에서 버림) 출력
        duration<double> elapsed = end - start;
        double timeSec = elapsed.count();
        
        // 소수점 둘째 자리까지만 버림
        double truncated = floor(timeSec * 100.0) / 100.0;
        
        // 이미 버림된 값을 소수점 둘째 자리까지 출력
        cout << fixed << setprecision(2);
        cout << "경과 시간: " << truncated << " 초\n";
        cout << "대기 상태로 돌아갑니다. (종료하려면 'q' 입력)\n\n";
    }
    
    return 0;
}

