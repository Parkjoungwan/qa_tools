import asyncio
import zipfile
from pathlib import Path
import edge_tts

VOICE = "ko-KR-InJoonNeural"     # 남성, 차분한 톤에 적합한 한국어 음성
RATE = "-5%"                     # 말속도 약간 느리게(차분한 느낌)
VOLUME = "+0%"                   # 기본 볼륨

LINES = {
    "long2.mp3": "그런게 가능할리가 없잖아요. 여기가 무슨 궁전도 아니고.",
}

async def synth_one(filename: str, text: str):
    tts = edge_tts.Communicate(text=text, voice=VOICE, rate=RATE, volume=VOLUME)
    await tts.save(filename)

async def main():
    out_dir = Path("tts_out")
    out_dir.mkdir(exist_ok=True)
    # mp3 생성
    tasks = [synth_one(str(out_dir / fn), txt) for fn, txt in LINES.items()]
    await asyncio.gather(*tasks)

    # zip 압축
    zip_path = Path("tts_samples.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fn in LINES.keys():
            zf.write(out_dir / fn, arcname=fn)

    print(f"[완료] {zip_path.resolve()} 생성")
    print(f"개별 파일 폴더: {out_dir.resolve()}")

if __name__ == "__main__":
    asyncio.run(main())
