#!/usr/bin/env python3
#
# Test script for the crystal light controller system
#
import asyncio
import json

from crystal_light_controller import Color, CrystalLightController
from speaking_light_observer import SpeakingLightObserver


async def test_light_controller():
    """Test the light controller with different bot configurations"""

    print("🧪 Testing Crystal Light Controller System")
    print("=" * 50)

    # Test different bot configurations
    bot_configs = ["Puck", "Charon", "Kore", "Zephyr"]

    for bot_config in bot_configs:
        print(f"\n🎭 Testing bot: {bot_config}")
        print("-" * 30)

        # Create light controller
        controller = CrystalLightController(bot_config, f"test_{bot_config}")
        observer = SpeakingLightObserver(controller)

        try:
            # Show configuration
            status = controller.get_status()
            config = status["config"]
            print(
                f"Primary Color: RGB({config['primary_color']['r']:.2f}, {config['primary_color']['g']:.2f}, {config['primary_color']['b']:.2f})"
            )
            print(
                f"Fade To Color: RGB({config['fade_to_color']['r']:.2f}, {config['fade_to_color']['g']:.2f}, {config['fade_to_color']['b']:.2f})"
            )
            print(f"Variation Intensity: {config['variation_intensity']}")
            print(f"Color Shift Speed: {config['color_shift_speed']}")
            print(f"Pulse Intensity: {config['pulse_intensity']}")
            print(f"Breathing Effect: {config['breathing_effect']}")

            # Test speaking start
            print("🔊 Starting speaking...")
            await controller.start_speaking()
            await asyncio.sleep(3)  # Let it animate for 3 seconds

            # Test speaking stop
            print("🔇 Stopping speaking...")
            await controller.stop_speaking()
            await asyncio.sleep(1)

        except Exception as e:
            print(f"❌ Error testing {bot_config}: {e}")

        finally:
            # Cleanup
            await observer.cleanup()
            print(f"✅ Cleaned up {bot_config}")

    print("\n🎉 Light controller test completed!")


async def test_color_calculations():
    """Test color calculation algorithms"""

    print("\n🎨 Testing Color Calculations")
    print("=" * 30)

    # Create a test controller
    controller = CrystalLightController("Puck", "color_test")

    # Test color variations over time
    print("Testing color variations over 5 seconds...")
    await controller.start_speaking()

    for i in range(50):  # 50 frames at ~10 FPS
        elapsed_time = i * 0.1
        color = controller._calculate_animated_color(elapsed_time)
        print(
            f"Time {elapsed_time:.1f}s: RGB({color.r:.3f}, {color.g:.3f}, {color.b:.3f}) Alpha({color.a:.3f})"
        )
        await asyncio.sleep(0.1)

    await controller.stop_speaking()
    await controller.cleanup()

    print("✅ Color calculation test completed!")


async def main():
    """Main test function"""
    print("🚀 Starting Crystal Light Controller Tests")

    try:
        # Test basic functionality
        await test_light_controller()

        # Test color calculations
        await test_color_calculations()

    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")

    print("\n🏁 All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
