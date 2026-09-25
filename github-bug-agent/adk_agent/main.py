import os
import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

AGENT_DIR = os.path.dirname(__file__)

app = get_fast_api_app(
    agent_dir=AGENT_DIR,
    session_db_url="sqlite:///./sessions.db",
    allow_origins=["*"],
    web=True,
)

@app.get("/health")
async def health():
    return {"status": "ok", "agent": "github-bug-fixer"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
