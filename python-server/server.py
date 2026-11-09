from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import librosa
import numpy as np
import os
import tempfile
import traceback
from pydub import AudioSegment

app = FastAPI()

def load_audio(file_path: str):
    try:
        y, sr = librosa.load(file_path, sr=None, mono=True, dtype=np.float32)
        return y, sr
    except Exception:
        pass

    try:
        audio = AudioSegment.from_file(file_path)
        wav_path = file_path + ".converted.wav"
        audio.export(wav_path, format="wav")
        y, sr = librosa.load(wav_path, sr=None, mono=True, dtype=np.float32)
        os.remove(wav_path)
        return y, sr
    except Exception as e:
        raise RuntimeError(f"Failed to load audio with both librosa and pydub: {e}")

def f2(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (np.generic,)):
        return x.item()
    return float(x)

def to_native(obj):
    if isinstance(obj, dict):
        return {k: to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_native(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.generic):
        return obj.item()
    return obj

def compute_window_features(y, sr, win_s=2.0, hop_s=1.0):
    win_samples = int(win_s * sr)
    hop_samples = int(hop_s * sr)
    n_samples = len(y)
    n_windows = max(1, 1 + (n_samples - win_samples) // hop_samples)

    stft = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    mags = np.mean(stft, axis=1)

    rms = librosa.feature.rms(y=y, frame_length=win_samples, hop_length=hop_samples)[0]
    zcr = librosa.feature.zero_crossing_rate(y, frame_length=win_samples, hop_length=hop_samples)[0]
    sc = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=win_samples, hop_length=hop_samples)[0]
    sr_feat = librosa.feature.spectral_rolloff(y=y, sr=sr, n_fft=win_samples, hop_length=hop_samples)[0]
    sflat = librosa.feature.spectral_flatness(y=y, n_fft=win_samples, hop_length=hop_samples)[0]

    times = librosa.frames_to_time(np.arange(rms.shape[0]), sr=sr, hop_length=hop_samples).tolist()

    bass_mask = (freqs >= 20) & (freqs < 250)
    mid_mask = (freqs >= 250) & (freqs < 4000)
    treble_mask = (freqs >= 4000) & (freqs <= 20000)
    total_mag = np.sum(mags)
    bass_ratio = float(np.sum(mags[bass_mask])) / total_mag if total_mag > 0 else 0.0
    mid_ratio = float(np.sum(mags[mid_mask])) / total_mag if total_mag > 0 else 0.0
    treble_ratio = float(np.sum(mags[treble_mask])) / total_mag if total_mag > 0 else 0.0

    windows = []
    for i in range(rms.shape[0]):
        t = float(times[i])
        w = {
            "time_s": round(t, 3),
            "rms": round(f2(rms[i]), 6),
            "zcr": round(f2(zcr[i]), 6),
            "spectral_centroid": round(f2(sc[i]), 2),
            "spectral_rolloff": round(f2(sr_feat[i]), 2),
            "spectral_flatness": round(f2(sflat[i]), 6),
            "bass_ratio": round(bass_ratio, 4),
            "mid_ratio": round(mid_ratio, 4),
            "treble_ratio": round(treble_ratio, 4)
        }
        windows.append(w)

    return windows, rms, sc, times

def detect_events(rms, times, onset_env, onset_frames, threshold=0.3):
    events = []
    if len(rms) == 0:
        return events

    rms = np.asarray(rms)
    rms_mean = float(np.mean(rms))
    rms_std = float(np.std(rms))
    rms_min = float(np.min(rms))
    rms_max = float(np.max(rms))

    peaks = []
    drops = []
    for i in range(1, len(rms) - 1):
        if rms[i] > rms[i - 1] and rms[i] > rms[i + 1]:
            if rms[i] > rms_mean + threshold * rms_std:
                peaks.append({
                    "time_s": round(float(times[i]), 3),
                    "rms": round(float(rms[i]), 6),
                    "delta": round(float(rms[i] - rms_mean), 6)
                })
        if rms[i] < rms[i - 1] and rms[i] < rms[i + 1]:
            if rms[i] < rms_mean - threshold * rms_std:
                drops.append({
                    "time_s": round(float(times[i]), 3),
                    "rms": round(float(rms[i]), 6),
                    "delta": round(float(rms[i] - rms_mean), 6)
                })

    onset_times = librosa.frames_to_time(onset_frames, sr=44100).tolist()
    onset_strengths = onset_env[onset_frames].tolist() if len(onset_frames) > 0 else []
    onsets = []
    for t, s in zip(onset_times, onset_strengths):
        onsets.append({
            "time_s": round(float(t), 3),
            "strength": round(float(s), 6)
        })

    events = {
        "rms_peaks": peaks[:20],
        "rms_drops": drops[:20],
        "onsets": onsets[:20],
        "rms_stats": {
            "mean": round(rms_mean, 6),
            "std": round(rms_std, 6),
            "min": round(rms_min, 6),
            "max": round(rms_max, 6)
        }
    }
    return events

def compute_deltas(rms, sc, onset_env):
    max_width = max(3, min(9, rms.shape[0] - 1))
    rms_delta = librosa.feature.delta(rms.reshape(1, -1), width=max_width)[0]
    sc_delta = librosa.feature.delta(sc.reshape(1, -1), width=max_width)[0]
    onset_delta = librosa.feature.delta(onset_env.reshape(1, -1), width=max_width)[0]

    return {
        "rms_delta_mean": round(f2(np.mean(rms_delta)), 6),
        "rms_delta_std": round(f2(np.std(rms_delta)), 6),
        "spectral_centroid_delta_mean": round(f2(np.mean(sc_delta)), 6),
        "spectral_centroid_delta_std": round(f2(np.std(sc_delta)), 6),
        "onset_delta_mean": round(f2(np.mean(onset_delta)), 6),
        "onset_delta_std": round(f2(np.std(onset_delta)), 6)
    }

def compute_culled_analysis(y, sr, tempo, beat_times, onset_env, onset_frames, windows_2s, events):
    win_s = 5.0
    hop_s = 5.0
    win_samples = int(win_s * sr)
    hop_samples = int(hop_s * sr)
    n_samples = len(y)
    n_windows = max(1, 1 + (n_samples - win_samples) // hop_samples)

    stft = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop_samples))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)

    rms = librosa.feature.rms(y=y, frame_length=win_samples, hop_length=hop_samples)[0]
    zcr = librosa.feature.zero_crossing_rate(y, frame_length=win_samples, hop_length=hop_samples)[0]
    sc = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=win_samples, hop_length=hop_samples)[0]
    sflat = librosa.feature.spectral_flatness(y=y, n_fft=win_samples, hop_length=hop_samples)[0]

    times = librosa.frames_to_time(np.arange(rms.shape[0]), sr=sr, hop_length=hop_samples).tolist()

    beat_times_arr = np.array(beat_times)
    onset_times_arr = librosa.frames_to_time(onset_frames, sr=sr, hop_length=512).tolist()

    bass_mask = (freqs >= 20) & (freqs < 250)
    mid_mask = (freqs >= 250) & (freqs < 4000)
    treble_mask = (freqs >= 4000) & (freqs <= 20000)

    windows = []
    for i in range(n_windows):
        t_start = float(times[i]) if i < len(times) else i * hop_s
        t_end = t_start + win_s

        sample_start = int(t_start * sr)
        sample_end = int(t_end * sr)
        if sample_end > n_samples:
            sample_end = n_samples

        window_y = y[sample_start:sample_end]
        if len(window_y) > 0:
            window_stft = np.abs(librosa.stft(window_y, n_fft=2048))
            window_mags = np.mean(window_stft, axis=1)
            window_total = np.sum(window_mags)
            w_bass = float(np.sum(window_mags[bass_mask])) / window_total if window_total > 0 else 0.0
            w_mid = float(np.sum(window_mags[mid_mask])) / window_total if window_total > 0 else 0.0
            w_treble = float(np.sum(window_mags[treble_mask])) / window_total if window_total > 0 else 0.0
        else:
            w_bass = w_mid = w_treble = 0.0

        beats_in_window = int(np.sum((beat_times_arr >= t_start) & (beat_times_arr < t_end)))
        beat_density = beats_in_window / win_s

        onset_count = int(np.sum((np.array(onset_times_arr) >= t_start) & (np.array(onset_times_arr) < t_end))) if len(onset_times_arr) > 0 else 0

        peaks_in_window = [p for p in events.get("rms_peaks", []) if t_start <= p["time_s"] < t_end]
        drops_in_window = [d for d in events.get("rms_drops", []) if t_start <= d["time_s"] < t_end]

        rms_val = float(rms[i]) if i < len(rms) else 0.0
        sc_val = float(sc[i]) if i < len(sc) else 0.0
        sflat_val = float(sflat[i]) if i < len(sflat) else 0.0

        windows.append({
            "time_s": round(t_start, 1),
            "energy": {
                "value": round(rms_val, 6),
                "character": "",
                "trend": ""
            },
            "brightness": {
                "value": round(sc_val, 2),
                "character": "",
                "trend": ""
            },
            "tonal_character": "",
            "frequency_balance": {
                "bass_ratio": round(w_bass, 4),
                "mid_ratio": round(w_mid, 4),
                "treble_ratio": round(w_treble, 4)
            },
            "beat_density": round(beat_density, 2),
            "event_count": onset_count + len(peaks_in_window) + len(drops_in_window),
            "peaks": peaks_in_window[:10],
            "drops": drops_in_window[:10],
            "deltas": {}
        })

    if len(windows) == 0:
        return {
            "tempo_bpm": 0,
            "overall_frequency_balance": {
                "bass_ratio": 0.0,
                "mid_ratio": 0.0,
                "treble_ratio": 0.0
            },
            "windows": windows
        }

    energy_vals = np.array([w["energy"]["value"] for w in windows])
    brightness_vals = np.array([w["brightness"]["value"] for w in windows])
    flatness_vals = np.array([sflat[i] for i in range(min(len(sflat), len(windows)))])

    energy_p25 = float(np.percentile(energy_vals, 25))
    energy_p75 = float(np.percentile(energy_vals, 75))
    brightness_p25 = float(np.percentile(brightness_vals, 25))
    brightness_p75 = float(np.percentile(brightness_vals, 75))
    flatness_p25 = float(np.percentile(flatness_vals, 25))
    flatness_p75 = float(np.percentile(flatness_vals, 75))

    for i, w in enumerate(windows):
        ev = float(energy_vals[i])
        bv = float(brightness_vals[i])
        fv = float(flatness_vals[i])

        if ev > energy_p75:
            w["energy"]["character"] = "strong"
        elif ev < energy_p25:
            w["energy"]["character"] = "weak"
        else:
            w["energy"]["character"] = "moderate"

        if bv > brightness_p75:
            w["brightness"]["character"] = "bright"
        elif bv < brightness_p25:
            w["brightness"]["character"] = "dark"
        else:
            w["brightness"]["character"] = "moderate"

        if fv > flatness_p75:
            w["tonal_character"] = "noisy"
        elif fv < flatness_p25:
            w["tonal_character"] = "tonal"
        else:
            w["tonal_character"] = "mixed"

        if i > 0:
            prev_ev = float(energy_vals[i - 1])
            prev_bv = float(brightness_vals[i - 1])

            ev_delta = ev - prev_ev
            bv_delta = bv - prev_bv

            ev_trend_threshold = max(energy_p75 - energy_p25, 0.001) * 0.2
            bv_trend_threshold = max(brightness_p75 - brightness_p25, 0.1) * 0.2

            if ev_delta > ev_trend_threshold:
                w["energy"]["trend"] = "rising"
            elif ev_delta < -ev_trend_threshold:
                w["energy"]["trend"] = "falling"
            else:
                w["energy"]["trend"] = "stable"

            if bv_delta > bv_trend_threshold:
                w["brightness"]["trend"] = "rising"
            elif bv_delta < -bv_trend_threshold:
                w["brightness"]["trend"] = "falling"
            else:
                w["brightness"]["trend"] = "stable"

            w["deltas"] = {
                "energy_delta": round(ev_delta, 6),
                "brightness_delta": round(bv_delta, 2)
            }

    overall_bass = float(np.mean([w["frequency_balance"]["bass_ratio"] for w in windows])) if windows else 0.0
    overall_mid = float(np.mean([w["frequency_balance"]["mid_ratio"] for w in windows])) if windows else 0.0
    overall_treble = float(np.mean([w["frequency_balance"]["treble_ratio"] for w in windows])) if windows else 0.0
    total_bal = overall_bass + overall_mid + overall_treble
    if total_bal > 0:
        overall_bass /= total_bal
        overall_mid /= total_bal
        overall_treble /= total_bal

    return {
        "tempo_bpm": round(float(tempo), 2),
        "overall_frequency_balance": {
            "bass_ratio": round(overall_bass, 4),
            "mid_ratio": round(overall_mid, 4),
            "treble_ratio": round(overall_treble, 4)
        },
        "windows": windows
    }

