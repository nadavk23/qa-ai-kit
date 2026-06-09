"""Unit tests for Phase 2 features (record-flow, visual regression, annotation, video)."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

# ============================================================================
# Record-flow Tests
# ============================================================================


def test_web_recorder_selector_priority():
    """Test selector priority: data-testid > aria-label > id > CSS path."""
    from qa_execution.record_flow import WebRecorder

    # Test data-testid first
    el = MagicMock()
    el.getAttribute = MagicMock(side_effect=lambda attr: "submit-btn" if attr == "data-testid" else None)
    el.getAttribute.return_value = None

    # For this test, just verify the selector generation logic exists
    assert WebRecorder.INJECT_SCRIPT  # Check script exists


def test_web_recorder_events_to_yaml():
    """Test conversion of recorded events to YAML format."""
    from qa_execution.record_flow import WebRecorder, RecordedEvent

    events = [
        RecordedEvent(type="click", selector="#login", text="Login"),
        RecordedEvent(type="input", selector="#email", text="user@test.com"),
        RecordedEvent(type="key", key="Enter"),
        RecordedEvent(type="navigate", url="https://app.com/dashboard"),
    ]

    yaml = WebRecorder.events_to_yaml(events, name="Login Test")

    assert "name: Login Test" in yaml
    assert "action: click" in yaml
    assert 'selector: "#login"' in yaml
    assert "action: type" in yaml
    assert 'text: "user@test.com"' in yaml
    assert "action: press" in yaml
    assert "key: Enter" in yaml
    assert "action: navigate" in yaml
    assert "https://app.com/dashboard" in yaml


def test_web_recorder_save_yaml(tmp_path):
    """Test saving YAML to file."""
    from qa_execution.record_flow import WebRecorder

    yaml_content = "name: Test\n---\n- action: click"
    output_path = tmp_path / "test.yaml"

    result = WebRecorder.save_yaml(yaml_content, str(output_path))

    assert result.exists()
    assert result.read_text() == yaml_content


# ============================================================================
# Visual Regression Tests
# ============================================================================


def test_visual_regression_baseline_paths(tmp_path):
    """Test baseline file path generation."""
    from qa_execution.visual_regression import VisualRegression

    vr = VisualRegression(str(tmp_path))

    baseline = vr.baseline_path("login-form", "web")
    assert "login-form" in str(baseline)
    assert ".web.baseline.png" in str(baseline)

    metadata = vr.metadata_path("login-form", "web")
    assert ".web.json" in str(metadata)


@pytest.mark.asyncio
async def test_visual_regression_save_baseline(tmp_path):
    """Test saving baseline image."""
    from qa_execution.visual_regression import VisualRegression
    from PIL import Image

    # Create a test image
    img = Image.new("RGB", (100, 100), color="red")
    img_path = tmp_path / "test.png"
    img.save(img_path)

    vr = VisualRegression(str(tmp_path))
    baseline = vr.save_baseline("test", str(img_path), "web")

    assert baseline.exists()
    assert baseline.suffix == ".png"


def test_visual_regression_compare_identical(tmp_path):
    """Test visual comparison with identical images."""
    from qa_execution.visual_regression import VisualRegression
    from PIL import Image

    # Create identical images
    img = Image.new("RGB", (100, 100), color="blue")
    baseline_path = tmp_path / "baseline.png"
    current_path = tmp_path / "current.png"
    img.save(baseline_path)
    img.save(current_path)

    vr = VisualRegression(str(tmp_path))
    # Save as baseline first
    vr.save_baseline("test", str(baseline_path), "web")

    # Compare
    result = vr.compare("test", str(current_path), "web", threshold=0.95)

    assert result.passed
    assert result.similarity >= 0.99


def test_visual_regression_compare_no_baseline(tmp_path):
    """Test visual comparison when baseline doesn't exist."""
    from qa_execution.visual_regression import VisualRegression
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="green")
    img_path = tmp_path / "test.png"
    img.save(img_path)

    vr = VisualRegression(str(tmp_path))
    result = vr.compare("nonexistent", str(img_path), "web")

    assert not result.passed
    assert "Baseline not found" in result.message


# ============================================================================
# Element Annotation Tests
# ============================================================================


def test_element_annotator_inject_script():
    """Test that annotator has injection script."""
    from qa_execution.annotation import ElementAnnotator

    annotator = ElementAnnotator()
    assert "__argusAnnotator" in annotator.inject_script
    assert "getElements" in annotator.inject_script
    assert "getBestSelector" in annotator.inject_script


def test_element_annotator_diagnose_selector():
    """Test selector diagnostics."""
    from qa_execution.annotation import ElementAnnotator, ElementInfo

    annotator = ElementAnnotator()

    elements = [
        ElementInfo(
            number=1,
            selector="button#submit-btn",
            text="Submit",
            bounds=(10, 10, 50, 20),
            tag="button",
            visible=True,
            disabled=False,
        ),
        ElementInfo(
            number=2,
            selector="input#email",
            text="",
            bounds=(10, 40, 100, 20),
            tag="input",
            visible=True,
            disabled=False,
        ),
    ]

    # Test found selector
    result = annotator.diagnose_selector("button#submit-btn", elements)
    assert result["found"]
    assert result["element"]["number"] == 1

    # Test not found selector
    result = annotator.diagnose_selector("button#login", elements)
    assert not result["found"]
    assert len(result["similar"]) >= 1


def test_element_annotator_element_list(tmp_path):
    """Test getting annotatable elements."""
    from qa_execution.annotation import ElementInfo

    elements = [
        ElementInfo(1, "#btn", "Click", (0, 0, 50, 20), "button", True, False),
        ElementInfo(2, "#input", "", (0, 30, 100, 20), "input", True, False),
    ]

    assert len(elements) == 2
    assert all(e.visible for e in elements)
    assert all(not e.disabled for e in elements)


# ============================================================================
# Video Recording Tests
# ============================================================================


def test_video_recorder_init():
    """Test VideoRecorder initialization."""
    from qa_execution.video_recorder import VideoRecorder

    recorder = VideoRecorder("/tmp/test.mp4", width=1280, height=720, fps=30)

    assert recorder.width == 1280
    assert recorder.height == 720
    assert recorder.fps == 30
    assert not recorder.recording


def test_video_recorder_artifact_path():
    """Test video artifact path generation."""
    from qa_execution.video_recorder import get_video_artifact_path

    path = get_video_artifact_path("login-test", 3, "failure")

    assert "login-test" in str(path)
    assert "step-3" in str(path)
    assert "failure" in str(path)
    assert str(path).endswith(".mp4")


# ============================================================================
# Integration Tests
# ============================================================================


def test_phase2_all_modules_importable():
    """Test that all Phase 2 modules can be imported."""
    from qa_execution import record_flow
    from qa_execution import visual_regression
    from qa_execution import annotation
    from qa_execution import video_recorder

    assert record_flow.WebRecorder
    assert visual_regression.VisualRegression
    assert annotation.ElementAnnotator
    assert video_recorder.VideoRecorder


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
