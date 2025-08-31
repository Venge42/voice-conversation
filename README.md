# Voice Conversation Bot

A voice conversation application with AI chatbot capabilities.

## Features

- Real-time voice conversation with AI bots
- Multiple bot configurations support
- WebSocket-based communication
- Voice activity detection
- Audio streaming

## Bot Selection

The application now supports multiple bot configurations. Users can:

1. Select from available bots using the dropdown menu
2. Connect to the selected bot for voice conversation
3. Switch between different bot personalities

### Available Bots

Currently, the following bots are available:
- `bot1` - Default bot configuration
- `bot2` - Alternative bot configuration

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   cd client && npm install
   ```

2. Set up environment variables (see `env.example`)

3. Start the server:
   ```bash
   python server.py
   ```

4. Start the client:
   ```bash
   cd client && npm run dev
   ```

5. Open your browser to `http://localhost:5173`

## Usage

1. Select a bot from the dropdown menu
2. Click "Connect" to establish a connection
3. Allow microphone access when prompted
4. Start speaking to interact with the bot
5. Click "Disconnect" when finished

## API Endpoints

- `GET /bots` - Returns list of available bot configurations
- `POST /connect` - Establishes WebSocket connection for voice chat
- `WS /ws` - WebSocket endpoint for real-time communication

## Development

- Backend: Python with FastAPI and Pipecat
- Frontend: TypeScript with Vite
- Audio: WebRTC for real-time audio streaming