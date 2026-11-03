"""Generate the voiceover per scene with edge-tts and sentence-level subtitles.

Usage: python tts.py  (writes audio/<scene>.mp3 and audio/<scene>.json with sentence timings)
"""
import asyncio
import json
from pathlib import Path

import edge_tts

HERE = Path(__file__).resolve().parent
OUT = HERE / "audio"


async def synth(scene: dict, voice: str, rate: str) -> None:
    comm = edge_tts.Communicate(scene["text"], voice, rate=rate, boundary="SentenceBoundary")
    cues = []
    with open(OUT / f"{scene['id']}.mp3", "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                cues.append({"start": chunk["offset"] / 1e7, "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                             "text": chunk["text"]})
    (OUT / f"{scene['id']}.json").write_text(json.dumps(cues, indent=1), encoding="utf-8")


async def main() -> None:
    cfg = json.loads((HERE / "narration.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    for s in cfg["scenes"]:
        await synth(s, cfg["voice"], cfg["rate"])
        print("ok", s["id"])


if __name__ == "__main__":
    asyncio.run(main())
