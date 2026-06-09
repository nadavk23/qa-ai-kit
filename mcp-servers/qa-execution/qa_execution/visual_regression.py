"""Visual regression: Screenshot baseline comparison with perceptual hashing."""

import hashlib
import json
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class VisualDiff:
    """Result of visual comparison."""
    passed: bool
    similarity: float  # 0.0-1.0
    message: str
    diff_image_path: Optional[str] = None


class VisualRegression:
    """Screenshot baseline management and comparison."""

    def __init__(self, snapshot_dir: str = "tests/snapshots"):
        self.snapshot_dir = Path(snapshot_dir).expanduser()
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def baseline_path(self, name: str, platform: str = "web") -> Path:
        """Get baseline image path."""
        return self.snapshot_dir / f"{name}.{platform}.baseline.png"

    def metadata_path(self, name: str, platform: str = "web") -> Path:
        """Get metadata path (hash, dimensions)."""
        return self.snapshot_dir / f"{name}.{platform}.json"

    def save_baseline(self, name: str, image_path: str, platform: str = "web") -> Path:
        """Save screenshot as baseline."""
        try:
            from PIL import Image
        except ImportError:
            raise RuntimeError("Pillow not installed. Install with: pip install Pillow")

        source = Path(image_path).expanduser()
        if not source.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        dest = self.baseline_path(name, platform)
        image = Image.open(source)
        image.save(dest)

        # Save metadata
        metadata = {
            "name": name,
            "platform": platform,
            "width": image.width,
            "height": image.height,
            "hash": self._image_hash(image),
        }
        self.metadata_path(name, platform).write_text(json.dumps(metadata, indent=2))

        return dest

    def compare(
        self,
        name: str,
        current_image_path: str,
        platform: str = "web",
        threshold: float = 0.95,
    ) -> VisualDiff:
        """Compare current screenshot to baseline."""
        try:
            from PIL import Image, ImageDraw, ImageChops
            import numpy as np
        except ImportError:
            raise RuntimeError("Pillow/numpy not installed. Install with: pip install Pillow numpy")

        baseline_path = self.baseline_path(name, platform)
        current_path = Path(current_image_path).expanduser()

        if not baseline_path.exists():
            return VisualDiff(
                passed=False,
                similarity=0.0,
                message=f"Baseline not found: {baseline_path}. Run baseline_save first.",
            )

        if not current_path.exists():
            raise FileNotFoundError(f"Current image not found: {current_image_path}")

        baseline = Image.open(baseline_path)
        current = Image.open(current_path)

        # Check dimensions match
        if baseline.size != current.size:
            return VisualDiff(
                passed=False,
                similarity=0.0,
                message=f"Size mismatch: baseline {baseline.size} vs current {current.size}",
            )

        # Calculate SSIM (perceptual similarity)
        try:
            from skimage.metrics import structural_similarity as ssim

            baseline_arr = np.array(baseline.convert("RGB"))
            current_arr = np.array(current.convert("RGB"))

            similarity = ssim(baseline_arr, current_arr, channel_axis=2, data_range=255)
        except ImportError:
            # Fallback: pixel-by-pixel comparison
            diff = ImageChops.difference(baseline, current)
            pixels = list(diff.getdata())
            changed = sum(1 for p in pixels if p != (0, 0, 0))
            similarity = 1.0 - (changed / len(pixels))

        passed = similarity >= threshold

        if not passed:
            # Generate diff image
            diff_path = self.snapshot_dir / f"{name}.{platform}.diff.png"
            self._generate_diff_image(baseline, current, diff_path)
        else:
            diff_path = None

        return VisualDiff(
            passed=passed,
            similarity=similarity,
            message=f"Similarity: {similarity:.1%} (threshold: {threshold:.1%})",
            diff_image_path=str(diff_path) if diff_path else None,
        )

    def _generate_diff_image(self, baseline, current, output_path):
        """Generate visual diff showing differences."""
        try:
            from PIL import Image, ImageDraw
            import numpy as np
        except ImportError:
            return

        baseline_arr = np.array(baseline.convert("RGB"))
        current_arr = np.array(current.convert("RGB"))

        # Create diff visualization (red = different pixels)
        diff = np.abs(baseline_arr.astype(int) - current_arr.astype(int))
        diff = np.any(diff > 30, axis=2)  # Threshold for "significant" changes

        # Create output image
        output = Image.new("RGB", baseline.size, (255, 255, 255))
        output.paste(baseline, (0, 0))

        # Overlay red for different pixels
        diff_img = Image.new("RGBA", baseline.size, (255, 0, 0, 0))
        draw = ImageDraw.Draw(diff_img)

        for i in range(diff.shape[0]):
            for j in range(diff.shape[1]):
                if diff[i, j]:
                    draw.point((j, i), fill=(255, 0, 0, 128))

        output.paste(diff_img, (0, 0), diff_img)
        output.save(output_path)

    @staticmethod
    def _image_hash(image) -> str:
        """Generate SHA256 hash of image."""
        import io

        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return hashlib.sha256(buffered.getvalue()).hexdigest()

    def approve_baseline(self, name: str, current_image_path: str, platform: str = "web") -> Path:
        """Approve current image as new baseline."""
        return self.save_baseline(name, current_image_path, platform)

    def list_baselines(self) -> list[str]:
        """List all saved baselines."""
        baselines = set()
        for f in self.snapshot_dir.glob("*.baseline.png"):
            name = f.stem.replace(".baseline", "").rsplit(".", 1)[0]
            baselines.add(name)
        return sorted(baselines)
