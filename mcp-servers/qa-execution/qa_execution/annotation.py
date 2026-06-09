"""Element annotation: Numbered overlays and selector diagnostics."""

import re
from typing import Optional, List, Dict, Tuple, Any
from dataclasses import dataclass


@dataclass
class ElementInfo:
    """Information about a page element."""
    number: int
    selector: str
    text: str
    bounds: Tuple[int, int, int, int]  # x, y, width, height
    tag: str
    visible: bool
    disabled: bool


class ElementAnnotator:
    """Annotate screenshots with numbered element overlays."""

    def __init__(self):
        self.inject_script = """
        (() => {
            window.__argusAnnotator = {
                getElements: function() {
                    const elements = [];
                    let index = 1;

                    // Find all interactive elements
                    const selectors = [
                        'button', 'a', 'input', 'textarea', 'select',
                        '[role="button"]', '[role="link"]', '[onclick]'
                    ];

                    const found = new Set();

                    for (const selector of selectors) {
                        try {
                            document.querySelectorAll(selector).forEach(el => {
                                if (found.has(el)) return;
                                found.add(el);

                                const rect = el.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    elements.push({
                                        number: index++,
                                        selector: this.getBestSelector(el),
                                        text: (el.textContent || '').trim().substring(0, 50),
                                        bounds: [rect.x, rect.y, rect.width, rect.height],
                                        tag: el.tagName.toLowerCase(),
                                        visible: el.offsetParent !== null,
                                        disabled: el.disabled || el.getAttribute('aria-disabled') === 'true'
                                    });
                                }
                            });
                        } catch (e) {}
                    }

                    return elements;
                },

                getBestSelector: function(el) {
                    if (el.getAttribute('data-testid')) {
                        return `[data-testid="${el.getAttribute('data-testid')}"]`;
                    }
                    if (el.getAttribute('aria-label')) {
                        return `[aria-label="${el.getAttribute('aria-label')}"]`;
                    }
                    if (el.id) return `#${el.id}`;

                    const path = [];
                    let current = el;
                    while (current && current.nodeType === 1 && current !== document.body) {
                        let selector = current.tagName.toLowerCase();
                        if (current.id) selector += `#${current.id}`;
                        else if (current.className) {
                            const classes = current.className.split(' ')
                                .filter(c => !c.startsWith('__'))
                                .join('.');
                            if (classes) selector += `.${classes}`;
                        }
                        path.unshift(selector);
                        current = current.parentElement;
                    }
                    return path.join(' > ');
                }
            };
        })();
        """

    async def get_annotatable_elements(self, page) -> List[ElementInfo]:
        """Get all interactive elements from page."""
        await page.evaluate(self.inject_script)
        raw = await page.evaluate("window.__argusAnnotator.getElements()")

        elements = []
        for item in raw:
            elements.append(
                ElementInfo(
                    number=item["number"],
                    selector=item["selector"],
                    text=item["text"],
                    bounds=tuple(item["bounds"]),
                    tag=item["tag"],
                    visible=item["visible"],
                    disabled=item["disabled"],
                )
            )

        return elements

    async def annotate_screenshot(
        self, page, screenshot_path: str, output_path: str
    ) -> str:
        """Add numbered element boxes to screenshot."""
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise RuntimeError("Pillow not installed. Install with: pip install Pillow")

        # Get elements
        elements = await self.get_annotatable_elements(page)

        # Load screenshot
        from pathlib import Path
        input_path = Path(screenshot_path).expanduser()
        if not input_path.exists():
            raise FileNotFoundError(f"Screenshot not found: {screenshot_path}")

        image = Image.open(input_path).convert("RGB")
        draw = ImageDraw.Draw(image)

        # Try to load a nice font, fallback to default
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        except:
            font = ImageFont.load_default()

        # Draw boxes
        for elem in elements:
            if not elem.visible:
                continue

            x, y, w, h = elem.bounds
            x2, y2 = x + w, y + h

            # Draw box (green for visible, red for disabled)
            color = (200, 0, 0) if elem.disabled else (0, 200, 0)
            draw.rectangle([x, y, x2, y2], outline=color, width=2)

            # Draw number label
            label = str(elem.number)
            bbox = draw.textbbox((0, 0), label, font=font)
            label_w = bbox[2] - bbox[0] + 4
            label_h = bbox[3] - bbox[1] + 4

            draw.rectangle([x, y - label_h, x + label_w, y], fill=color)
            draw.text((x + 2, y - label_h + 2), label, font=font, fill=(255, 255, 255))

        # Save annotated image
        output = Path(output_path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output)

        # Generate element list
        element_list = "\n".join(
            [
                f"[{e.number}] {e.tag} @ {e.selector[:60]}"
                for e in elements
                if e.visible
            ]
        )

        return f"✅ Annotated: {output}\n\nElements:\n{element_list}"

    @staticmethod
    def diagnose_selector(
        selector: str, available_elements: List[ElementInfo]
    ) -> Dict[str, Any]:
        """Suggest why a selector might be failing."""
        diagnosis = {
            "selector": selector,
            "found": False,
            "suggestions": [],
            "similar": [],
        }

        # Check for exact match
        for elem in available_elements:
            if elem.selector == selector or selector in elem.selector:
                diagnosis["found"] = True
                diagnosis["element"] = {
                    "number": elem.number,
                    "text": elem.text,
                    "visible": elem.visible,
                    "disabled": elem.disabled,
                }
                break

        if not diagnosis["found"]:
            # Look for similar selectors. Tokenize on CSS delimiters (#, ., >,
            # whitespace, brackets) so "button#login" -> ["button", "login"].
            selector_lower = selector.lower()
            tokens = re.split(r"[#.>\s\[\]]+", selector_lower)
            for elem in available_elements:
                if any(
                    part in elem.selector.lower()
                    for part in tokens
                    if len(part) > 3
                ):
                    diagnosis["similar"].append(
                        {
                            "number": elem.number,
                            "selector": elem.selector,
                            "text": elem.text,
                        }
                    )

            if not diagnosis["similar"]:
                diagnosis["suggestions"].append(
                    "Selector not found. Check spelling or use annotateElements: true to see available selectors."
                )
            else:
                diagnosis["suggestions"].append(
                    f"Selector not found, but {len(diagnosis['similar'])} similar elements exist."
                )

        return diagnosis
