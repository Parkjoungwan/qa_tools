
import yaml
import os
import re
from .config import AppConfig

def load_spec(spec_path: str) -> dict:
    """
    지정된 경로의 YAML 스펙 파일을 로드하고 내용을 파싱합니다.
    - env.keys 에 명시된 환경 변수를 로드합니다.
    - ${VAR_NAME} 형태의 플레이스홀더를 실제 환경 변수 값으로 치환합니다.
    """
    if not os.path.exists(spec_path):
        raise FileNotFoundError(f"스펙 파일을 찾을 수 없습니다: {spec_path}")

    with open(spec_path, 'r', encoding='utf-8') as f:
        spec_content = f.read()

    spec = yaml.safe_load(spec_content)

    # 스펙 파일에 명시된 필수 환경 변수 로드
    config = AppConfig(required_keys=spec.get('env', {}).get('keys', []))

    # 스펙 파일 내용에서 ${VAR_NAME} 플레이스홀더를 환경 변수 값으로 치환
    def replace_env_vars(content):
        if isinstance(content, str):
            # 정규식을 사용하여 ${VAR_NAME} 패턴을 찾고 config에서 값을 가져와 대체
            return re.sub(r'\$\{([^}]+)\}', lambda m: getattr(config, m.group(1)), content)
        elif isinstance(content, dict):
            return {k: replace_env_vars(v) for k, v in content.items()}
        elif isinstance(content, list):
            return [replace_env_vars(i) for i in content]
        else:
            return content

    return replace_env_vars(spec)

