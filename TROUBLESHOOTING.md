# Troubleshooting Guide

## Broken Voice Issues

### Symptoms
- Audio cuts out mid-sentence
- Garbled or distorted speech
- Audio delays or stuttering
- Complete audio loss

### Common Causes and Solutions

#### 1. Audio Buffer Issues
**Problem**: Small audio buffers can cause audio to break up during network latency spikes.

**Solution**: Increase audio buffer size
```bash
# Add to your .env file
AUDIO_BUFFER_SIZE=8192  # Double the default size
```

#### 2. Network Connectivity Issues
**Problem**: Unstable network connections can cause audio streams to break.

**Solution**: 
- Check your internet connection stability
- Use a wired connection instead of WiFi if possible
- Increase WebSocket ping interval:
```bash
WEBSOCKET_PING_INTERVAL=60  # Increase from 30 to 60 seconds
```

#### 3. Browser Audio Processing
**Problem**: Browser audio processing can interfere with the audio stream.

**Solution**: 
- Disable browser extensions that might interfere with audio
- Try a different browser (Chrome/Edge recommended)
- Clear browser cache and cookies

#### 4. System Audio Issues
**Problem**: System audio settings can cause conflicts.

**Solution**:
- Check that your default audio device is working
- Disable audio enhancements in system settings
- Ensure microphone permissions are granted

## Scrambled Log Output

### Symptoms
- Log messages appear out of order
- Incomplete log entries
- Mixed log messages from different connections

### Common Causes and Solutions

#### 1. Concurrent Logging Conflicts
**Problem**: Multiple threads writing to logs simultaneously.

**Solution**: The code now uses thread-safe logging with `enqueue=True`.

#### 2. Log Level Issues
**Problem**: Too much debug output can overwhelm the log.

**Solution**: Set appropriate log level:
```bash
LOG_LEVEL=INFO  # Use INFO instead of DEBUG for production
```

#### 3. Connection-Specific Logging
**Problem**: Logs from different connections getting mixed up.

**Solution**: Each connection now has its own logger instance.

## Performance Optimization

### Audio Quality Settings
```bash
# For better audio quality (higher bandwidth usage)
AUDIO_SAMPLE_RATE=24000
VAD_THRESHOLD=0.3

# For better stability (lower bandwidth usage)
AUDIO_SAMPLE_RATE=8000
VAD_THRESHOLD=0.7
```

### Memory and CPU Optimization
```bash
# Reduce buffer size for lower latency (may cause more audio breaks)
AUDIO_BUFFER_SIZE=2048

# Increase buffer size for stability (higher latency)
AUDIO_BUFFER_SIZE=8192
```

## Debugging Steps

### 1. Check Server Logs
Look for these patterns in the server logs:
- `Transport error:` - Indicates WebSocket issues
- `Audio playback error:` - Indicates client-side audio problems
- `Connection error:` - Indicates connection stability issues

### 2. Check Browser Console
Open browser developer tools and look for:
- WebSocket connection errors
- Audio context errors
- Media stream errors

### 3. Test Network Stability
```bash
# Test ping to your server
ping your-server-address

# Test WebSocket connection
# Use browser developer tools Network tab
```

### 4. Monitor System Resources
- Check CPU usage during voice calls
- Monitor memory usage
- Check network bandwidth usage

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `AUDIO_BUFFER_SIZE` | 4096 | Audio buffer size in samples |
| `AUDIO_SAMPLE_RATE` | 16000 | Audio sample rate in Hz |
| `VAD_THRESHOLD` | 0.5 | Voice activity detection sensitivity |
| `WEBSOCKET_PING_INTERVAL` | 30 | WebSocket ping interval in seconds |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Quick Fixes

### For Immediate Audio Issues:
1. Refresh the browser page
2. Disconnect and reconnect to the bot
3. Check microphone permissions
4. Try a different browser

### For Log Issues:
1. Restart the server
2. Check log level settings
3. Monitor server resources

### For Connection Issues:
1. Check internet connection
2. Restart the server
3. Clear browser cache
4. Try a different network

## Getting Help

If issues persist:
1. Check the server logs for specific error messages
2. Note the exact steps to reproduce the issue
3. Include your environment configuration
4. Test with different browsers/devices
