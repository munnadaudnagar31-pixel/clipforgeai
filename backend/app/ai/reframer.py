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

"""
ClipForge AI â€” FFmpeg Rendering Worker
Handles: 9:16 smart crop, audio mixing, music overlay, SFX insertion, watermark.
"""

import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple
from backend.app.config import settings


# â”€â”€ Smart Reframing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class SmartReframer:
    """
    Detects the action region in a 16:9 frame using optical flow
    and motion saliency, then crops to 9:16 centred on that region.
    """

    @staticmethod
    def compute_crop_offset(
        video_path: str,
        start_time: float,
        duration: float,
        src_w: int = 1920,
        src_h: int = 1080,
        target_w: int = 608,   # 1080 * 9/16 â‰ˆ 608
    ) -> int:
        """
        Returns the horizontal crop offset (x) that keeps the most
        motion-heavy region centred. Uses FFmpeg's 'cropdetect' and
        a quick OpenCV optical flow pass.
        In production, replace with MediaPipe/DepthAnything.
        """
        try:
            import cv2
            import numpy as np

            cap = cv2.VideoCapture(video_path)
            cap.set(cv2.CAP_PROP_POS_MSEC, start_time * 1000)

            motion_cols = np.zeros(src_w, dtype=float)
            prev_gray = None

            for _ in range(min(90, int(duration * 30))):
                ret, frame = cap.read()
                if not ret:
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if prev_gray is not None:
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_gray, gray, None,
                        0.5, 3, 15, 3, 5, 1.2, 0
                    )
                    magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
                    motion_cols += magnitude.mean(axis=0)
                prev_gray = gray

            cap.release()

            # Centre of mass of motion
            if motion_cols.sum() > 0:
                com = int(np.average(np.arange(src_w), weights=motion_cols))
            else:
                com = src_w // 2

            # Clamp to valid range
            x = max(0, min(com - target_w // 2, src_w - target_w))
            return x

        except Exception as e:
            print(f"[SmartReframer] Fallback to centre crop: {e}")
            return (src_w - target_w) // 2


# â”€â”€ FFmpeg Renderer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class FFmpegRenderer:
    """
    Renders a highlight clip from a source video using FFmpeg.
    Supports: smart crop, 9:16/16:9/1:1, music overlay, SFX, watermark.
    """

    MUSIC_DIR = Path("assets/music")
    SFX_DIR   = Path("assets/sfx")

    def render(
        self,
        source_path: str,
        output_path: str,
        start_time: float,
        duration: float,
        aspect: str = "9:16",
        quality: str = "1080p",
        watermark: bool = True,
        add_music: bool = True,
        music_file: Optional[str] = None,
        add_sfx: bool = False,
        sfx_timestamps: Optional[list] = None,
    ) -> str:
        """
        Build and run FFmpeg command for a single highlight clip.
        Returns: output_path
        """
        # Determine output resolution
        res_map = {
            "720p":       (1280, 720),
            "1080p":      (1920, 1080),
            "1080p 60fps":(1920, 1080),
            "4K":         (3840, 2160),
        }
        out_w, out_h = res_map.get(quality, (1920, 1080))
        fps = 60 if "60fps" in quality else 30

        # Determine crop for aspect ratio
        crop_filter = self._crop_filter(source_path, start_time, duration, aspect, out_w, out_h)

        # Build filter graph
        filter_parts = [crop_filter, f"scale={out_w}:{out_h}:flags=lanczos"]
        if watermark:
            filter_parts.append(
                "drawtext=text='ClipForge AI':fontcolor=white@0.5:"
                "fontsize=28:x=w-tw-20:y=h-th-20:shadowcolor=black:shadowx=2:shadowy=2"
            )

        vf = ",".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", source_path,
            "-t", str(duration),
            "-vf", vf,
            "-r", str(fps),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
        ]

        # Audio: mix original + optional background music
        if add_music and music_file and Path(music_file).exists():
            cmd += [
                "-i", music_file,
                "-filter_complex",
                "[0:a]volume=1.0[orig];[1:a]volume=0.3[music];[orig][music]amix=inputs=2:duration=shortest",
                "-c:a", "aac", "-b:a", "192k",
            ]
        else:
            cmd += ["-c:a", "aac", "-b:a", "192k"]

        cmd += ["-movflags", "+faststart", output_path]

        print(f"[FFmpegRenderer] Running: {' '.join(cmd[:6])} ...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed:\n{result.stderr}")

        print(f"[FFmpegRenderer] Done â†’ {output_path}")
        return output_path

    def _crop_filter(
        self,
        source_path: str,
        start_time: float,
        duration: float,
        aspect: str,
        out_w: int,
        out_h: int,
    ) -> str:
        """Return FFmpeg crop= filter string for the given aspect ratio."""
        if aspect == "9:16":
            # Smart crop: detect action region
            src_w, src_h = 1920, 1080
            target_w = int(src_h * 9 / 16)   # 607
            x_offset = SmartReframer.compute_crop_offset(source_path, start_time, duration, src_w, src_h, target_w)
            return f"crop={target_w}:{src_h}:{x_offset}:0"
        elif aspect == "1:1":
            return "crop=ih:ih:(iw-ih)/2:0"
        else:  # 16:9 â€” just use source (or pad)
            return "copy"

    def render_batch(
        self,
        source_path: str,
        highlights,            # List[HighlightMoment]
        output_dir: str,
        watermark: bool = True,
        add_music: bool = True,
        quality: str = "1080p",
        aspect: str = "9:16",
    ) -> list:
        """Render multiple clips from a source video."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        rendered = []

        for i, hl in enumerate(highlights):
            clip_filename = f"clip_{i+1}_{uuid.uuid4().hex[:8]}.mp4"
            output_path = str(Path(output_dir) / clip_filename)
            try:
                self.render(
                    source_path=source_path,
                    output_path=output_path,
                    start_time=hl.timestamp,
                    duration=hl.duration,
                    aspect=aspect,
                    quality=quality,
                    watermark=watermark,
                    add_music=add_music,
                )
                rendered.append({
                    "highlight": hl,
                    "output_path": output_path,
                    "success": True,
                })
            except Exception as e:
                print(f"[FFmpegRenderer] Failed clip {i+1}: {e}")
                rendered.append({
                    "highlight": hl,
                    "output_path": None,
                    "success": False,
                    "error": str(e),
                })

        return rendered


# â”€â”€ Thumbnail Generator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def generate_thumbnail(video_path: str, timestamp: float, output_path: str) -> str:
    """Extract a single frame as JPEG thumbnail."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True)
    return output_path

