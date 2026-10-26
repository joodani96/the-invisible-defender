from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai_commentary import generate_commentary, provider_status
from .data import SCENARIOS
from .player_analysis import analyze_player, selectable_defenders

STATIC_DIR = Path(__file__).resolve().parent / "static"
app = FastAPI(title="The Invisible Defender API", version="0.9.16")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def find_scene(scenario_id: str) -> dict:
    scene = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scene


def verify_defender(scene: dict, defender_id: str) -> None:
    if defender_id not in {p["id"] for p in selectable_defenders(scene)}:
        raise HTTPException(status_code=404, detail="Selectable defender not found")


@app.get("/", include_in_schema=False)
def homepage():
    return RedirectResponse(url="/studio")


@app.get("/studio", include_in_schema=False)
def studio():
    return FileResponse(STATIC_DIR / "studio.html")


@app.get("/about", include_in_schema=False)
def about():
    return FileResponse(STATIC_DIR / "about.html")


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


@app.get("/api/scenarios")
def scenarios():
    return [
        {"id": s["id"], "title": s["title"], "subtitle": s["subtitle"], "minute": s["minute"],
         "default_defender_id": s["defender_id"], "selectable_defenders": selectable_defenders(s)}
        for s in SCENARIOS
    ]


@app.get("/api/player-analysis/{scenario_id}/{defender_id}")
def player_analysis(scenario_id: str, defender_id: str):
    scene = find_scene(scenario_id)
    verify_defender(scene, defender_id)
    return analyze_player(scene, defender_id)


class CommentaryRequest(BaseModel):
    phase: Literal["pre", "post"]
    action: str = Field(min_length=1, max_length=32, pattern=r"^[a-z_-]+$")
    audience: Literal["fan", "analyst"] = "fan"


@app.get("/api/ai/status")
def ai_status():
    return provider_status()


@app.post("/api/commentary/{scenario_id}/{defender_id}")
async def commentary(scenario_id: str, defender_id: str, request: CommentaryRequest):
    scene = find_scene(scenario_id)
    verify_defender(scene, defender_id)
    analysis = analyze_player(scene, defender_id)
    valid = {opt["action"] for opt in analysis["pre_pass"]["options"]} | {"observed"}
    if request.action not in valid:
        raise HTTPException(status_code=422, detail="Unknown defensive action")
    return await generate_commentary(analysis, request.phase, request.action, request.audience)
