
import os
from dotenv import load_dotenv

class AppConfig:
    """
    .env 파일에서 환경 변수를 로드하고 관리합니다.
    필요한 키가 없는 경우 예외를 발생시킵니다.
    """
    def __init__(self, required_keys: list[str]):
        # .env 파일이 WebAppTester 폴더 내에 있을 것을 가정합니다.
        # 이 파일의 위치(WebAppTester/src)에서 상위 폴더를 기준으로 .env 경로를 잡습니다.
        dotenv_path = os.path.join(os.path.dirname(__file__), '../.env')
        load_dotenv(dotenv_path=dotenv_path)

        self.config = {}
        for key in required_keys:
            value = os.getenv(key)
            if not value:
                raise ValueError(f"환경 변수 '{key}'가 .env 파일에 설정되지 않았습니다.")
            self.config[key] = value

    def __getattr__(self, name: str) -> str:
        if name in self.config:
            return self.config[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.config.get(key, default)
