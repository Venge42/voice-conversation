# Crystal Light Control System

A sophisticated speaking light control system for crystal bots that creates dynamic, animated lighting effects when the bots are speaking.

## Overview

The system automatically detects when a bot starts and stops speaking through the Pipecat pipeline and controls Shelly smart lights to create immersive visual effects. Each bot has its own unique color scheme and animation parameters.

## Features

### 🎨 Sophisticated Color Animation
- **Primary Colors**: Each bot has a distinctive primary color
- **Color Shifting**: Subtle hue variations using multiple sine waves
- **Pulsing Effects**: Dynamic brightness changes
- **Breathing Effects**: Alpha/intensity variations for organic feel
- **Smooth Transitions**: 30 FPS animation for fluid motion

### 🤖 Bot-Specific Configurations
- **Puck**: Purple/magenta with high energy
- **Charon**: Dark purple with mysterious pulsing
- **Kore**: Green with calm, earthy breathing
- **Zephyr**: Blue with airy, fast variations

### 🔧 Technical Features
- **Frame-Based Detection**: Monitors TTS frames for accurate speaking detection
- **Timeout Handling**: Automatically stops if no audio frames received
- **Error Recovery**: Graceful handling of network issues
- **Status Monitoring**: REST API endpoints for monitoring
- **Resource Management**: Proper cleanup of async resources

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Pipecat       │    │  Speaking Light  │    │ Crystal Light   │    │   WebSocket     │
│   Pipeline      │───▶│    Observer      │───▶│   Controller    │───▶│   Message       │
│                 │    │                  │    │                 │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └─────────────────┘
                                                                               │
                                                                               ▼
                                                                     ┌─────────────────┐
                                                                     │   Client-Side   │
                                                                     │ Light Controller│
                                                                     └─────────────────┘
                                                                               │
                                                                               ▼
                                                                     ┌─────────────────┐
                                                                     │   Shelly API    │
                                                                     │   (Local LAN)   │
                                                                     └─────────────────┘
