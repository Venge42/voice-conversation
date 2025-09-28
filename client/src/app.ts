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
import { CrystalLightController } from './light_controller';

class WebsocketClientApp {
  private pcClient: PipecatClient | null = null;
  private connectBtn: HTMLButtonElement | null = null;
  private disconnectBtn: HTMLButtonElement | null = null;
  private statusSpan: HTMLElement | null = null;
  private debugLog: HTMLElement | null = null;
  private botSelect: HTMLSelectElement | null = null;
  private botAudio: HTMLAudioElement;
  private lightController: CrystalLightController;
  private lightWebSocket: WebSocket | null = null;
  private lastServerUrl: string = '';
  private lightAnimationInterval: NodeJS.Timeout | null = null;
  private currentDisplayedColor: any = { r: 0, g: 0, b: 0, a: 0 };
  private shellyAvailable: boolean = true;
  private shellyErrorCount: number = 0;
  private readonly MAX_SHELLY_ERRORS: number = 3;
  private shellyIP: string | null = null;
  private currentBotLightConfig: any | null = null;

  /**
   * Normalize server light_config (snake_case) to client animation structure
   */
  private normalizeLightConfig(raw: any): any {
    if (!raw) return null;
    const primary = raw.primary || raw.primary_color;
    const fadeTo = raw.fadeTo || raw.fade_to_color || raw.fade_to;
    const offColor = raw.offColor || raw.off_color;
    return {
      primary: primary || { r: 0, g: 0, b: 0, a: 1 },
      fadeTo: fadeTo || primary || { r: 0, g: 0, b: 0, a: 1 },
      offColor: offColor || { r: 0, g: 0, b: 0, a: 0 },
      colorShiftSpeed: raw.colorShiftSpeed ?? raw.color_shift_speed ?? 2.0,
      pulseSpeed: raw.pulseSpeed ?? raw.pulse_speed ?? 1.5,
      pulseIntensity: raw.pulseIntensity ?? raw.pulse_intensity ?? 0.2,
      breathingSpeed: raw.breathingSpeed ?? raw.breathing_speed ?? 0.8,
      breathingIntensity: raw.breathingIntensity ?? raw.breathing_intensity ?? 0.15,
    };
  }

  constructor() {
    console.log('WebsocketClientApp');
    this.botAudio = document.createElement('audio');
    this.botAudio.autoplay = true;
    //this.botAudio.playsInline = true;
    document.body.appendChild(this.botAudio);

    // Initialize light controller
    this.lightController = new CrystalLightController();
    this.lightController.setDebugMode(true);

    this.setupDOMElements();
    this.setupEventListeners();
    
    // Initialize color display with default black
    this.updateColorDisplay({ r: 0, g: 0, b: 0, a: 0 });
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
    
    // Set up light control event listeners
    this.setupLightControlEventListeners();
    
    this.loadBots();
  }

  /**
   * Set up light control event listeners
   */
  private setupLightControlEventListeners(): void {
    // Light control test buttons
    const testRedBtn = document.getElementById('test-red');
    const testGreenBtn = document.getElementById('test-green');
    const testBlueBtn = document.getElementById('test-blue');
    const testOffBtn = document.getElementById('test-off');

    if (testRedBtn) {
      testRedBtn.addEventListener('click', () => this.testLightColor({ r: 1, g: 0, b: 0, a: 1 }));
    }

    if (testGreenBtn) {
      testGreenBtn.addEventListener('click', () => this.testLightColor({ r: 0, g: 1, b: 0, a: 1 }));
    }

    if (testBlueBtn) {
      testBlueBtn.addEventListener('click', () => this.testLightColor({ r: 0, g: 0, b: 1, a: 1 }));
    }

    if (testOffBtn) {
      testOffBtn.addEventListener('click', () => this.testLightOff());
    }
  }

