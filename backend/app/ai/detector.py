import os
import sys
# Inject workspace paths to fix IDE red lines and Render imports
_app_dir = os.path.dirname(os.path.abspath(__file__))
while os.path.basename(_app_dir) != 'app' and _app_dir != os.path.dirname(_app_dir):
    _app_dir = os.path.dirname(_app_dir)
_backend_dir = os.path.dirname(_app_dir)
_root_dir = os.path.dirname(_backend_dir)
if _backend_dir not in sys.path: sys.path.insert(0, _backend_dir)
if _root_dir not in sys.path: sys.path.insert(0, _root_dir)
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""ClipForge AI â€” AI Highlight Detection Engine

Pipeline:
  1. Audio Analysis  â€” librosa RMS peaks â†’ timestamps
  2. Computer Vision â€” YOLO v8 killfeed detection â†’ events + timestamps
  3. Chat Sentiment  â€” Twitch/YouTube chat emoji/keyword clustering (optional)
  4. Fusion Scoring  â€” Weighted multi-signal score per second
  5. Clip Selection  â€” Top-N windows, deduplication
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from config import settings

# â”€â”€ Optional heavy-dependency imports (fail-safe) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# The server starts normally even if these packages are not installed.
# Install them only when you need the full AI pipeline:
#   pip install opencv-python-headless numpy librosa soundfile ultralytics
try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None          # type: ignore[assignment]
    np  = None          # type: ignore[assignment]
    _CV2_AVAILABLE = False

try:
    import librosa
    import soundfile as sf
    _LIBROSA_AVAILABLE = True
except ImportError:
    librosa = None      # type: ignore[assignment]
    sf      = None      # type: ignore[assignment]
    _LIBROSA_AVAILABLE = False

try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    YOLO = None         # type: ignore[assignment]
    _YOLO_AVAILABLE = False


# â”€â”€ Data structures â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@dataclass
class AudioPeak:
    timestamp: float   # seconds
    rms: float         # energy value
    percentile: float  # 0-1

@dataclass
class CVEvent:
    timestamp: float
    event_type: str    # "kill", "victory", "death", "multi_kill", "down"
    confidence: float
    bbox: Optional[Tuple[int, int, int, int]] = None

@dataclass
class HighlightMoment:
    timestamp: float
    duration: float
    score: float        # 0-10 composite
    clip_type: str      # kill | funny | victory | audio | chat
    events: List[dict]
    title: str


# â”€â”€ Audio Analysis â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class AudioAnalyzer:
    """Detects audio peaks using librosa RMS energy."""

    def __init__(self, rms_percentile: float = 0.85):
        self.rms_percentile = rms_percentile

    def extract_peaks(self, audio_path: str) -> List[AudioPeak]:
        """Load audio and find RMS energy spikes."""
        try:
            y, sr = librosa.load(audio_path, sr=22050, mono=True)
        except Exception as e:
            print(f"[AudioAnalyzer] Load error: {e}")
            return []

        # Compute RMS energy with hop_length=512 â†’ ~23ms per frame
        frame_length = 2048
        hop_length = 512
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=hop_length)

        threshold = np.percentile(rms, self.rms_percentile * 100)
        peaks: List[AudioPeak] = []

        in_peak = False
        for i, (t, r) in enumerate(zip(times, rms)):
            if r >= threshold and not in_peak:
                # Only keep 1 peak per 5-second window (avoid flood)
                if not peaks or (t - peaks[-1].timestamp) > 5.0:
                    percentile_rank = float(np.mean(rms <= r))
                    peaks.append(AudioPeak(
                        timestamp=float(t),
                        rms=float(r),
                        percentile=percentile_rank,
                    ))
                    in_peak = True
            elif r < threshold:
                in_peak = False

        print(f"[AudioAnalyzer] Detected {len(peaks)} audio peaks")
        return peaks