```

**Note**: Light control is now client-side to handle local network access to Shelly devices.

## Configuration

Each bot's light configuration is stored in `lore/bots/{bot_name}/config.json`:

```json
{
  "voice_id": "Puck",
  "description": "Kristall Wesen - ein mystisches, kristallines Wesen",
  "personality": "emotional, verwirrt, wissenschaftlich, sarkastisch",
  "light_config": {
    "primary_color": {"r": 0.8, "g": 0.2, "b": 1.0, "a": 1.0},
    "fade_to_color": {"r": 1.0, "g": 0.4, "b": 0.6, "a": 1.0},
    "off_color": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.0},
    "variation_intensity": 0.3,
    "color_shift_speed": 2.0,
    "pulse_intensity": 0.2,
    "pulse_speed": 1.5,
    "breathing_effect": true,
    "breathing_speed": 0.8,
    "breathing_intensity": 0.15,
    "shelly_ip": "192.168.2.77"
  }
}
```

### Configuration Parameters

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| `primary_color` | Main color when speaking | RGBA 0.0-1.0 | Bot-specific |
| `fade_to_color` | Color to fade towards for variation | RGBA 0.0-1.0 | Auto-generated |
| `off_color` | Color when not speaking | RGBA 0.0-1.0 | (0,0,0,0) |
| `variation_intensity` | How much color variation | 0.0-1.0 | 0.3 |
| `color_shift_speed` | Speed of color shifting | 0.1-5.0 | 2.0 |
| `pulse_intensity` | Intensity of pulsing | 0.0-1.0 | 0.2 |
| `pulse_speed` | Speed of pulsing | 0.1-5.0 | 1.5 |
| `breathing_effect` | Enable breathing effect | true/false | true |
| `breathing_speed` | Speed of breathing | 0.1-3.0 | 0.8 |
| `breathing_intensity` | Intensity of breathing | 0.0-0.5 | 0.15 |
| `shelly_ip` | IP address of Shelly device | IP string | "192.168.2.77" |

## API Endpoints

### Light Status Monitoring

#### Get All Light Status
```http
GET /light-status
```

Response:
```json
{
  "active_connections": 2,
  "connections": {
    "192.168.1.100:12345": {
      "bot_config": "Puck",
      "connection_id": "192.168.1.100:12345",
      "is_speaking": true,
      "current_color": {
        "r": 0.823,
        "g": 0.156,
        "b": 0.987,
        "a": 1.0
      },
      "config": { ... }
    }
  }
}
```

#### Get Specific Connection Status
```http
GET /light-status/{connection_id}
```

## Usage

### Starting the System

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Shelly Device**:
   - Ensure your Shelly device is accessible from the client machine
   - The system uses Shelly's HTTP API for light control
   - **Important**: Shelly devices must be on the same local network as the client

3. **Start the Server**:
   ```bash
   python server.py
   ```

4. **Start the Client**:
   ```bash
   cd client
   npm run dev
   ```

5. **Connect a Bot**:
   - Open the client in your browser
   - Select a bot from the dropdown
   - Click "Portal öffnen" to connect
   - The server will automatically send light commands to the client

### Client-Side Light Control

The client includes a light control panel for testing:

- **Test Buttons**: Test red, green, blue, and off states
- **Real-time Status**: Shows current light state and bot activity
- **Automatic Control**: Lights automatically respond to bot speaking

### Network Requirements

- **Server**: Must be accessible from the client (localhost or public IP)
- **Client**: Must be on the same local network as Shelly devices
- **Shelly Devices**: Must be accessible via HTTP on the configured IP

### Testing

Run the test script to verify the system:
```bash
python test_light_controller.py
```

## Algorithm Details

### Color Animation Algorithm

The system uses a sophisticated multi-layered animation approach with proper color interpolation:

1. **Color Interpolation**: Linear interpolation between primary and fade_to colors using multiple sine waves
2. **Pulsing**: Brightness modulation for dynamic intensity
3. **Breathing**: Alpha channel modulation for organic feel

```python
# Improved algorithm with proper color interpolation
color_shift_factor = calculate_shift_factor(elapsed_time)  # 0.0 to 1.0
base_color = primary_color.lerp(fade_to_color, color_shift_factor)
final_color = base_color * pulse_factor * breathing_factor
final_color = final_color.clamp()  # Ensure valid range
```

This approach ensures that pure colors (like red 1,0,0) can properly fade to other colors (like pink 1,0.4,0.6) instead of staying red.

### Speaking Detection

The system monitors Pipecat frames to detect speaking:

- **TTSStartedFrame**: Immediately starts light effects
- **TTSAudioRawFrame**: Maintains speaking state, resets timeout
- **TTSStoppedFrame**: Immediately stops light effects
- **Timeout**: Stops if no audio frames for 500ms

## Troubleshooting

### Common Issues

1. **Lights Not Responding**:
   - Check Shelly device IP address
   - Verify network connectivity
   - Check Shelly device status

2. **Animation Too Fast/Slow**:
   - Adjust `color_shift_speed`, `pulse_speed`, `breathing_speed`
   - Lower values = slower animation

3. **Colors Too Bright/Dim**:
   - Adjust `pulse_intensity`, `breathing_intensity`
   - Lower values = more subtle effects

4. **Speaking Detection Issues**:
   - Check Pipecat pipeline configuration
   - Verify TTS service is working
   - Monitor logs for frame processing

### Debug Mode

Enable debug logging by setting the log level:
```python
logger.add(sys.stderr, level="DEBUG")
```

## Performance Considerations

- **Animation Rate**: 30 FPS for smooth animation
- **Network Calls**: HTTP requests to Shelly with 2-second timeout
- **Memory Usage**: Minimal, controllers are cleaned up on disconnect
- **CPU Usage**: Low, mostly mathematical calculations

## Future Enhancements

- **Multiple Light Support**: Control multiple Shelly devices
- **Scene Presets**: Predefined light scenes for different moods
- **Audio Reactive**: Sync with actual audio amplitude
- **Web Interface**: Real-time light control dashboard
- **Color Themes**: Seasonal or mood-based color schemes

## Contributing

When adding new features:

1. Update bot configurations in `lore/bots/`
2. Add tests to `test_light_controller.py`
3. Update this README
4. Ensure proper error handling and cleanup
5. Add logging for debugging

## License

SPDX-License-Identifier: BSD 2-Clause License
