# Google Colab server code
# Run this in a Colab cell after enabling GPU (Runtime > Change runtime type > Hardware accelerator > GPU)

# Install dependencies
!pip install fastapi uvicorn pydub demucs

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from pydub import AudioSegment
import os
import shutil
import uuid

app = FastAPI()

# Save path in Google Drive
OUTPUT_DIR = "/content/drive/MyDrive/vidthing_stems"
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    try:
        file_id = str(uuid.uuid4())[:8]
        suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
        input_path = os.path.join("/content", f"input_{file_id}{suffix}")
        
        with open(input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        drive_path = os.path.join(OUTPUT_DIR, file_id)
        os.makedirs(drive_path, exist_ok=True)
        
        # Run Demucs
        from demucs import separate
        separate.main(["--mp", "--two-stems=vocals", "-o", drive_path, input_path])
        
        stems = []
        for root, dirs, files in os.walk(drive_path):
            for fname in files:
                if fname.endswith(".wav"):
                    stems.append(fname)
        
        return JSONResponse(content={
            "message": "Stems saved to Google Drive",
            "drive_path": drive_path,
            "stems": stems
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)

# Run with: uvicorn server:app --host 0.0.0.0 --port 8000


import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import numpy as np
import torch
import json
import gc
import threading
from pyngrok import ngrok
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

if int(np.__version__.split(".")[0]) < 2:
    raise RuntimeError(
        f"NumPy {np.__version__} is loaded (ABI 88). Colab torch needs NumPy 2.x (ABI 96). "
        "Runtime -> Restart session, run the install cell, restart again, then run this cell."
    )

import transformers.utils.import_utils as _tf_import_utils
_tf_import_utils.is_sklearn_available = lambda: False
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# --- Configuration ---
NGROK_AUTH_TOKEN = ""  # <--- Update with your genuine token
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Rigid CUDA Hardware Verification ---
if not torch.cuda.is_available():
    print("\n⚠️ WARNING: CUDA is missing! Server falling back to slow CPU calculation.")
    print("Fix: Colab Menu -> Runtime -> Change runtime type -> Choose T4 GPU.\n")
    device = "cpu"
else:
    device = "cuda"
    print(f"\n🚀 Connected to GPU: {torch.cuda.get_device_name(0)}. Processing will run fast.\n")

# --- System Prompt for Qwen Three.js Visual Director ---
SYSTEM_INSTRUCTION = """You are to act as a visual director for music. Create psychedelic visual effects by analysing provided music analysis
data and lyrics. You are to do this by analysing the provided data in terms of timeframes and output a JSON of your imagined visuals
in a strict schema, such that it can be used by a Three JS engine. Strictly avoid adding conversational text or anything else.
Exclusively output JSON
Ensure the visuals are arranged, satisfying and psychedelic
JSON SCHEMA:
{
  "background": {
    "color": "string of a HEX color (use either this or the gradient with an array of 2+ colors)",
    "gradient": ["#000010", "#1a0a2e", "#2d1b4e"]
  },
  "camera": {
    "fov": 75, (integer - field of view)
    "position": [0, 2, 10], (array)
    "lookAt": [0, 0, 0] (array)
  },
  "lighting": [
    {
      "type": "ambient",
      "color": "#404040",
      "intensity": 0.5
    },
    {
      "type": "point",
      "color": "#ff6600",
      "intensity": 2,
      "position": [5, 5, 5]
    }
  ],
  "objects": [
    {
      "type": "particles",
      "id": "particles1",
      "count": 2000,
      "position": [0, 0, 0],
      "rotation": [0, 0, 0],
      "scale": [1, 1, 1],
      "color": "#ff00ff",
      "colors": ["#ff00ff", "#00ffff"],
      "opacity": 1,
      "size": 15,
      "motion": {
        "type": "swarm",
        "speed": 1,
        "amplitude": 2,
        "frequency": 1,
        "axis": "y",
        "center": [0, 0, 0],
        "target": [5, 5, 5]
      },
      "startTime": 0,
      "endTime": 30
    }
  ],
  "effects": {
    "bloom": {
      "enabled": true,
      "strength": 1.5,
      "radius": 0.4,
      "threshold": 0.1
    },
    "chromaticAberration": {
      "enabled": true,
      "offset": 0.003
    },
    "vignette": {
      "enabled": true,
      "offset": 0.5,
      "darkness": 1.2
    },
    "kaleidoscope": {
      "enabled": true,
      "slices": 6
    },
    "glitch": {
      "enabled": false,
      "intensity": 0.1
    }
  },
  "global": {
    "timeScale": 1,
    "loop": true,
    "duration": 30
  }
}
(The provided values are only examples - Give values solely based on your creative analysis of given data)
"""

# --- Free Memory & Load Qwen Model ---
gc.collect()
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    _free_vram = torch.cuda.mem_get_info()[0] / (1024**3)
    print(f"VRAM available before Qwen load: {_free_vram:.2f} GiB")

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True
)

print("Loading Qwen 4B in 4-bit NF4 quantization...")

try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

    vmodel = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=quantization_config,
        device_map="auto",
        max_memory={0: "8GiB", "cpu": "32GiB"},
        offload_folder="offload_weights"
    )

    print("✅ Qwen 4B loaded successfully (4-bit NF4, max_memory=8GiB enforced).")

