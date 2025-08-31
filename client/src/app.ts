/**
 * Copyright (c) 2024–2025, Daily
 *
 * SPDX-License-Identifier: BSD 2-Clause License
 */

/**
 * Pipecat Client Implementation
 *
 * This client connects to an RTVI-compatible bot server using WebSocket.
 *
 * Requirements:
 * - A running RTVI bot server (defaults to http://localhost:7860)
 */

import {
  PipecatClient,
  PipecatClientOptions,
  RTVIEvent,
} from '@pipecat-ai/client-js';
import { WebSocketTransport } from '@pipecat-ai/websocket-transport';

class WebsocketClientApp {
  private pcClient: PipecatClient | null = null;
  private connectBtn: HTMLButtonElement | null = null;
  private disconnectBtn: HTMLButtonElement | null = null;
  private statusSpan: HTMLElement | null = null;
  private debugLog: HTMLElement | null = null;
  private botSelect: HTMLSelectElement | null = null;
  private botAudio: HTMLAudioElement;

  constructor() {
    console.log('WebsocketClientApp');
    this.botAudio = document.createElement('audio');
    this.botAudio.autoplay = true;
    //this.botAudio.playsInline = true;
    document.body.appendChild(this.botAudio);

    this.setupDOMElements();
    this.setupEventListeners();
  }

  /**
   * Set up references to DOM elements and create necessary media elements
   */
  private setupDOMElements(): void {
    this.connectBtn = document.getElementById(
      'connect-btn'
    ) as HTMLButtonElement;
    this.disconnectBtn = document.getElementById(
      'disconnect-btn'
    ) as HTMLButtonElement;
    this.statusSpan = document.getElementById('connection-status');
    this.debugLog = document.getElementById('debug-log');
    this.botSelect = document.getElementById('bot-select') as HTMLSelectElement;
  }

  /**
   * Set up event listeners for connect/disconnect buttons
   */
  private setupEventListeners(): void {
    this.connectBtn?.addEventListener('click', () => this.connect());
    this.disconnectBtn?.addEventListener('click', () => this.disconnect());
    
    // Initially disable connect button until a bot is selected
    if (this.connectBtn) {
      this.connectBtn.disabled = true;
    }
    
    this.loadBots();
  }

