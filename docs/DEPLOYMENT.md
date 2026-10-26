# Deploying and enabling Foundry for judging

## Two independent things must work

1. The **FastAPI web app** hosts `/studio`, `/about`, the synthetic data API and the Babylon.js/2D visualization.
2. The **Microsoft Foundry model** is called by the backend on demand. The Foundry project endpoint is a service endpoint, **not a web hosting URL**. Creating a Foundry model does not deploy the FastAPI website.

## Local testing (Azure CLI)

Run the commands in the repository README. `AzureCliCredential()` uses your own `az login` session. This is sufficient for the developer's local demo and for an offline test build, but cannot be assumed to work on a public Azure host.

## Azure-hosted demo (managed identity)

Deploy the `backend/` directory as a Python web app (for instance, Azure App Service or Azure Container Apps). Configure startup so the app serves port 8000 or the hosting platform's expected port, for example:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Install `requirements-ai.txt`, not only `requirements.txt`. Set **application environment variables** (no secret committed to source control):

```text
TID_AI_PROVIDER=foundry
TID_AZURE_CREDENTIAL=managed_identity
FOUNDRY_PROJECT_ENDPOINT=https://YOUR-ACCOUNT.services.ai.azure.com/api/projects/YOUR-PROJECT
FOUNDRY_MODEL=YOUR-DEPLOYMENT-NAME
```

Enable a **system-assigned managed identity** on the Azure web-hosting resource. Give that identity the minimum role that authorizes Foundry model inference at the appropriate **Foundry resource** scope; consult the current Microsoft Foundry RBAC guidance and verify with a real test request. For Foundry inference, a Foundry User assignment on the resource/account is the documented general approach. Assigning rights to your personal account does not give the deployed app rights.

For a hosted app that does not provide managed identity, you must instead configure an appropriate supported workload credential securely. Do not embed Azure CLI login files, passwords, personal access tokens or model keys in public source code.

## Verify public access

- Visit `/health`, `/studio`, and `/about` in a private/incognito browser session without Azure login.
- Choose a synthetic scenario and defender; verify both synchronized views and nine movement decisions.
- Generate commentary; verify the status **Microsoft Foundry agents** and `generated_by_ai: true` in the API response, not an offline fallback.
- Use explicit message and request limits, monitor Azure quotas and costs, and guard against public abuse of an unauthenticated billable commentary endpoint.
- Keep the test instance free to access until **November 10, 2026**, the end of the published judging period (check for official schedule changes).

**Hosting and Azure model calls can incur charges.** The repository does not provision Azure services automatically. Only enable a publicly accessible billable endpoint after checking quotas, pricing, and access controls.

## If a public Azure host is unavailable

The official rules also allow a **functioning demo or test build** with testing instructions. Local reproduction of the offline mode is documented; the Foundry mode additionally requires suitable cloud permissions and a deployed model. Make sure the judges have working access to the actual features shown in the video. Public GitHub + YouTube alone does not automatically provide that access.

Useful official documentation:
- Official hackathon rules: https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md
- Foundry RBAC: https://learn.microsoft.com/en-us/azure/foundry/concepts/rbac-foundry
- Agent Framework Foundry model provider: https://learn.microsoft.com/en-us/agent-framework/agents/providers/microsoft-foundry