  /**
   * Fetch available bots from the server and populate the dropdown
   */
  private async loadBots(): Promise<void> {
    try {
      const serverUrl = import.meta.env.VITE_SERVER_URL || 'http://localhost:7860';
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
   * Test light with a specific color
   */
  private async testLightColor(color: { r: number; g: number; b: number; a: number }): Promise<void> {
    this.log(`🧪 Testing light color: RGB(${color.r}, ${color.g}, ${color.b})`);
    await this.lightController.testColor(color);
    this.updateColorDisplay(color);
  }

  /**
   * Test turning off lights
   */
  private async testLightOff(): Promise<void> {
    this.log('🔇 Testing light off');
    await this.lightController.turnOff();
    this.updateColorDisplay({ r: 0, g: 0, b: 0, a: 0 });
  }

  /**
   * Update color display with current color values
   */
  private updateColorDisplay(color: { r: number; g: number; b: number; a: number }): void {
    // Store the current displayed color for fade transitions
    this.currentDisplayedColor = { ...color };
    
    // Update color preview circle
    const colorPreview = document.getElementById('color-preview');
    if (colorPreview) {
      const r = Math.round(color.r * 255);
      const g = Math.round(color.g * 255);
      const b = Math.round(color.b * 255);
      const a = 1.0; //Math.round(color.a * 255);
      
      // Apply color to preview circle
      colorPreview.style.background = `rgba(${r}, ${g}, ${b}, ${a})`;
      
      // Add glow effect based on intensity
      const intensity = Math.max(r, g, b) / 255;
      colorPreview.style.boxShadow = `0 0 ${15 + intensity * 10}px rgba(${r}, ${g}, ${b}, ${a * 0.8})`;
    }

    // Update RGB values
    const redValue = document.getElementById('red-value');
    const greenValue = document.getElementById('green-value');
    const blueValue = document.getElementById('blue-value');
    const alphaValue = document.getElementById('alpha-value');
    
    if (redValue) redValue.textContent = Math.round(color.r * 255).toString();
    if (greenValue) greenValue.textContent = Math.round(color.g * 255).toString();
    if (blueValue) blueValue.textContent = Math.round(color.b * 255).toString();
    if (alphaValue) alphaValue.textContent = Math.round(color.a * 255).toString();

    // Update HEX value
    const hexValue = document.getElementById('hex-value');
    if (hexValue) {
      const r = Math.round(color.r * 255);
      const g = Math.round(color.g * 255);
      const b = Math.round(color.b * 255);
      const hex = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
      hexValue.textContent = hex;
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
      // Reset client state for clean connection
      this.resetClientState();
      
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
            
            // Set up light control WebSocket after bot is ready
            this.setupLightControlWebSocket().catch(error => {
              this.log(`❌ Error setting up light control: ${error}`);
            });
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
          const serverUrl = import.meta.env.VITE_SERVER_URL || 'http://localhost:7860';
    this.lastServerUrl = serverUrl; // Store for light WebSocket
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
   * Set up light control WebSocket connection
   */
  private async setupLightControlWebSocket(): Promise<void> {
    try {
      // Use the same server URL that we used for the voice connection
      const serverUrl = this.lastServerUrl || import.meta.env.VITE_SERVER_URL || 'http://localhost:7860';
      const selectedBot = this.botSelect?.value;
      if (!selectedBot) {
        this.log('❌ No bot selected for light control WebSocket');
        return;
      }

      // Fetch bot config to obtain real Shelly IP and colors
      try {
        const configResp = await fetch(`${serverUrl}/bot-config?bot=${encodeURIComponent(selectedBot)}`);
        if (configResp.ok) {
          const cfg = await configResp.json();
          // Log full received config
          console.log('🔧 Full bot config received:', cfg);
          this.currentBotLightConfig = this.normalizeLightConfig(cfg?.light_config || null);
          this.shellyIP = (cfg?.light_config?.shelly_ip) || null;
          // Inform light controller so it can send no-cors GETs to LAN Shelly
          this.lightController.setShellyIP(this.shellyIP);
          if (this.shellyIP) {
            this.log(`🔍 Shelly IP for ${selectedBot}: ${this.shellyIP}`);
          } else {
            this.log('⚠️ No shelly_ip found in bot config; Shelly will be disabled');
          }
        } else {
          this.log(`⚠️ Failed to fetch bot config: ${configResp.status}`);
        }
      } catch (e) {
        this.log(`⚠️ Error fetching bot config: ${e}`);
      }

      // Check Shelly availability using configured IP
      this.shellyAvailable = await this.checkShellyAvailability();
      if (this.shellyAvailable) {
        this.log('✅ Shelly device detected and available');
      } else {
        this.log('⚠️ Shelly device not available, lights will only animate in UI');
      }

      const wsUrl = serverUrl.replace('http://', 'ws://').replace('https://', 'wss://');
      const lightWsUrl = `${wsUrl}/light-ws?bot=${selectedBot}`;
      
      this.log(`🔌 Setting up light control WebSocket: ${lightWsUrl}`);
      
      this.lightWebSocket = new WebSocket(lightWsUrl);
      
      this.lightWebSocket.onopen = () => {
        this.log('🔌 Light control WebSocket connected');
      };
      
      this.lightWebSocket.onmessage = (event) => {
        this.log(`🔌 Light control message received: ${event.data}`);
        console.log('🔌 Raw light WebSocket message:', event.data);
        try {
          const data = JSON.parse(event.data);
          console.log('🔌 Parsed light control data:', data);
          this.handleLightWebSocketMessage(data);
        } catch (error) {
          this.log(`❌ Error parsing light control message: ${error}`);
          console.error('❌ Light message parsing error:', error);
        }
      };
      
      this.lightWebSocket.onerror = (error) => {
        this.log(`❌ Light control WebSocket error: ${error}`);
      };
      
      this.lightWebSocket.onclose = () => {
        this.log('🔌 Light control WebSocket closed');
      };
      
    } catch (error) {
      this.log(`❌ Error setting up light control WebSocket: ${error}`);
    }
  }

  /**
   * Handle light control WebSocket messages
   */
  private handleLightWebSocketMessage(message: any): void {
    console.log('🎨 Processing light WebSocket message:', message);
    
    if (message.type === 'speaking_start') {
      this.log(`🎤 Bot started speaking: ${message.bot_config}`);
      console.log('🎤 Speaking started, beginning light animation');
      
      // Start local light animation
      this.startLightAnimation(message.bot_config);
      
    } else if (message.type === 'speaking_stop') {
      this.log(`🔇 Bot stopped speaking: ${message.bot_config}`);
      console.log('🔇 Speaking stopped, ending light animation');
      
      // Stop local light animation and turn off lights
      this.stopLightAnimation(message.bot_config);
      
    } else if (message.type === 'light_command') {
      this.log(`🎨 Light command received for ${message.bot_config}`);
      console.log('🎨 Light command details:', message);
      
      this.lightController.handleLightCommand(message);
      
      // Update color display with the received color
      // Use full alpha for UI visibility (white channel may be 0)
      const color = {
        r: message.command.red / 255,
        g: message.command.green / 255,
        b: message.command.blue / 255,
        a: 1.0
      };
      console.log('🎨 Extracted color:', color);
      this.updateColorDisplay(color);
    } else {
      console.log('📡 Non-light command message:', message);
    }
  }

  /**
   * Start local light animation for a bot
   */
  private startLightAnimation(botConfig: string): void {
    console.log(`🎨 Starting light animation for ${botConfig}`);
    
    // Use server-provided light config
    const botColors = this.currentBotLightConfig;
    if (!botColors) {
      console.warn(`⚠️ No light_config loaded for ${botConfig}`);
      return;
    }
    
    // Start the animation loop
    this.runLightAnimation(botConfig, botColors);
  }

  /**
   * Stop local light animation for a bot
   */
  private stopLightAnimation(botConfig: string): void {
    console.log(`🎨 Stopping light animation for ${botConfig}`);
    
    // Stop any running animation
    if (this.lightAnimationInterval) {
      clearInterval(this.lightAnimationInterval);
      this.lightAnimationInterval = null;
      console.log(`🎨 Animation loop stopped for ${botConfig}`);
    }
    
    // Fade to off color smoothly
    console.log(`🎨 Fading to off color for ${botConfig}...`);
    this.fadeToOffColor(botConfig);
  }

  /**
   * Run the light animation loop
   */
  private runLightAnimation(botConfig: string, colors: any): void {
    let startTime = Date.now();
    
    // Run at 10 FPS to limit Shelly update rate
    this.lightAnimationInterval = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000; // seconds
      
      // Calculate animated color using the same algorithm as the server
      const animatedColor = this.calculateAnimatedColor(colors, elapsed);
      
      // Apply the color to lights
      this.applyLightColor(botConfig, animatedColor);
      
      // Update color display
      this.updateColorDisplay(animatedColor);
      
    }, 1000 / 30); // 10 FPS
  }

  /**
   * Calculate animated color with enhanced variation
   */
  private calculateAnimatedColor(colors: any, elapsed: number): any {
    if (!colors || !colors.primary || !colors.fadeTo) {
      // Guard against missing config; fall back to no-op color
      return this.clampColor(this.currentDisplayedColor || { r: 0, g: 0, b: 0, a: 1 });
    }
    // Enhanced color shifting with multiple phases
    const colorShiftFactor = this.calculateColorShiftFactor(elapsed, colors.colorShiftSpeed);
    const baseColor = this.lerpColor(colors.primary, colors.fadeTo, colorShiftFactor);
    
    // Add complementary color variation for more interest
    const complementaryVariation = this.calculateComplementaryVariation(elapsed, colors);
    
    // Enhanced pulsing effect
    const pulseFactor = this.calculatePulseFactor(elapsed, colors.pulseSpeed, colors.pulseIntensity);
    
    // Enhanced breathing effect
    const breathingFactor = this.calculateBreathingFactor(elapsed, colors.breathingSpeed, colors.breathingIntensity);
    
    // Add subtle hue shifting for more dynamic colors
    const hueShift = this.calculateHueShift(elapsed, colors);
    
    // Combine all effects
    const enhancedColor = {
      r: (baseColor.r + complementaryVariation.r * 0.3) * pulseFactor * breathingFactor + hueShift.r * 0.2,
      g: (baseColor.g + complementaryVariation.g * 0.3) * pulseFactor * breathingFactor + hueShift.g * 0.2,
      b: (baseColor.b + complementaryVariation.b * 0.3) * pulseFactor * breathingFactor + hueShift.b * 0.2,
      a: baseColor.a * breathingFactor
    };
    
    return this.clampColor(enhancedColor);
  }

  /**
   * Helper methods for color calculations
   */
  private lerpColor(a: any, b: any, t: number): any {
    if (!a || !b) {
      return this.clampColor(this.currentDisplayedColor || { r: 0, g: 0, b: 0, a: 1 });
    }
    return {
      r: a.r + (b.r - a.r) * t,
      g: a.g + (b.g - a.g) * t,
      b: a.b + (b.b - a.b) * t,
      a: a.a + (b.a - a.a) * t
    };
  }

  private clampColor(color: any): any {
    return {
      r: Math.max(0, Math.min(1, color.r)),
      g: Math.max(0, Math.min(1, color.g)),
      b: Math.max(0, Math.min(1, color.b)),
      a: Math.max(0, Math.min(1, color.a))
    };
  }

  private calculateColorShiftFactor(elapsed: number, speed: number): number {
    const phase = elapsed * speed;
    
    // Use multiple sine waves with different frequencies for more organic movement
    const shift1 = Math.sin(phase) * 0.4;
    const shift2 = Math.sin(phase * 1.3) * 0.3;
    const shift3 = Math.sin(phase * 0.7) * 0.3;
    const shift4 = Math.sin(phase * 2.1) * 0.2; // Additional high-frequency variation
    
    const combinedShift = shift1 + shift2 + shift3 + shift4;
    return (combinedShift + 1) / 2; // Normalize to 0-1
  }

  private calculatePulseFactor(elapsed: number, speed: number, intensity: number): number {
    // Add some randomness and multiple frequencies to pulsing
    const basePulse = Math.sin(elapsed * speed) * intensity;
    const secondaryPulse = Math.sin(elapsed * speed * 1.7) * intensity * 0.5;
    const microPulse = Math.sin(elapsed * speed * 3.2) * intensity * 0.3;
    
    return 1 + basePulse + secondaryPulse + microPulse;
  }

  private calculateBreathingFactor(elapsed: number, speed: number, intensity: number): number {
    // Add some randomness and multiple frequencies to breathing
    const baseBreathing = Math.sin(elapsed * speed) * intensity;
    const secondaryBreathing = Math.sin(elapsed * speed * 0.6) * intensity * 0.4;
    const microBreathing = Math.sin(elapsed * speed * 2.3) * intensity * 0.2;
    
    return 1 + baseBreathing + secondaryBreathing + microBreathing;
  }

  /**
   * Calculate complementary color variation for more interest
   */
  private calculateComplementaryVariation(elapsed: number, colors: any): any {
    // Create complementary colors based on the primary color
    const complementary = {
      r: 1 - colors.primary.r,
      g: 1 - colors.primary.g,
      b: 1 - colors.primary.b,
      a: 1
    };
    
    // Use different sine wave frequencies for each channel
    const rVariation = Math.sin(elapsed * colors.colorShiftSpeed * 0.7) * 0.15;
    const gVariation = Math.sin(elapsed * colors.colorShiftSpeed * 1.1) * 0.15;
    const bVariation = Math.sin(elapsed * colors.colorShiftSpeed * 0.9) * 0.15;
    
    return {
      r: complementary.r * rVariation,
      g: complementary.g * gVariation,
      b: complementary.b * bVariation,
      a: 0
    };
  }

  /**
   * Calculate subtle hue shifting for dynamic colors
   */
  private calculateHueShift(elapsed: number, colors: any): any {
    // Add subtle color temperature shifts
    const warmShift = Math.sin(elapsed * colors.colorShiftSpeed * 0.5) * 0.1;
    const coolShift = Math.sin(elapsed * colors.colorShiftSpeed * 0.8) * 0.1;
    
    return {
      r: warmShift,      // Red channel gets warm variations
      g: (warmShift + coolShift) * 0.5,  // Green gets mixed
      b: coolShift,      // Blue channel gets cool variations
      a: 0
    };
  }

  /**
   * Get bot color configuration
   */
  // Removed getBotColors. Colors now come from server-provided light_config.

  /**
   * Check if Shelly device is available
   */
  private async checkShellyAvailability(): Promise<boolean> {
    try {
      const shellyIP = this.shellyIP;
      if (!shellyIP) {
        return false;
      }
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000); // 2 second timeout
      
      const response = await fetch(`http://${shellyIP}/light/0`, {
        method: 'GET',
        mode: 'no-cors',
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      // Opaque response from no-cors still indicates device reachable
      return response.ok || (response as any).type === 'opaque';
    } catch (error) {
      console.log(`🔍 Shelly availability check failed: ${error}`);
      return false;
    }
  }

  /**
   * Apply light color to Shelly device
   */
  private async applyLightColor(botConfig: string, color: any): Promise<void> {
    // Skip if Shelly is disabled
    if (!this.shellyAvailable) {
      console.log('🎨 Shelly disabled, skipping light color update');
      return;
    }

    try {
      // Convert to Shelly format (0-255)
      const red = Math.round(color.r * 255);
      const green = Math.round(color.g * 255);
      const blue = Math.round(color.b * 255);
      const white = Math.round(color.a * 255);
      
      // Use Shelly IP from loaded config
      const shellyIP = this.shellyIP;
      if (!shellyIP) {
        this.handleShellyError();
        return;
      }
      
      // Use light controller to send GET with no-cors to LAN device (avoids CORS)
      await this.lightController.sendToShelly({
        turn: 'on',
        mode: 'color',
        red,
        green,
        blue,
        white,
      });
      // We can't inspect response in no-cors; assume success and reset error count
      this.shellyErrorCount = 0;
      
    } catch (error) {
      console.error('❌ Error setting light color:', error);
      this.handleShellyError();
    }
  }

  /**
   * Fade smoothly from current color to off color
   */
  private fadeToOffColor(botConfig: string): void {
    console.log(`🎨 Applying single off update for ${botConfig}`);
    
    // Get bot's configured off color from server config
    const botColors = this.currentBotLightConfig;
    if (!botColors) {
      console.warn(`⚠️ No color config found for ${botConfig}, using default off`);
      this.turnOffLights(botConfig);
      return;
    }
    
    const offColor = botColors.offColor;
    // Single update only; no step-wise fade on device to reduce traffic
    this.applyLightColor(botConfig, offColor);
    this.updateColorDisplay(offColor);
  }

  /**
   * Handle Shelly connection errors and disable if too many occur
   */
  private handleShellyError(): void {
    this.shellyErrorCount++;
    console.warn(`⚠️ Shelly error count: ${this.shellyErrorCount}/${this.MAX_SHELLY_ERRORS}`);
    
    if (this.shellyErrorCount >= this.MAX_SHELLY_ERRORS) {
      this.shellyAvailable = false;
      this.shellyErrorCount = 0;
      this.log('🚫 Shelly disabled due to repeated connection errors');
      this.log('💡 Lights will still animate in the UI but won\'t control physical devices');
    }
  }

  /**
   * Turn off lights for a bot
   */
  private async turnOffLights(botConfig: string): Promise<void> {
    try {
      // Get bot's configured off color from server config
      const botColors = this.currentBotLightConfig;
      if (!botColors) {
        console.warn(`⚠️ No color config found for ${botConfig}, using default off`);
        // Fallback to default off
        await this.applyLightColor(botConfig, { r: 0, g: 0, b: 0, a: 0 });
        this.updateColorDisplay({ r: 0, g: 0, b: 0, a: 0 });
        return;
      }
      
      // Use bot's configured off color
      const offColor = botColors.offColor;
      console.log(`🎨 Using ${botConfig}'s off color:`, offColor);
      
      // Apply the off color (will be skipped if Shelly is disabled)
      await this.applyLightColor(botConfig, offColor);
      
      // Update color display to show off state
      this.updateColorDisplay(offColor);
      
      console.log(`🎨 Lights set to off color for ${botConfig}`);
      
    } catch (error) {
      console.error('❌ Error turning off lights:', error);
    }
  }

  /**
   * Reset client state for clean connection
   */
  private resetClientState(): void {
    this.log('🔄 Resetting client state for clean connection...');
    
    // Clear any existing light animation
    if (this.lightAnimationInterval) {
      clearInterval(this.lightAnimationInterval);
      this.lightAnimationInterval = null;
      this.log('🎨 Light animation interval cleared');
    }
    
    // Reset color display
    this.currentDisplayedColor = { r: 0, g: 0, b: 0, a: 0 };
    this.updateColorDisplay({ r: 0, g: 0, b: 0, a: 0 });
    
    // Reset status
    this.updateStatus('Ready');
    
    this.log('✅ Client state reset complete');
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
        
        // Close light control WebSocket
        if (this.lightWebSocket) {
          try {
            this.lightWebSocket.close();
            this.lightWebSocket = null;
            this.log('🔌 Light control WebSocket closed');
          } catch (error) {
            this.log(`❌ Error closing light control WebSocket: ${error}`);
          }
        }
        
        // Clean up light animation state
        if (this.lightAnimationInterval) {
          clearInterval(this.lightAnimationInterval);
          this.lightAnimationInterval = null;
          this.log('🎨 Light animation interval cleared');
        }
        
        // Reset color display and state
        this.currentDisplayedColor = { r: 0, g: 0, b: 0, a: 0 };
        this.updateColorDisplay({ r: 0, g: 0, b: 0, a: 0 });
        this.log('🎨 Color display reset to off state');
        
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
