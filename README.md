# AI Music Visualiser

An end-to-end music-to-visualisation project that uploads an audio file, analyses the track using Python audio signal processing, and turns the results into a generated visual scene driven by an LLM routing layer.

This repository combines:

- a Node.js + Express web app for upload and UI
- a FastAPI Python service for audio analysis
- a visual engine that renders music-reactive scenes
- a router that converts music analysis into structured JSON for the visual engine
- optional Colab-based stem separation forwarding

## Features

- Upload audio files through a browser interface
- Analyse tempo, beat timing, energy, brightness, frequency balance, MFCCs, and chroma
- Detect audio events like peaks, drops, and onsets
- Generate a structured visual scene definition from the audio analysis
- Render visuals via the local visual engine
- Forward audio and analysis data to a remote Colab environment for stem separation
- Support Google GenAI as the primary model with OpenRouter fallback

## Project structure

```text
AI-Music-Visualiser/
├── index.js                  # Express upload server and API endpoints
├── router.py                 # LLM routing layer for Google GenAI/OpenRouter
├── run_router.py             # CLI wrapper for generating visual JSON from analysis input
├── python-server/
│   ├── server.py             # FastAPI audio analysis service
│   └── requirements.txt      # Python dependencies
├── views/                   # EJS views for upload and result pages
├── visual-engine/           # Visual rendering project files
├── uploads/                 # Temporary uploaded audio files
├── public/                  # Static frontend assets
├── package.json             # Node project metadata and start script
├── package-lock.json        # Lockfile
├── LICENSE                  # MIT license
├── README.md                # Project documentation
└── run.txt                  # Local run notes or helper commands
```

## Tech stack

- Node.js / Express
- FastAPI
- Python audio analysis with librosa, numpy, pydub
- Pydantic schema validation
- EJS templates
- Google Generative AI and OpenRouter

## Quick start

### 1) Install Node dependencies

```bash
npm install
```

### 2) Install Python dependencies

```bash
cd python-server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3) Configure environment variables

Create a `.env` file or export variables before running the services:

```bash
export PORT=3000
export PYTHON_URL=http://localhost:8000/analyze
export COLAB_URL=http://localhost:8888
export GOOGLE_API_KEY=your_google_api_key
export OPENROUTER_API_KEY=your_openrouter_api_key
export GOOGLE_MODEL=gemini-3.5-flash
export OPENROUTER_MODEL=mistralai/mistral-large-2407
```

Notes:

- `PYTHON_URL` points to the FastAPI analysis service.
- `COLAB_URL` is optional and enables forwarding to a remote Google Colab environment.
- The app can work without a router model key if visual generation is not needed, but the visual pipeline depends on the LLM layer.

### 4) Start the Python analysis server

```bash
cd python-server
uvicorn server:app --host 0.0.0.0 --port 8000
```

### 5) Start the Node web app

From the repository root:

```bash
npm start
```

Then open:

```text
http://localhost:3000
```

## How it works

1. User uploads an audio file in the web app.
2. The Node server stores the uploaded file and forwards it to the Python FastAPI endpoint.
3. The Python service analyses the track using librosa and computes:
   - tempo and beat structure
   - RMS and zero-crossing statistics
   - spectral centroid and rolloff
   - MFCC and chroma features
   - frequency-band balance
   - event and onset timing
4. The analysis is sent through a visual-generation router.
5. The router uses a Pydantic schema and an LLM prompt to generate JSON describing a music-reactive scene.
6. The visual engine consumes that JSON to render the final animation.

## API endpoints

### Node app

- `GET /` - upload page
- `POST /upload` - upload audio and trigger audio analysis + visual generation
- `POST /separate` - forward audio/analysis to the configured Colab endpoint

### Python analysis service

- `POST /analyze` - receives an uploaded audio file and returns structured analysis JSON
- `GET /health` - health check endpoint

## Example workflow

```bash
# start backend
cd python-server && uvicorn server:app --host 0.0.0.0 --port 8000

# start frontend
cd ..
npm start
```

Then:

- open the local upload page
- choose an audio file
- wait for analysis and visual generation
- view the generated result and visual output

## Environment and runtime notes

The project expects a fairly capable local runtime because:

- audio processing can be CPU-intensive
- the LLM visual generation step may require external API access
- the visual engine may rely on browser rendering resources

If model access is unavailable or a provider fails, the app may still render a limited result or continue without visual generation depending on the failure mode.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

- librosa for audio feature extraction
- FastAPI for the Python API layer
- Express and EJS for the web application
- Google GenAI and OpenRouter for the visual generation backend

