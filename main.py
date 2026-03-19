import os
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import edge_tts
import imageio_ffmpeg
import subprocess
import uuid
from deep_translator import GoogleTranslator

app = FastAPI()

# Make sure temp directory exists for TTS audio files
os.makedirs("temp", exist_ok=True)

# Mount static files correctly
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def get_index():
    return FileResponse("static/index.html")

class TTSRequest(BaseModel):
    text: str
    voice: str
    lang: str
    speed: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"
    stability: int = 75
    clarity: int = 88
    style: str = ""

@app.post("/api/tts")
async def generate_tts(req: TTSRequest):
    # Auto-translate text to the target language 
    try:
        translated_text = GoogleTranslator(source='auto', target=req.lang).translate(req.text)
        print(f"Translated '{req.text}' to '{translated_text}' in {req.lang}")
    except Exception as e:
        print(f"Translation error: {e}")
        translated_text = req.text

    # Setup Edge TTS with parameters
    communicate = edge_tts.Communicate(translated_text, req.voice, rate=req.speed, pitch=req.pitch, volume=req.volume)
    
    base_uuid = uuid.uuid4()
    mp3_output_path = f"temp/{base_uuid}.mp3"
    wav_output_path = f"temp/{base_uuid}.wav"
    
    # Run the save operation
    await communicate.save(mp3_output_path)

    # Convert the MP3 to WAV
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    # Apply "style" filters if needed (e.g., aecho for whispery/dramatic effects)
    audio_filters = []
    if req.style == "Whispery":
        audio_filters = ["-af", "aecho=0.8:0.88:6:0.4"]
    elif req.style == "Dramatic":
        audio_filters = ["-af", "aecho=0.8:0.9:1000:0.3,highpass=f=200,lowpass=f=3000"]
    elif req.style == "Suspenseful":
        audio_filters = ["-af", "aecho=0.8:0.9:500:0.5"]

    cmd = [ffmpeg_exe, "-y", "-i", mp3_output_path] + audio_filters + [wav_output_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    os.remove(mp3_output_path)
    
    # Stream the file back and then remove it
    def iterfile():
        try:
            with open(wav_output_path, "rb") as f:
                yield from f
        finally:
            if os.path.exists(wav_output_path):
                os.remove(wav_output_path)

    return StreamingResponse(iterfile(), media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=4000, reload=True)