# â”€â”€ Computer Vision Detector â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class CVDetector:
    """YOLO v8 game UI event detector."""

    GAME_CLASSES = {
        0: ("kill",      0.85),
        1: ("death",     0.70),
        2: ("victory",   0.95),
        3: ("defeat",    0.60),
        4: ("multi_kill",0.90),
        5: ("down",      0.80),
        6: ("assist",    0.65),
        7: ("headshot",  0.88),
    }

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or settings.YOLO_MODEL_PATH
        self._model: Optional[YOLO] = None

    def _load_model(self) -> YOLO:
        if self._model is None:
            if os.path.exists(self.model_path):
                print(f"[CVDetector] Loading custom model: {self.model_path}")
                self._model = YOLO(self.model_path)
            else:
                print(f"[CVDetector] Custom model not found, using base: {settings.YOLO_BASE_MODEL}")
                self._model = YOLO(settings.YOLO_BASE_MODEL)
        return self._model

    def analyze_video(
        self,
        video_path: str,
        sample_fps: int = None,
        game: str = "BGMI",
    ) -> List[CVEvent]:
        """Sample frames and run YOLO inference."""
        sample_fps = sample_fps or settings.CV_SAMPLE_FPS
        model = self._load_model()
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, int(source_fps / sample_fps))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        events: List[CVEvent] = []
        frame_idx = 0
        last_event_time = -10.0  # cooldown tracker

        print(f"[CVDetector] Analyzing {total_frames} frames at {sample_fps} fps samples")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = frame_idx / source_fps

                # Run inference
                results = model(frame, verbose=False, conf=0.45)

                for result in results:
                    for box in (result.boxes or []):
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        if cls_id in self.GAME_CLASSES:
                            event_type, min_conf = self.GAME_CLASSES[cls_id]
                            if conf >= min_conf and (timestamp - last_event_time) > 3.0:
                                bbox = tuple(box.xyxy[0].cpu().numpy().astype(int).tolist())
                                events.append(CVEvent(
                                    timestamp=timestamp,
                                    event_type=event_type,
                                    confidence=conf,
                                    bbox=bbox,
                                ))
                                last_event_time = timestamp

            frame_idx += 1

        cap.release()
        print(f"[CVDetector] Detected {len(events)} CV events")
        return events


