"""Driver for router.py: reads culled analysis from stdin, generates visual JSON.

The user is expected to fill in:
  1. The Pydantic schema (VisualSchema)
  2. The intro prompt / system instruction

Output: JSON on stdout (the generated visual scene).
"""

import re
import sys
import json
import logging
from typing import Optional, List, Any

from pydantic import BaseModel, Field

from router import generate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_router")


# ---------------------------------------------------------------------------
# Color sanitisation — LLMs often emit malformed hex (e.g. "#09001flow").
# ---------------------------------------------------------------------------
_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _sanitize_color(value: Any) -> Any:
    """Return a valid hex color string, or None if unparseable."""
    if not isinstance(value, str):
        return value
    m = _HEX_RE.match(value.strip())
    if m:
        return "#" + m.group(1).upper()
    # Try to salvage: take first 6 hex chars after optional '#'
    cleaned = value.strip().lstrip("#")
    hex_only = re.sub(r"[^0-9a-fA-F]", "", cleaned)
    if len(hex_only) >= 6:
        return "#" + hex_only[:6].upper()
    return None  # unparseable


def _sanitize_colors(obj: Any) -> Any:
    """Recursively walk a JSON tree and fix any color strings."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ("color", "colors") and isinstance(v, str):
                out[k] = _sanitize_color(v)
            elif k == "colors" and isinstance(v, list):
                out[k] = [_sanitize_color(c) for c in v]
            else:
                out[k] = _sanitize_colors(v)
        return out
    if isinstance(obj, list):
        return [_sanitize_colors(x) for x in obj]
    return obj


# ===========================================================================
# Visual scene schema — must match what visual-engine/src/scene.js expects.
# ===========================================================================
class BackgroundSchema(BaseModel):
    color: Optional[str] = None
    gradient: Optional[List[str]] = None


class CameraSchema(BaseModel):
    fov: int = 75
    position: List[float] = [0.0, 2.0, 10.0]
    lookAt: Optional[List[float]] = None


class LightingSchema(BaseModel):
    type: str
    color: Optional[str] = None
    intensity: Optional[float] = None
    position: Optional[List[float]] = None
    target: Optional[List[float]] = None


class MotionSchema(BaseModel):
    type: Optional[str] = None
    speed: Optional[float] = None
    amplitude: Optional[float] = None
    frequency: Optional[float] = None
    axis: Optional[str] = None
    center: Optional[List[float]] = None
    target: Optional[List[float]] = None
    direction: Optional[int] = None
    radius: Optional[float] = None


class ObjectSchema(BaseModel):
    type: str
    id: str
    count: Optional[int] = None
    position: Optional[List[float]] = None
    rotation: Optional[List[float]] = None
    scale: Optional[List[float]] = None
    color: Optional[str] = None
    colors: Optional[List[str]] = None
    opacity: Optional[float] = None
    size: Optional[float] = None
    radius: Optional[float] = None
    tubeRadius: Optional[float] = None
    innerRadius: Optional[float] = None
    outerRadius: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    depth: Optional[float] = None
    radialSegments: Optional[int] = None
    tubularSegments: Optional[int] = None
    points: Optional[List[List[float]]] = None
    motion: Optional[MotionSchema] = None
    startTime: Optional[float] = None
    endTime: Optional[float] = None


class BloomSchema(BaseModel):
    enabled: bool = True
    strength: float = 1.5
    radius: float = 0.4
    threshold: float = 0.1


class ChromaticAberrationSchema(BaseModel):
    enabled: bool = True
    offset: float = 0.003


class VignetteSchema(BaseModel):
    enabled: bool = True
    offset: float = 0.5
    darkness: float = 1.2


class KaleidoscopeSchema(BaseModel):
    enabled: bool = True
    slices: int = 6


class GlitchSchema(BaseModel):
    enabled: bool = False
    intensity: float = 0.1


class EffectsSchema(BaseModel):
    bloom: Optional[BloomSchema] = None
    chromaticAberration: Optional[ChromaticAberrationSchema] = None
    vignette: Optional[VignetteSchema] = None
    kaleidoscope: Optional[KaleidoscopeSchema] = None
    glitch: Optional[GlitchSchema] = None


class GlobalSchema(BaseModel):
    timeScale: float = 1.0
    loop: bool = True
    duration: float = 30.0


class VisualSchema(BaseModel):
    model_config = {"extra": "allow"}

    background: Optional[BackgroundSchema] = None
    camera: Optional[CameraSchema] = None
    lighting: Optional[List[LightingSchema]] = None
    objects: Optional[List[ObjectSchema]] = None
    effects: Optional[EffectsSchema] = None
    global_settings: Optional[GlobalSchema] = Field(None, alias="global")

    def get_objects(self) -> list:
        """Return objects, falling back to common alternative field names."""
        if self.objects:
            return [o.model_dump(by_alias=True) for o in self.objects]
        # Try common alternatives the LLM might use
        for alt in ("visual_effects", "items", "elements", "shapes"):
            val = getattr(self, alt, None)
            if val:
                return [o if isinstance(o, dict) else o.model_dump(by_alias=True) for o in val]
        return []


# ===========================================================================
# TODO: Write the intro prompt / system instruction here.
# ===========================================================================
INTRO_PROMPT = """\
You are a visual director for music. Create psychedelic visual effects by analysing
the provided music analysis data. Output a JSON object matching the schema.

The "objects" field MUST be a JSON array of scene objects. Each object must have
at least "type" and "id". Valid types: particles, torus, ring, stars, sphere,
box, cylinder, cone, plane, wave, mesh. Do NOT nest objects inside other objects.
Do NOT put objects inside "visual_effects" or any other wrapper key — put them
directly in the top-level "objects" array.

The "background" field is optional. Use "color" for a solid background or
"gradient" for an array of 2+ HEX color strings.

The "lighting" field is optional — an array of light objects with "type"
(ambient, point, directional, spot) and optional "color", "intensity", "position".

The "effects" field is optional — an object with optional sub-keys:
bloom, chromaticAberration, vignette, kaleidoscope, glitch.

The "global" field is optional — an object with "timeScale", "loop", "duration".

The effects should be mesmerising and complement the energy and beats of the music. The duration and nature of the effects should match the song roughly. Avoid static effects.

Strictly avoid adding conversational text or anything else. Exclusively output JSON.
"""


def main() -> None:
    raw = sys.stdin.read()
    try:
        culled_analysis = json.loads(raw)
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON on stdin"}), file=sys.stderr)
        sys.exit(1)

    prompt = (
        INTRO_PROMPT
        + "\n\nMUSIC ANALYSIS DATA:\n"
        + json.dumps(culled_analysis, ensure_ascii=False, separators=(",", ":"))
    )

    logger.info("Generating visual scene via router...")
    result = generate(prompt, VisualSchema)

    # Ensure the output always has an "objects" key the visual engine expects.
    if not result.get("objects"):
        result["objects"] = (
            result.pop("visual_effects", None)
            or result.pop("items", None)
            or result.pop("elements", None)
            or result.pop("shapes", None)
            or []
        )

    # Sanitise colors — LLMs sometimes emit malformed hex strings.
    result = _sanitize_colors(result)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()