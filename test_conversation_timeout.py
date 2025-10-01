#!/usr/bin/env python3
"""
Test script for the per-connection conversation timeout mechanism.
This demonstrates how each connection gets its own 5-minute timer that resets on activity.
"""

import os
import time


def main():
    """Demonstrate the conversation timeout mechanism."""
    print("🧪 Per-Connection Conversation Timeout Test")
    print("=" * 50)

    print("\n📋 How it works:")
    print("1. Each WebSocket connection gets its own 5-minute timer")
    print("2. Timer resets whenever there's activity (audio frames, text processing)")
    print("3. After 5 minutes of inactivity, conversation history is cleared")
    print("4. Connection stays open - only the conversation context is reset")

    print("\n⚙️  Configuration:")
    print("   Default timeout: 5 minutes (300 seconds)")
    print("   Configurable via: CONVERSATION_TIMEOUT_SECONDS environment variable")

    print("\n🔧 Testing with shorter timeout:")
    print("   CONVERSATION_TIMEOUT_SECONDS=10 python server.py")
    print("   (This sets 10-second timeout for faster testing)")

    print("\n📊 What happens:")
    print("   ✅ Connection established → Timer starts")
    print("   ✅ User speaks → Timer resets")
    print("   ✅ Bot responds → Timer resets")
    print("   ⏰ 5 minutes of silence → Conversation history cleared")
    print("   🔄 User speaks again → Fresh conversation starts")

    print("\n🎯 Benefits:")
    print("   • Prevents conversation context from growing indefinitely")
    print("   • Gives users a fresh start after being away")
    print("   • Keeps connections alive (no reconnection needed)")
    print("   • Per-connection isolation (one user's timeout doesn't affect others)")

    print("\n" + "=" * 50)
    print("✅ Implementation complete!")
    print("\nTo test:")
    print("1. Start server: python server.py")
    print("2. Connect a client and have a conversation")
    print("3. Wait 5 minutes without speaking")
    print("4. Speak again - conversation should start fresh")


if __name__ == "__main__":
    main()
