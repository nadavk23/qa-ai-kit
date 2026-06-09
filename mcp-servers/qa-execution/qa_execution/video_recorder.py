"""Video recording: H.264 MP4 capture for failure debugging."""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional, List
from collections import deque


class VideoRecorder:
    """Records test execution as H.264 MP4 video."""

    def __init__(
        self,
        output_path: str,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
    ):
        self.output_path = Path(output_path).expanduser()
        self.width = width
        self.height = height
        self.fps = fps
        self.frames: deque = deque(maxlen=300)  # 10 seconds at 30 FPS
        self.recording = False
        self.process: Optional[subprocess.Popen] = None

    async def start(self) -> None:
        """Start recording (via ffmpeg)."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Start ffmpeg process
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "-",  # Read from stdin
            "-c:v", "libx264",
            "-crf", "23",  # Quality (18-28, lower = better)
            "-preset", "fast",  # Speed (ultrafast to veryslow)
            "-pix_fmt", "yuv420p",
            str(self.output_path),
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.recording = True
        except FileNotFoundError:
            raise RuntimeError(
                "ffmpeg not found. Install with: brew install ffmpeg (macOS) "
                "or apt-get install ffmpeg (Linux)"
            )

    def add_frame(self, frame_data: bytes) -> None:
        """Add a frame to the video buffer."""
        if self.recording and self.process and self.process.stdin:
            try:
                self.process.stdin.write(frame_data)
                self.process.stdin.flush()
            except (BrokenPipeError, OSError):
                self.recording = False

    async def stop(self) -> Optional[Path]:
        """Stop recording and finalize video."""
        if not self.recording or not self.process:
            return None

        self.recording = False

        if self.process.stdin:
            self.process.stdin.close()

        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()

        if self.output_path.exists() and self.output_path.stat().st_size > 0:
            return self.output_path
        return None

    async def record_page_video(
        self,
        page,
        duration_seconds: int = 300,
        test_name: str = "test",
    ) -> Optional[Path]:
        """Record page activity for specified duration."""
        try:
            await self.start()
        except RuntimeError as e:
            return None

        frame_count = 0
        max_frames = self.fps * min(duration_seconds, 300)  # Max 300 seconds

        while frame_count < max_frames and self.recording:
            try:
                # Take screenshot
                screenshot = await page.screenshot(type="png")

                # Convert PNG to raw RGB for ffmpeg
                from PIL import Image
                import io

                img = Image.open(io.BytesIO(screenshot)).convert("RGB")

                # Resize if needed
                if img.size != (self.width, self.height):
                    img = img.resize((self.width, self.height))

                # Get raw RGB data
                rgb_data = img.tobytes()
                self.add_frame(rgb_data)

                frame_count += 1
                await asyncio.sleep(1.0 / self.fps)  # Frame rate delay

            except Exception:
                break

        return await self.stop()

    @staticmethod
    async def record_until_failure(
        page,
        test_steps: callable,
        test_name: str = "test",
        output_dir: str = "artifacts",
    ) -> Optional[Path]:
        """Record test execution until failure."""
        output_path = Path(output_dir).expanduser() / f"{test_name}.mp4"
        recorder = VideoRecorder(str(output_path))

        try:
            await recorder.start()

            # Run test steps while recording
            await test_steps()

            # Test passed, don't save video
            await recorder.stop()
            if output_path.exists():
                output_path.unlink()
            return None

        except Exception as e:
            # Test failed, save video
            video_path = await recorder.stop()
            if video_path:
                print(f"📹 Video saved: {video_path} ({video_path.stat().st_size / 1024 / 1024:.1f} MB)")
            return video_path


def get_video_artifact_path(test_name: str, step_number: int, status: str = "failure") -> Path:
    """Generate video artifact path for test failures."""
    return Path("artifacts") / f"{test_name}-step-{step_number}-{status}.mp4"
