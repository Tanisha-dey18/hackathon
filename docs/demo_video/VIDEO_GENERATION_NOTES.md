# SENTINEL demo video: how it was made

`SENTINEL_Hackathon_Demo.mp4` is a 2:37 video (1920×1080, 30 fps, H.264 + AAC 48 kHz). It was made entirely from the
running application plus generated narration, captions, title cards and music. Everything is reproducible with the
scripts in `SENTINEL_Video_Assets/`.

## Deliverables

| File | What it is |
|---|---|
| `SENTINEL_Hackathon_Demo.mp4` | Final video, with subtitles burned in |
| `SENTINEL_Voiceover_Script.txt` | The narration, scene by scene |
| `SENTINEL_Subtitles.srt` | The same captions as a sidecar file (for YouTube/Devpost upload) |
| `SENTINEL_Thumbnail.png` | 1920×1080 thumbnail; the graph panel is a real frame from the recording |
| `SENTINEL_Video_Assets/` | Narration text, scripts, voice audio, raw footage and timings |

## Tools

- **Voice:** [edge-tts](https://github.com/rany2/edge-tts), using the Microsoft neural voice `en-IN-NeerjaNeural`
  (female, Indian English) at normal rate. It is a natural neural voice, not a robotic one. Sentence timings come from
  the TTS engine, so the captions line up with speech.
- **Footage:** Playwright Chromium recording the real app at 1920×1080, with the local backend (`:8000`) and frontend
  (`:5173`) freshly reset. The recording uses only the seeded synthetic demo accounts on localhost.
- **Editing:** FFmpeg (from `imageio-ffmpeg`): crossfades, a slow 3.5 % push-in on each clip, alpha-faded scene
  labels, ASS subtitles, ducking and EBU R128 loudness normalisation to −16 LUFS.
- **Graphics:** Pillow (title card, closing card, scene labels, thumbnail).
- **Music:** an original ambient pad (Am–F–C–G), synthesised with numpy inside `build_video.py`. It contains no
  third-party or copyrighted audio. It plays at low volume and is side-chain ducked under the voice.

## Honesty choices

- **PayPal:** Sandbox credentials were not configured on the recording machine. The checkout scene shows the app's
  real "PayPal Sandbox is not configured" message, and the narration says so. **No PayPal approval or capture is
  shown or implied.**
- **AI agent:** no Groq key was set, so the agent ran its labelled deterministic fallback ("Deterministic rule-based
  report — not LLM-generated", visible on screen). The narration says this.
- **Fraud-ring scenario:** in the recording, Demo C scored 0.48 (MEDIUM) from the model alone, and the graph policy
  raised it to HIGH. The narration matches that ("only medium risk"), rather than claiming a higher model score.
- **Data:** all customers, merchants and transactions are synthetic, and the video says so.
- **Secrets:** no API keys or secrets appear. The reviewer password is typed into a masked password field.

## Regenerating

From the repo root:

1. Reset the demo data and start the servers (backend on 8000, frontend on 5173):
   ```powershell
   .\scripts\reset-demo.ps1
   ```
2. In `docs/demo_video/SENTINEL_Video_Assets/`, with `edge-tts`, `playwright` (plus `playwright install chromium`),
   `httpx`, `pillow`, `numpy` and `imageio-ffmpeg` installed:
   ```bash
   python tts.py          # narration.json -> audio/*.mp3 + sentence timings
   python record.py       # real app footage -> footage/*.webm + timing.json
   python build_video.py  # cards, music, subtitles, final mix -> ../SENTINEL_Hackathon_Demo.mp4
   ```
   `record.py` must run on a freshly reset database, because the scenes depend on each other (Demo C is investigated,
   then rejected).
3. `build_video.py` looks for Segoe UI font files in `fonts/` (`segoeuib.ttf`, `seguisb.ttf`, `segoeui.ttf`,
   `segoeuii.ttf`, copied from `C:\Windows\Fonts`). They are not committed because of their licence.

To change wording, edit `narration.json` and rerun all three steps. The footage is padded to each scene's narration
length.

## Using your own voice instead

Record one file per scene, named `audio/<scene_id>.mp3` (`s1_intro` … `s8_close`). Then update the matching
`audio/<scene_id>.json` so its sentence `start`/`end` times (in seconds) match your recording. Then rerun
`record.py` (scene lengths follow the narration) and `build_video.py`.

## Quality check (final render)

| Check | Result |
|---|---|
| Plays / decodes | Yes: full decode with FFmpeg, no errors |
| Length | 2:37.3 (under 3:00) |
| Resolution / frame rate | 1920×1080, 16:9, 30 fps |
| Voice | Female neural voice (en-IN-NeerjaNeural); clips are timed from narration, so voice and footage stay in sync |
| Subtitles | Burned in: white Segoe UI Semibold 44 px on a translucent box, at most 2 lines; also supplied as SRT |
| Music | Original and synthesised. Music-only passages average about −32 dB against about −24 dB for speech, and it is ducked further under the voice |
| Loudness | About −16 LUFS integrated, −1.5 dBTP ceiling |
| Secrets | None visible; the password field is masked |
| Real features only | Every app shot is the live app. Payment shows "not configured" with no fake success, and the agent fallback is labelled |
