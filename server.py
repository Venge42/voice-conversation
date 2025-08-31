#
# Copyright (c) 2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#
import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv(override=True)

from bot_fast_api import run_bot
from bot_websocket_server import run_bot_websocket_server


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles FastAPI startup and shutdown."""
    yield  # Run app


# Initialize FastAPI app with lifespan manager
app = FastAPI(lifespan=lifespan)

# Configure CORS to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Store bot configurations per connection
connection_bot_configs = {}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Get bot from query parameters
    bot_config = websocket.query_params.get("bot", "bot1")

    # Use the WebSocket client address as connection ID
    connection_id = f"{websocket.client.host}:{websocket.client.port}"

    # Store the bot configuration for this connection
    connection_bot_configs[connection_id] = bot_config

    print(
        f"WebSocket connection accepted for bot: {bot_config}, connection: {connection_id}"
    )

    try:
        await run_bot(websocket, bot_config, connection_id)
    except Exception as e:
        print(f"Exception in run_bot: {e}")
    finally:
        # Clean up connection when it's closed
        if connection_id in connection_bot_configs:
            del connection_bot_configs[connection_id]
            print(f"Cleaned up connection: {connection_id}")


@app.get("/bots")
async def get_bots() -> Dict[str, list[str]]:
    """Return a list of available bot configurations from the lore/bots directory."""
    import os
    from pathlib import Path

    bots_dir = Path("lore/bots")
    if not bots_dir.exists():
        # Fallback to hardcoded list if directory doesn't exist
        return {"bots": ["bot1", "bot2"]}

    # Get all subdirectories in lore/bots/
    bot_dirs = [d.name for d in bots_dir.iterdir() if d.is_dir()]

    # Sort for consistent ordering
    bot_dirs.sort()

    return {"bots": bot_dirs}


from pydantic import BaseModel


class ConnectRequest(BaseModel):
    bot: str


@app.post("/connect")
async def bot_connect(request: Request) -> Dict[Any, Any]:
    # Try to get bot from JSON body first
    try:
        body = await request.json()
        bot = body.get("bot", "bot1")
    except:
        # Fallback to query parameter
        bot = request.query_params.get("bot", "bot1")

    server_mode = os.getenv("WEBSOCKET_SERVER", "fast_api")
    server_url = os.getenv("SERVER_URL", "localhost:7860")
    if server_mode == "websocket_server":
        # In websocket_server mode, the websocket server runs on port 8765
        ws_url = f"ws://localhost:8765"
    else:
        # In fast_api mode, use the FastAPI WebSocket endpoint
        ws_url = f"ws://{server_url}/ws?bot={bot}"

    print(f"Returning WebSocket URL: {ws_url} for bot: {bot}")

    return {"ws_url": ws_url}


async def main():
    server_mode = os.getenv("WEBSOCKET_SERVER", "fast_api")
    tasks = []
    try:
        if server_mode == "websocket_server":
            tasks.append(run_bot_websocket_server())

        config = uvicorn.Config(app, host="0.0.0.0", port=7860)
        server = uvicorn.Server(config)
        tasks.append(server.serve())

        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        print("Tasks cancelled (probably due to shutdown).")


if __name__ == "__main__":
    asyncio.run(main())
