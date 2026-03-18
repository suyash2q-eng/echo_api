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

@app.post("/api/tts")
async def generate_tts(req: TTSRequest):
    # Auto-translate text to the target language 
    try:
        translated_text = GoogleTranslator(source='auto', target=req.lang).translate(req.text)
        print(f"Translated '{req.text}' to '{translated_text}' in {req.lang}")
    except Exception as e:
        print(f"Translation error: {e}")
        translated_text = req.text

    # Setup Edge TTS
    communicate = edge_tts.Communicate(translated_text, req.voice)
    
    base_uuid = uuid.uuid4()
    mp3_output_path = f"temp/{base_uuid}.mp3"
    wav_output_path = f"temp/{base_uuid}.wav"
    
    # Run the save operation (we must await it correctly or it fails without errors in some envs)
    await communicate.save(mp3_output_path)

    # Convert the MP3 to WAV
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg_exe, "-y", "-i", mp3_output_path, wav_output_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    os.remove(mp3_output_path)
    
    # Stream the file back and then remove it
    def iterfile():
        with open(wav_output_path, "rb") as f:
            yield from f
        os.remove(wav_output_path)

    return StreamingResponse(iterfile(), media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=4000, reload=True)
