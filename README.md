# The Invisible Defender

> An explainable football tactics prototype built for the Microsoft × Premier League **Inside the Game: Developer Hackathon** (October 2026).

**The challenge:** Defenders can prevent attacks without making a tackle or interception. **The solution:** choose a synthetic match situation and defender, compare nine body-relative decisions, play the same moment in synchronized **2D and 3D**, and ask two AI agents to explain the underlying tactical evidence.

The prototype uses **synthetic, scripted match scenarios**. Its attacking-threat index is a **heuristic**, not xG, a calibrated interception probability, or a validated player rating. It does **not** process live Premier League match feeds or real match footage.

## Demo experience

- `/studio`: one synchronized timeline for 2D pitch and Babylon.js 3D stadium; before/after pass; defender selection; nine counterfactual moves and team-coverage decomposition.
- `/about`: research inspiration, architecture, and model limitations.
- AI Tactical Commentary: **TacticalEvidenceEditor → TacticalCommentaryWriter**, code-defined Microsoft Agent Framework agents using a deployed Microsoft Foundry model. A grounding check validates cited evidence IDs and numeric claims. When Foundry is unavailable, an explicitly labeled deterministic fallback is shown.

## Architecture

```text
Synthetic scenarios ──► Python analysis (geometry, trajectories,
                     │  teammate coverage, offside, threat index)
                     ├──► /api/player-analysis ──► 2D SVG + Babylon.js 3D
                     └──► Evidence facts ─► Foundry / Agent Framework
                                              TacticalEvidenceEditor
                                           ─► TacticalCommentaryWriter
                                           ─► Grounding validation
                                           ─► Studio commentary
```

**Foundry integration type:** code-defined Agent Framework agents calling a model deployed in a Foundry project. These are **not** standalone Prompt Agents or Hosted Agents published to Foundry Agent Service. Neither agent calculates or modifies defensive scores.

## Run locally (Windows PowerShell)

Python 3.13 and Node.js 22 are used in CI. Node.js is only needed for JavaScript tests.

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
python check_install.py
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000/studio**. The application works **without an Azure account** using deterministic commentary; this is not the AI-generated mode.

## Enable the real Microsoft Foundry agents

Deploy a supported model (for example, `gpt-5-mini`) in a Microsoft Foundry project. Install the optional AI dependencies:

```powershell
python -m pip install -r requirements-ai.txt
az login
$env:TID_AI_PROVIDER = 'foundry'
$env:TID_AZURE_CREDENTIAL = 'azure_cli'
$env:FOUNDRY_PROJECT_ENDPOINT = 'https://YOUR-ACCOUNT.services.ai.azure.com/api/projects/YOUR-PROJECT'
$env:FOUNDRY_MODEL = 'YOUR-MODEL-DEPLOYMENT-NAME'
uvicorn app.main:app --reload
```

Use the **project endpoint**, not the `/openai/v1/responses` inference URL. No API key is required when Azure Entra ID authorization is configured. Confirm the Studio explicitly shows *Microsoft Foundry agents* after generating commentary. If it reports fallback, the model call did not succeed. No model inference is performed by CI tests.

For Azure-hosted instances, set `TID_AZURE_CREDENTIAL=managed_identity` and grant the application's managed identity the required Foundry inference permissions at the Foundry resource scope. See [deployment and judging access](docs/DEPLOYMENT.md). **Do not commit tokens, keys, a real `.env` file or Azure CLI credential caches.** The public frontend never receives the Foundry identity.

## Testing

```powershell
cd backend
python -m pytest -q
python check_install.py
node --test js_tests/*.cjs
```

The repository includes GitHub Actions CI. It does not require Foundry credentials or make billable Foundry calls.

## Scientific and engineering limitations

- Positions, body directions, and events are authored synthetic inputs, not live tracking data.
- Counterfactual actions are evaluated against the same scripted attacking scenario and a simplified geometric ball-contact test.
- Team coverage and attacking-threat values are explanatory proxies; model-derived statements are distinct from measured real-world effectiveness.
- The project does not implement or claim to reproduce the trained models from the papers cited on the About page.
- Agent output is checked for evidence IDs and numeric grounding, but can still require semantic editorial review.

## Source and third-party components

The application code in this repository is original prototype code. The 3D renderer loads the Apache-2.0-licensed Babylon.js from its official development CDN (Internet required). Babylon.js recommends self-hosting the runtime for production; see [third-party notices](docs/THIRD_PARTY.md).

The interface is football-broadcast inspired and is **not affiliated with or endorsed by the Premier League**. No official match footage or Premier League trademarks are included.

**Copyright / project license:** This public submission does not itself grant an open-source license for the original application code. Third-party dependencies have their own license terms. A project-wide license may be added by the owner later.

## Hackathon submission

See [submission checklist](docs/SUBMISSION.md). In addition to this **public** repository, the official rules require a **public demo video shorter than two minutes** and **unrestricted judge testing access** through a functioning website, demo, or test build until judging is complete.
