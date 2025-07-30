# OpenCV 기반 테스트 자동화 및 유틸리티 프로젝트

이 프로젝트는 OpenCV를 활용한 테스트 자동화, ADB를 이용한 디바이스 제어, 그리고 반복적인 셸 명령어 실행을 돕는 GUI 도구들을 포함하고 있습니다.

## 주요 도구

### 1. adb_mirror

Android 디바이스의 화면을 PC에 미러링하고, 터치 이벤트를 재현하거나 UI 상태를 모니터링하는 등 다양한 자동화 작업을 수행하는 도구입니다.

- **주요 기능:**
    - 실시간 화면 미러링
    - 터치 이벤트 기록 및 재현
    - UI 요소 자동 토글
    - 메모리 사용량 등 디바이스 상태 로깅

- **실행 방법:**
  ```bash
  python adb_mirror/main.py
  ```

### 2. command_pad

자주 사용하는 셸 명령어들을 버튼으로 만들어 관리하고 실행할 수 있는 GUI 애플리케이션입니다. 복잡한 명령어들을 매번 입력할 필요 없이 버튼 클릭만으로 실행할 수 있어 작업 효율을 높여줍니다.

- **주요 기능:**
    - 명령어 단축키(버튼) 생성, 편집, 삭제 및 재정렬
    - `cmd_pad.json` 파일을 통해 명령어 목록 관리
    - 명령어 실행 상태 및 결과 표시

- **실행 방법:**
  ```bash
  python command_pad/cmd_pad.py
  ```

### 3. opencv_test_automation

OpenCV를 사용하여 이미지 인식을 기반으로 한 테스트 자동화를 수행하는 도구입니다. 특정 이미지가 화면에 나타나는 것을 감지하여 테스트 시나리오를 실행할 수 있습니다.

- **주요 기능:**
    - 이미지 기반 테스트 케이스 실행
    - 여러 디바이스에 대한 동시 테스트 지원

- **실행 방법:**
  ```bash
  python opencv_test_automation/run.py
  ```

## 의존성

각 도구 폴더의 `requirements.txt` 파일을 참고하여 필요한 라이브러리를 설치하십시오.

```bash
pip install -r adb_mirror/requirements.txt
pip install -r opencv_test_automation/requirements.txt
```