# â”€â”€ Fusion Scorer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class HighlightScorer:
    """
    Fuses audio peaks + CV events â†’ ranked highlight windows.

    Score formula per window:
      base     = 1.0 for audio peak
      cv_boost = {kill:3.5, multi_kill:5.0, victory:4.0, headshot:3.0, ...}
      density  = 1 + 0.5 Ã— (num events in window âˆ’ 1)
      final    = min(10, base + cv_boost Ã— density)
    """

    CV_WEIGHTS = {
        "kill":       3.5,
        "multi_kill": 5.0,
        "victory":    4.0,
        "headshot":   3.0,
        "down":       2.0,
        "death":      1.5,
        "assist":     1.0,
        "defeat":     0.5,
    }

    CLIP_TYPE_MAP = {
        "kill":       "kill",
        "multi_kill": "kill",
        "headshot":   "kill",
        "victory":    "victory",
        "death":      "funny",
        "defeat":     "funny",
    }

    def score(
        self,
        audio_peaks: List[AudioPeak],
        cv_events: List[CVEvent],
        video_duration: float,
        clip_duration: int = 30,
        max_clips: int = 5,
        window_before: int = 5,
    ) -> List[HighlightMoment]:
        """Produce top-N highlight windows."""

        # Build a per-second score array
        duration_int = max(1, int(video_duration))
        score_arr = np.zeros(duration_int, dtype=float)
        event_map: Dict[int, List[dict]] = {}

        # Audio contribution
        for peak in audio_peaks:
            t = min(int(peak.timestamp), duration_int - 1)
            score_arr[t] += 1.0 + (peak.percentile * 2.0)

        # CV contribution
        for ev in cv_events:
            t = min(int(ev.timestamp), duration_int - 1)
            weight = self.CV_WEIGHTS.get(ev.event_type, 1.0) * ev.confidence
            score_arr[t] += weight
            event_map.setdefault(t, []).append({
                "type":       ev.event_type,
                "confidence": round(ev.confidence, 2),
                "timestamp":  round(ev.timestamp, 2),
            })

        # Sliding window sum (clip_duration window, centred on each second)
        half = clip_duration // 2
        window_scores = np.convolve(score_arr, np.ones(clip_duration), mode='same')

        # Pick top-N non-overlapping peaks
        highlights: List[HighlightMoment] = []
        used_ranges: List[Tuple[float, float]] = []

        for _ in range(max_clips * 3):   # over-sample, then trim
            if len(highlights) >= max_clips:
                break
            peak_t = int(np.argmax(window_scores))
            if window_scores[peak_t] <= 0:
                break

            # Start/end
            start = max(0.0, peak_t - window_before)
            end   = min(video_duration, start + clip_duration)
            start = max(0.0, end - clip_duration)

            # Overlap check (min 10s separation)
            overlaps = any(
                not (end <= us or start >= ue)
                for us, ue in used_ranges
            )
            if overlaps:
                window_scores[peak_t] = 0
                continue

            # Gather events in this window
            window_events = []
            for t_s in range(int(start), min(int(end) + 1, duration_int)):
                window_events.extend(event_map.get(t_s, []))

            # Determine clip type from dominant CV event
            clip_type = "audio"
            if window_events:
                dominant = max(window_events, key=lambda e: self.CV_WEIGHTS.get(e["type"], 0))
                clip_type = self.CLIP_TYPE_MAP.get(dominant["type"], "kill")

            # Final score capped 0-10
            raw_score = window_scores[peak_t]
            final_score = min(10.0, round(raw_score / max(1, len(audio_peaks) + len(cv_events)) * 30, 1))
            if not cv_events and not audio_peaks:
                final_score = 5.0

            title = self._auto_title(clip_type, window_events)

            highlights.append(HighlightMoment(
                timestamp=peak_t,
                duration=float(clip_duration),
                score=final_score,
                clip_type=clip_type,
                events=window_events,
                title=title,
            ))
            used_ranges.append((start, end))

            # Zero out used region
            window_scores[max(0, peak_t - half): min(duration_int, peak_t + half)] = 0

        highlights.sort(key=lambda h: h.score, reverse=True)
        print(f"[HighlightScorer] Selected {len(highlights)} highlights")
        return highlights[:max_clips]

    def _auto_title(self, clip_type: str, events: List[dict]) -> str:
        """Generate a human-readable clip title."""
        kills = [e for e in events if e["type"] in ("kill", "multi_kill", "headshot")]
        if clip_type == "victory":
            return "Victory Screen"
        if len(kills) >= 3:
            return f"{len(kills)}-Kill Clutch"
        if len(kills) == 2:
            return "Double Kill Highlight"
        if events:
            return f"{events[0]['type'].replace('_',' ').title()} Highlight"
        return "AI Highlight Clip"


# â”€â”€ Main Detector (used by workers) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class ClipDetector:
    """End-to-end highlight detection for a local video file."""

    def __init__(self):
        self.audio_analyzer = AudioAnalyzer(settings.AUDIO_RMS_PERCENTILE)
        self.cv_detector    = CVDetector()
        self.scorer         = HighlightScorer()

    def run(
        self,
        video_path: str,
        audio_path: Optional[str] = None,
        game: str = "BGMI",
        max_clips: int = 5,
        clip_duration: int = 30,
    ) -> List[HighlightMoment]:
        """Full pipeline: audio â†’ CV â†’ score â†’ return highlights."""
        video_path = str(video_path)
        print(f"\n[ClipDetector] Starting pipeline for: {video_path}")

        # Get video duration
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        video_duration = frame_count / fps
        cap.release()

        # 1. Audio analysis
        audio_src = audio_path or video_path  # librosa can read mp4 directly
        audio_peaks = self.audio_analyzer.extract_peaks(audio_src)

        # 2. CV analysis
        cv_events = self.cv_detector.analyze_video(video_path, game=game)

        # 3. Score & select
        highlights = self.scorer.score(
            audio_peaks=audio_peaks,
            cv_events=cv_events,
            video_duration=video_duration,
            clip_duration=clip_duration,
            max_clips=max_clips,
        )

        print(f"[ClipDetector] Pipeline complete. {len(highlights)} highlights.")
        return highlights