except torch.cuda.OutOfMemoryError:
    print("❌ GPU OOM with 8GiB cap. Retrying with 4GiB cap + more CPU offload...")

    try:
        vmodel = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            quantization_config=quantization_config,
            device_map="auto",
            max_memory={0: "4GiB", "cpu": "32GiB"},
            offload_folder="offload_weights"
        )
        print("✅ Qwen loaded with reduced GPU footprint + CPU offload.")

    except Exception as e2:
        print(f"❌ Qwen fallback failed: {e2}")
        vmodel = None
        tokenizer = None

except Exception as e:
    print(f"❌ Qwen failed to load: {e}")
    vmodel = None
    tokenizer = None


def generate_visual_json(music_analysis, lyrics_data=None):
    """Generates Three.js visual scene JSON using Qwen based on audio analysis."""
    if vmodel is None:
        return {
            "success": False,
            "error": "Qwen model is unavailable."
        }

    try:
        # Format lyrics if present; otherwise default to instrumental indicator
        clean_lyrics = []
        if isinstance(lyrics_data, dict) and "segments" in lyrics_data:
            for s in lyrics_data["segments"]:
                clean_lyrics.append({
                    "start": round(float(s.get("start", 0)), 2),
                    "end": round(float(s.get("end", 0)), 2),
                    "text": s.get("text", "").strip()
                })
        elif isinstance(lyrics_data, list):
            clean_lyrics = lyrics_data
        elif lyrics_data:
            clean_lyrics = lyrics_data

        user_content = {
            "music_analysis": music_analysis,
            "lyrics": clean_lyrics if clean_lyrics else "No lyrics available (instrumental / lyrics stripped)."
        }

        messages = [
            {
                "role": "system",
                "content": SYSTEM_INSTRUCTION
            },
            {
                "role": "user",
                "content": json.dumps(
                    user_content,
                    ensure_ascii=False,
                    separators=(",", ":")
                )
            }
        ]

        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        # Free all residual memory before allocating generation KV-cache
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        model_inputs = tokenizer(
            [text],
            return_tensors="pt"
        ).to(vmodel.device)

        input_tokens = model_inputs.input_ids.shape[1]
        print(f"🧠 Qwen input prompt: {input_tokens} tokens")

        max_tokens = 4096
        print(f"🎨 Generating full visual direction (up to {max_tokens} tokens)...")

        try:
            with torch.inference_mode():
                generated_ids = vmodel.generate(
                    **model_inputs,
                    max_new_tokens=max_tokens,
                    do_sample=True,
                    temperature=0.75,
                    top_p=0.85,
                    repetition_penalty=1.05
                )
        except torch.cuda.OutOfMemoryError:
            print("⚠️ Qwen OOM with 4096 tokens. Retrying with 2048 tokens limit...")
            del model_inputs
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            model_inputs = tokenizer([text], return_tensors="pt").to(vmodel.device)
            with torch.inference_mode():
                generated_ids = vmodel.generate(
                    **model_inputs,
                    max_new_tokens=2048,
                    do_sample=True,
                    temperature=0.75,
                    top_p=0.85,
                    repetition_penalty=1.05
                )

        # Remove prompt tokens from output
        generated_ids = [
            output_ids[len(input_ids):]
            for input_ids, output_ids
            in zip(model_inputs.input_ids, generated_ids)
        ]

        response_text = tokenizer.batch_decode(
            generated_ids,
            skip_special_tokens=True
        )[0].strip()

        # Free generation tensors from GPU
        del model_inputs
        del generated_ids
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Parse & save JSON (with markdown code fence fallback)
        try:
            visual_json = json.loads(response_text)
        except json.JSONDecodeError:
            print("⚠️ Qwen returned markdown-wrapped JSON. Stripping backticks...")
            cleaned = response_text
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            try:
                visual_json = json.loads(cleaned)
            except Exception:
                print("❌ Failed to parse JSON even after stripping.")
                return {
                    "success": False,
                    "error": "INVALID_JSON",
                    "raw_output": response_text
                }

        with open("visual_output.json", "w", encoding="utf-8") as f:
            json.dump(visual_json, f, indent=2, ensure_ascii=False)

        print("🎉 Complete visual JSON generated and saved to visual_output.json!")

        return {
            "success": True,
            "input_tokens": input_tokens,
            "visual_json": visual_json
        }

    except torch.cuda.OutOfMemoryError as oom:
        print(f"❌ Qwen OutOfMemoryError: {oom}")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return {
            "success": False,
            "error": "GPU_OUT_OF_MEMORY",
            "message": str(oom)
        }

    except Exception as e:
        print(f"❌ Qwen generation failed: {e}")
        return {
            "success": False,
            "error": "QWEN_GENERATION_FAILED",
            "message": str(e)
        }