def analyze_audio(file_path: str) -> dict:
    y, sr = load_audio(file_path)
    duration = float(librosa.get_duration(y=y, sr=sr))

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.asarray(tempo).flatten()[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, onset_envelope=onset_env)

    spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)
    spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
    zcr = librosa.feature.zero_crossing_rate(y)
    rms = librosa.feature.rms(y=y)
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)

    stft = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    mags = np.mean(stft, axis=1)

    bass = float(np.sum(mags[(freqs >= 20) & (freqs < 250)]))
    mid = float(np.sum(mags[(freqs >= 250) & (freqs < 4000)]))
    treble = float(np.sum(mags[(freqs >= 4000) & (freqs <= 20000)]))
    total = bass + mid + treble if (bass + mid + treble) > 0 else 1.0

    windows, w_rms, w_sc, w_times = compute_window_features(y, sr)
    events = detect_events(w_rms, w_times, onset_env, onset_frames)
    deltas = compute_deltas(w_rms, w_sc, onset_env)
    culled = compute_culled_analysis(y, sr, tempo, beat_times, onset_env, onset_frames, windows, events)

    result = {
        "tempo_bpm": round(float(tempo), 2),
        "beat_count": int(len(beat_frames)),
        "beat_times": [round(float(t), 4) for t in beat_times],
        "duration_seconds": round(duration, 2),
        "sample_rate": int(sr),
        "spectral_centroid": {
            "mean": round(float(np.mean(spectral_centroids)), 2),
            "std": round(float(np.std(spectral_centroids)), 2)
        },
        "spectral_rolloff": {
            "mean": round(float(np.mean(spectral_rolloff)), 2),
            "std": round(float(np.std(spectral_rolloff)), 2)
        },
        "zero_crossing_rate": {
            "mean": round(float(np.mean(zcr)), 6),
            "std": round(float(np.std(zcr)), 6)
        },
        "rms_energy": {
            "mean": round(float(np.mean(rms)), 6),
            "std": round(float(np.std(rms)), 6)
        },
        "mfcc_mean": [round(float(v), 4) for v in np.mean(mfccs, axis=1).tolist()],
        "chroma_mean": [round(float(v), 4) for v in np.mean(chroma, axis=1).tolist()],
        "frequency_bands": {
            "bass_20_250hz": round(bass / total, 4),
            "mid_250_4000hz": round(mid / total, 4),
            "treble_4000_20000hz": round(treble / total, 4)
        },
        "instruments_estimate": estimate_instruments(bass, mid, treble),
        "windows": windows,
        "events": events,
        "deltas": deltas,
        "culled_analysis": culled
    }
    return result

def estimate_instruments(bass: float, mid: float, treble: float) -> dict:
    total = bass + mid + treble
    bass_r = bass / total
    mid_r = mid / total
    treble_r = treble / total

    estimates = []
    if bass_r > 0.45:
        estimates.append("heavy_bass")
    if treble_r > 0.35:
        estimates.append("bright_treble")
    if mid_r > 0.50:
        estimates.append("vocal_or_mid_heavy")
    if not estimates:
        estimates.append("balanced")

    return {
        "dominant_bands": estimates,
        "bass_ratio": round(bass_r, 4),
        "mid_ratio": round(mid_r, 4),
        "treble_ratio": round(treble_r, 4)
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        analysis = analyze_audio(tmp_path)
        analysis["filename"] = file.filename
        analysis["file_size_bytes"] = len(content)
        return JSONResponse(content=to_native(analysis))
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.get("/health")
async def health():
    return {"status": "ok"}
