/**
 * Crystal Light Controller for TypeScript
 * Handles light commands and communicates with Shelly devices
 */

export class CrystalLightController {
    private isConnected: boolean = false;
    private currentColor: { r: number; g: number; b: number; a: number } = { r: 0, g: 0, b: 0, a: 0 };
    private shellyIP: string | null = null;
    private debugMode: boolean = false;
    private lastSendAtMs: number = 0;
    private readonly minSendIntervalMs: number = 100; // 10 fps
    private pendingCommand: any | null = null;
    private pendingTimer: number | null = null;

    constructor() {
        console.log('🎨 CrystalLightController initialized');
    }
    /**
     * Set Shelly IP address to target
     */
    setShellyIP(ip: string | null): void {
        this.shellyIP = ip;
        if (this.debugMode) {
            console.log('🔧 Shelly IP set to:', this.shellyIP);
        }
    }


    /**
     * Handle light commands received from the server
     * @param command - Light command from server
     */
    async handleLightCommand(command: any): Promise<void> {
        console.log('🎨 CrystalLightController.handleLightCommand called with:', command);
        
        if (command.type !== 'light_command') {
            console.log('❌ Not a light command, ignoring');
            return;
        }

        this.shellyIP = command.shelly_ip;
        this.currentColor = {
            r: command.command.red / 255,
            g: command.command.green / 255,
            b: command.command.blue / 255,
            a: command.command.white / 255
        };

        console.log('🎨 Light command processed:');
        console.log('  - Shelly IP:', this.shellyIP);
        console.log('  - Current color:', this.currentColor);

        // Send command to Shelly device
        await this.sendToShelly(command.command);
    }

    /**
     * Get current color for display purposes
     * @returns Current color object
     */
    getCurrentColor(): { r: number; g: number; b: number; a: number } {
        return this.currentColor;
    }

    /**
     * Send light command to Shelly device
     * @param command - Shelly API command
     */
    async sendToShelly(command: any): Promise<void> {
        if (!this.shellyIP) {
            console.warn('⚠️ No Shelly IP configured');
            return;
        }
        // Coalesce and throttle to max 10 fps
        const now = Date.now();
        const sendImmediately = now - this.lastSendAtMs >= this.minSendIntervalMs;

        if (!sendImmediately) {
            // Store latest command and schedule a send if not already scheduled
            this.pendingCommand = command;
            if (this.pendingTimer === null) {
                const delay = this.minSendIntervalMs - (now - this.lastSendAtMs);
                this.pendingTimer = window.setTimeout(async () => {
                    this.pendingTimer = null;
                    const cmd = this.pendingCommand;
                    this.pendingCommand = null;
                    if (cmd) {
                        await this._sendShellyNow(cmd);
                    }
                }, Math.max(0, delay));
            }
            return;
        }

        // Send now and record timestamp
        this.lastSendAtMs = now;
        await this._sendShellyNow(command);
    }

    private async _sendShellyNow(command: any): Promise<void> {
        try {
            const url = `http://${this.shellyIP}/light/0`;
            const params = new URLSearchParams(command);

            if (this.debugMode) {
                console.log('🔌 Sending to Shelly:', url, 'Params:', command);
            }

            await fetch(`${url}?${params}`, {
                method: 'GET',
                mode: 'no-cors'
            });

            if (this.debugMode) {
                console.log('✅ Shelly command sent (no-cors)');
            }
        } catch (error) {
            console.error('❌ Error sending to Shelly:', error);
        } finally {
            // Update last send time after attempt to maintain pacing
            this.lastSendAtMs = Date.now();
        }
    }

    /**
     * Set debug mode
     * @param enabled - Enable/disable debug logging
     */
    setDebugMode(enabled: boolean): void {
        this.debugMode = enabled;
        console.log(`🔍 Light controller debug mode: ${enabled ? 'ON' : 'OFF'}`);
    }

    /**
     * Get current status
     * @returns Current status
     */
    getStatus(): any {
        return {
            isConnected: this.isConnected,
            currentColor: this.currentColor,
            shellyIP: this.shellyIP,
            debugMode: this.debugMode
        };
    }

    /**
     * Test light with a specific color
     * @param color - RGB color object
     */
    async testColor(color: { r: number; g: number; b: number; a: number }): Promise<void> {
        if (this.debugMode) {
            console.log('🧪 Testing light color:', color);
        }

        // Update current color
        this.currentColor = color;

        // Create Shelly command
        const command = {
            red: Math.round(color.r * 255),
            green: Math.round(color.g * 255),
            blue: Math.round(color.b * 255),
            white: Math.round(color.a * 255)
        };

        // Send to Shelly if IP is configured
        if (this.shellyIP) {
            await this.sendToShelly(command);
        }
    }

    /**
     * Turn off lights
     */
    async turnOff(): Promise<void> {
        if (this.debugMode) {
            console.log('🔇 Turning off lights');
        }

        // Update current color to black
        this.currentColor = { r: 0, g: 0, b: 0, a: 0 };

        // Create off command
        const command = {
            red: 0,
            green: 0,
            blue: 0,
            white: 0
        };

        // Send to Shelly if IP is configured
        if (this.shellyIP) {
            await this.sendToShelly(command);
        }
    }
}
