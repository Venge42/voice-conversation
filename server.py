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
# In production, you might want to restrict this to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from state import *


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Get bot from query parameters
    bot_config = websocket.query_params.get("bot", "bot1")

    # Generate a unique session ID for this bot session
    session_id = f"{bot_config}_{uuid.uuid4().hex[:8]}"

    # Store the bot configuration for this session
    connection_bot_configs[session_id] = bot_config

    print(f"WebSocket connection accepted for bot: {bot_config}, session: {session_id}")

    # Store the session ID in the websocket object for later use
    websocket.session_id = session_id

    try:
        await run_bot(websocket, bot_config, session_id, connection_light_controllers)
    except asyncio.CancelledError:
        print(f"WebSocket connection cancelled for {session_id}")
    except Exception as e:
        print(f"Exception in run_bot for {session_id}: {e}")
    finally:
        # Clean up connection when it's closed
        if session_id in connection_bot_configs:
            del connection_bot_configs[session_id]
        if session_id in connection_light_controllers:
            del connection_light_controllers[session_id]
        print(f"Cleaned up connection: {session_id}")


@app.websocket("/light-ws")
async def light_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Get bot from query parameters
    bot_config = websocket.query_params.get("bot", "bot1")

    # Find the most recent session ID for this bot (voice WebSocket should be created first)
    session_id = None
    for sid, bot in list(connection_bot_configs.items())[
        ::-1
    ]:  # Reverse to get most recent first
        if bot == bot_config:
            session_id = sid
            break

    if not session_id:
        # If no matching session found, reject the connection
        print(
            f"❌ No voice WebSocket session found for {bot_config}, rejecting light WebSocket"
        )
        await websocket.close(code=1000, reason="No voice session available")
        return
    else:
        print(f"🔌 Found existing session ID for light WebSocket: {session_id}")

    # Store the light WebSocket connection using the session ID
    light_websocket_connections[session_id] = websocket

    print(
        f"🔌 Light WebSocket connection accepted for bot: {bot_config}, session: {session_id}"
    )

    try:
        # Keep connection alive and forward light commands
        while True:
            # Just sleep to keep the connection alive
            await asyncio.sleep(1)

            # Check if the WebSocket is still connected
            if websocket.client_state.value != 1:  # 1 = CONNECTED
                print(f"🔌 Light WebSocket {session_id} disconnected, breaking loop")
                break

    except Exception as e:
        print(f"Light WebSocket connection closed for {session_id}: {e}")
    finally:
        # Clean up the connection
        if session_id in light_websocket_connections:
            del light_websocket_connections[session_id]
            print(f"🔌 Light WebSocket connection cleaned up: {session_id}")
            print(
                f"🔌 Remaining light connections: {list(light_websocket_connections.keys())}"
            )
        else:
            print(
                f"🔌 Light WebSocket connection {session_id} not found in dictionary during cleanup"
            )


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


@app.api_route("/connect", methods=["GET", "POST"])
async def bot_connect(request: Request) -> Dict[Any, Any]:
    # Support both POST (JSON body) and GET (query param)
    bot = "bot1"
    if request.method == "POST":
        try:
            body = await request.json()
            bot = body.get("bot", "bot1")
        except Exception:
            # Fall back to query parameter if no/invalid JSON
            bot = request.query_params.get("bot", "bot1")
    else:
        bot = request.query_params.get("bot", "bot1")

    server_mode = os.getenv("WEBSOCKET_SERVER", "fast_api")
    server_url = os.getenv("SERVER_URL", "localhost:7860")

    # Choose ws/wss intelligently if not explicitly set
    env_ws_protocol = os.getenv("WS_PROTOCOL")
    if env_ws_protocol:
        ws_protocol = env_ws_protocol
    else:
        # Default to ws for localhost, wss otherwise
        if "localhost" in server_url or "127.0.0.1" in server_url:
            ws_protocol = "ws"
        else:
            ws_protocol = "wss"
    print(f"Server URL: {server_url}")
    print(f"WebSocket protocol: {ws_protocol}")

    if server_mode == "websocket_server":
        # In websocket_server mode, the websocket server runs on port 8765
        ws_url = f"{ws_protocol}://localhost:8765"
    else:
        # In fast_api mode, use the FastAPI WebSocket endpoint
        # Always use wss:// for consistency
        ws_url = f"{ws_protocol}://{server_url}/ws?bot={bot}"

    print(f"Server mode: {server_mode}")
    print(f"Server URL from env: {server_url}")
    print(f"Returning WebSocket URL: {ws_url} for bot: {bot}")

    return {"ws_url": ws_url}


@app.get("/light-status")
async def get_light_status() -> Dict[str, Any]:
    """Get the status of all active light controllers."""
    return {
        "active_connections": len(connection_light_controllers),
        "connections": {
            conn_id: controller.get_status()
            for conn_id, controller in connection_light_controllers.items()
        },
    }


@app.get("/light-status/{connection_id}")
async def get_connection_light_status(connection_id: str) -> Dict[str, Any]:
    """Get the light status for a specific connection."""
    if connection_id not in connection_light_controllers:
        return {"error": "Connection not found"}

    return connection_light_controllers[connection_id].get_status()


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