  /**
   * Fetch available bots from the server and populate the dropdown
   */
  private async loadBots(): Promise<void> {
    try {
      const serverUrl = import.meta.env.VITE_SERVER_URL || window.location.origin;
      console.log('Environment VITE_SERVER_URL:', import.meta.env.VITE_SERVER_URL);
      console.log('Using server URL:', serverUrl);
      const response = await fetch(`${serverUrl}/bots`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      
      if (this.botSelect) {
        // Clear existing options
        this.botSelect.innerHTML = '';
        
        // Add default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Wähle ein mystisches Wesen...';
        this.botSelect.appendChild(defaultOption);
        
        // Add bot options
        data.bots.forEach((bot: string) => {
          const option = document.createElement('option');
          option.value = bot;
          option.textContent = bot;
          this.botSelect!.appendChild(option);
        });
        
        // Add change listener to enable/disable connect button
        this.botSelect.addEventListener('change', () => {
          if (this.connectBtn) {
            this.connectBtn.disabled = !this.botSelect?.value;
          }
        });
      }
      
      this.log(`Loaded ${data.bots.length} bots`);
    } catch (error) {
      this.log(`Error loading bots: ${(error as Error).message}`);
      if (this.botSelect) {
        this.botSelect.innerHTML = '<option value="">Fehler beim Laden der mystischen Wesen</option>';
      }
    }
  }

  /**
   * Add a timestamped message to the debug log
   */
  private log(message: string): void {
    if (!this.debugLog) return;
    const entry = document.createElement('div');
    
    // Format timestamp in German style
    const now = new Date();
    const timestamp = now.toLocaleString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    
    // Translate and style messages
    let displayMessage = message;
    let messageClass = '';
    
    if (message.startsWith('User: ')) {
      displayMessage = `👤 Benutzer: ${message.substring(6)}`;
      messageClass = 'user-message';
    } else if (message.startsWith('Bot: ')) {
      displayMessage = `🤖 Mystisches Wesen: ${message.substring(5)}`;
      messageClass = 'bot-message';
    } else if (message.includes('Connected')) {
      displayMessage = `🔗 Portal geöffnet - Verbindung hergestellt`;
      messageClass = 'success-message';
    } else if (message.includes('Disconnected')) {
      displayMessage = `❌ Portal geschlossen - Verbindung getrennt`;
      messageClass = 'error-message';
    } else if (message.includes('Error')) {
      displayMessage = `⚠️ Fehler: ${message}`;
      messageClass = 'error-message';
    } else if (message.includes('Bot ready')) {
      displayMessage = `✨ Mystisches Wesen bereit für Kommunikation`;
      messageClass = 'success-message';
    } else if (message.includes('Loading bots')) {
      displayMessage = `📚 Lade mystische Wesen...`;
      messageClass = 'info-message';
    } else if (message.includes('Loaded')) {
      displayMessage = `📖 ${message.replace('Loaded', 'Geladen:')} mystische Wesen verfügbar`;
      messageClass = 'info-message';
    }
    
    entry.textContent = `[${timestamp}] ${displayMessage}`;
    entry.className = messageClass;
    
    this.debugLog.appendChild(entry);
    this.debugLog.scrollTop = this.debugLog.scrollHeight;
    console.log(message);
  }

  /**
   * Update the connection status display
   */
  private updateStatus(status: string): void {
    if (this.statusSpan) {
      // Translate status messages to German
      let germanStatus = status;
      switch (status) {
        case 'Connected':
          germanStatus = 'Verbunden';
          break;
        case 'Disconnected':
          germanStatus = 'Nicht verbunden';
          break;
        case 'Error':
          germanStatus = 'Fehler';
          break;
        case 'Connecting':
          germanStatus = 'Verbinde...';
          break;
      }
      this.statusSpan.textContent = germanStatus;
    }
    this.log(`Status: ${status}`);
  }

  /**
   * Check for available media tracks and set them up if present
   * This is called when the bot is ready or when the transport state changes to ready
   */
  setupMediaTracks() {
    if (!this.pcClient) return;
    const tracks = this.pcClient.tracks();
    if (tracks.bot?.audio) {
      this.setupAudioTrack(tracks.bot.audio);
    }
  }

  /**
   * Set up listeners for track events (start/stop)
   * This handles new tracks being added during the session
   */
  setupTrackListeners() {
    if (!this.pcClient) return;

    // Listen for new tracks starting
    this.pcClient.on(RTVIEvent.TrackStarted, (track: any, participant: any) => {
      // Only handle non-local (bot) tracks
      if (!participant?.local && track.kind === 'audio') {
        this.setupAudioTrack(track);
      }
    });

    // Listen for tracks stopping
    this.pcClient.on(RTVIEvent.TrackStopped, (track: any, participant: any) => {
      this.log(
        `Track stopped: ${track.kind} from ${participant?.name || 'unknown'}`
      );
    });
  }

  /**
   * Set up an audio track for playback
   * Handles both initial setup and track updates
   */
  private setupAudioTrack(track: MediaStreamTrack): void {
    this.log('Setting up audio track');
    
    try {
      // Stop any existing audio tracks to prevent conflicts
      if (
        this.botAudio.srcObject &&
        'getAudioTracks' in this.botAudio.srcObject
      ) {
        const oldTracks = this.botAudio.srcObject.getAudioTracks();
        oldTracks.forEach(oldTrack => {
          if (oldTrack.id !== track.id) {
            oldTrack.stop();
          }
        });
      }
      
      // Create new MediaStream with the track
      const newStream = new MediaStream([track]);
      this.botAudio.srcObject = newStream;
      
      // Add error handling for audio playback
      this.botAudio.onerror = (error) => {
        this.log(`Audio playback error: ${error}`);
      };
      
      // Add event listeners for better debugging
      this.botAudio.onloadstart = () => this.log('Audio loading started');
      this.botAudio.oncanplay = () => this.log('Audio can start playing');
      this.botAudio.onended = () => this.log('Audio playback ended');
      
      // Ensure audio is ready to play
      this.botAudio.load();
      
    } catch (error) {
      this.log(`Error setting up audio track: ${error}`);
    }
  }

  /**
   * Initialize and connect to the bot
   * This sets up the Pipecat client, initializes devices, and establishes the connection
   */
  public async connect(): Promise<void> {
    try {
      const startTime = Date.now();

      //const transport = new DailyTransport();
      const PipecatConfig: PipecatClientOptions = {
        transport: new WebSocketTransport(),
        enableMic: true,
        enableCam: false,
        callbacks: {
          onConnected: () => {
            this.updateStatus('Connected');
            if (this.connectBtn) this.connectBtn.disabled = true;
            if (this.disconnectBtn) this.disconnectBtn.disabled = false;
          },
          onDisconnected: () => {
            this.updateStatus('Disconnected');
            if (this.connectBtn) this.connectBtn.disabled = false;
            if (this.disconnectBtn) this.disconnectBtn.disabled = true;
            this.log('Client disconnected');
          },
          onBotReady: (data: any) => {
            this.log(`Bot ready: ${JSON.stringify(data)}`);
            this.setupMediaTracks();
          },
          onUserTranscript: (data: any) => {
            if (data.final) {
              this.log(`User: ${data.text}`);
            }
          },
          onBotTranscript: (data: any) => this.log(`Bot: ${data.text}`),
          onMessageError: (error: any) => console.error('Message error:', error),
          onError: (error: any) => {
            console.error('Error:', error);
            this.log(`Connection error: ${error.message || error}`);
            this.updateStatus('Error');
          },
        },
      };
      this.pcClient = new PipecatClient(PipecatConfig);
      // @ts-ignore
      window.pcClient = this.pcClient; // Expose for debugging
      this.setupTrackListeners();

      this.log('Initializing devices...');
      await this.pcClient.initDevices();

      this.log('Connecting to bot...');
      const serverUrl = import.meta.env.VITE_SERVER_URL || window.location.origin;
      console.log('Connecting to server:', serverUrl);
      
      const selectedBot = this.botSelect?.value;
      if (!selectedBot) {
        throw new Error('Bitte wähle zuerst ein mystisches Wesen aus');
      }
      
      this.log(`Connecting to bot: ${selectedBot}`);
      
      const endpoint = `${serverUrl}/connect?bot=${selectedBot}`;
      this.log(`Using endpoint: ${endpoint}`);
      
      await this.pcClient.startBotAndConnect({
        // The baseURL and endpoint of your bot server that the client will connect to
        endpoint: endpoint,
      });

      const timeTaken = Date.now() - startTime;
      this.log(`Connection complete, timeTaken: ${timeTaken}`);
    } catch (error) {
      this.log(`Error connecting: ${(error as Error).message}`);
      this.updateStatus('Error');
      // Clean up if there's an error
      if (this.pcClient) {
        try {
          await this.pcClient.disconnect();
        } catch (disconnectError) {
          this.log(`Error during disconnect: ${disconnectError}`);
        }
      }
    }
  }

  /**
   * Disconnect from the bot and clean up media resources
   */
  public async disconnect(): Promise<void> {
    if (this.pcClient) {
      try {
        this.log('Disconnecting from bot...');
        await this.pcClient.disconnect();
        this.pcClient = null;
        
        // Clean up audio resources
        if (
          this.botAudio.srcObject &&
          'getAudioTracks' in this.botAudio.srcObject
        ) {
          this.botAudio.srcObject
            .getAudioTracks()
            .forEach((track) => {
              track.stop();
              this.log('Audio track stopped');
            });
          this.botAudio.srcObject = null;
        }
        
        // Reset audio element
        this.botAudio.pause();
        this.botAudio.currentTime = 0;
        this.botAudio.src = '';
        
        this.log('Disconnection complete');
      } catch (error) {
        this.log(`Error disconnecting: ${(error as Error).message}`);
      }
    }
  }
}

declare global {
  interface Window {
    WebsocketClientApp: typeof WebsocketClientApp;
  }
}

window.addEventListener('DOMContentLoaded', () => {
  window.WebsocketClientApp = WebsocketClientApp;
  new WebsocketClientApp();
});