def process_visual_generation(filepath, original_filename):
    """Processes music analysis through Qwen in the background (no Demucs/WhisperX)."""
    try:
        print(f"[Worker] Processing track for visual direction: {original_filename}")

        analysed = {}
        if os.path.exists("analysis.json"):
            with open("analysis.json", "r", encoding="utf-8") as a:
                analysed = json.load(a)
        else:
            print("[Worker] Notice: analysis.json not found yet, proceeding with empty analysis.")

        # Demucs & WhisperX removed to prevent OOM
        # If a prior lyrics_output.json exists, use it; otherwise proceed without lyrics
        lyrics = []
        if os.path.exists("lyrics_output.json"):
            try:
                with open("lyrics_output.json", "r", encoding="utf-8") as f:
                    lyrics = json.load(f)
            except Exception:
                lyrics = []

        print("[Worker] Triggering Qwen visual direction generation...")
        Result = generate_visual_json(analysed, lyrics)

        if not Result.get("success"):
            print(f"[Worker] Visual generation finished with status: {Result.get('error')}")
            return Result

        print("🎨 Visual direction successfully generated.")
        return Result

    except Exception as e:
        print(f"[Worker Error] System failure during execution: {str(e)}")


if __name__ == '__main__':
    try:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path == '/upload-audio':
                    content_len = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_len)
                    boundary = self.headers.get('Content-Type', '').split('boundary=')[1] if 'boundary=' in self.headers.get('Content-Type', '') else None
                    filename = 'audio.wav'
                    if boundary:
                        parts = body.split(boundary.encode())
                        for part in parts:
                            if b'audio_file' in part:
                                lines = part.split(b'\r\n')
                                for line in lines:
                                    if b'name="audio_file"' in line and b'filename=' in line:
                                        filename = line.split(b'filename="')[1].split(b'"')[0].decode()
                                content_start = part.find(b'\r\n\r\n') + 4
                                content_end = part.rfind(b'\r\n')
                                audio_content = part[content_start:content_end]
                                filepath = os.path.join(UPLOAD_FOLDER, filename)
                                with open(filepath, 'wb') as f:
                                    f.write(audio_content)

                                # 🔥 Trigger Qwen visual direction generation in background thread
                                threading.Thread(
                                    target=process_visual_generation,
                                    args=(filepath, filename),
                                    daemon=True
                                ).start()
                                break

                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'ok'}).encode())

                elif self.path == '/analysed-features':
                    content_len = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_len)
                    data = json.loads(body.decode())
                    with open('analysis.json', 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'ok'}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_GET(self):
                if self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'ok'}).encode())
                elif self.path in ('/visual-output', '/visual_output.json'):
                    if os.path.exists("visual_output.json"):
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        with open("visual_output.json", "rb") as f:
                            self.wfile.write(f.read())
                    else:
                        self.send_response(404)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'error': 'visual_output.json not generated yet'}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()

        # 1. Close any stale ngrok tunnels
        ngrok.kill()

        # 2. Authenticate ngrok
        ngrok.set_auth_token(NGROK_AUTH_TOKEN)

        # 3. Create public tunnel to port 8888
        tunnel = ngrok.connect(8888)
        print("\n" + "="*65)
        print(f"🚀 COLAB NGROK URL: {tunnel.public_url}")
        print("👉 Copy the URL above and paste it into the web UI box")
        print("="*65 + "\n")

        # 4. Start multi-threaded server on 0.0.0.0
        server = ThreadingHTTPServer(('0.0.0.0', 8888), Handler)
        server.serve_forever()
    except Exception as e:
        print(f"Server execution halted: {e}")
