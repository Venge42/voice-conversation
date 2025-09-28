#!/usr/bin/env python3
"""
Utility module to load lore files and inject them into system prompts.
"""

import glob
import os
from pathlib import Path


def load_lore_files(lore_directory="lore"):
    """
    Load all .txt files from the lore directory and combine their content.

    Args:
        lore_directory (str): Path to the lore directory

    Returns:
        str: Combined content of all lore files
    """
    lore_content = []

    # Check if lore directory exists
    if not os.path.exists(lore_directory):
        print(f"⚠️  Lore directory '{lore_directory}' not found. Creating it...")
        os.makedirs(lore_directory, exist_ok=True)
        return ""

    # Find all .txt files in the lore directory
    txt_files = glob.glob(os.path.join(lore_directory, "*.txt"))

    if not txt_files:
        print(f"⚠️  No .txt files found in '{lore_directory}' directory.")
        return ""

    print(f"📚 Loading {len(txt_files)} lore files...")
    print("=" * 60)

    total_size = 0
    file_details = []

    # Read each file and combine content
    for file_path in sorted(txt_files):
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read().strip()
                if content:
                    filename = os.path.basename(file_path)
                    file_size = len(content)
                    total_size += file_size

                    file_details.append(
                        {"name": filename, "size": file_size, "content": content}
                    )

                    lore_content.append(f"=== {filename} ===\n{content}")
                    print(f"   ✅ {filename:<30} | {file_size:>6} chars")
        except Exception as e:
            print(f"   ❌ Error reading {file_path}: {e}")

    if lore_content:
        combined_lore = "\n\n".join(lore_content)
        print("-" * 60)
        print(f"📊 SUMMARY:")
        print(f"   Files loaded: {len(file_details)}")
        print(f"   Total lore size: {total_size:,} characters")
        print(f"   Combined size: {len(combined_lore):,} characters")
        print("=" * 60)
        return combined_lore
    else:
        print("⚠️  No content found in lore files.")
        return ""


def create_enhanced_system_prompt(base_prompt, lore_content=""):
    """
    Create an enhanced system prompt that includes lore wisdom.

    Args:
        base_prompt (str): The base system prompt
        lore_content (str): Combined lore content to inject

    Returns:
        str: Enhanced system prompt with lore
    """
    if not lore_content:
        return base_prompt

    enhanced_prompt = f"""{base_prompt}

WICHTIGE WEISHEIT UND HINTERGRUNDWISSEN:
{"-" * 10}
{lore_content}
{"-" * 10}

Verwende diese Hintergrundwissen in deinen Antworten, um authentisch deutsch zu kommunizieren und wertvolle Einsichten zu vermitteln und Fragen zu beantworten.
Gib nichts einfach so preis. Lass die Spieler dafür Arbeiten und dich überzeugen.
"""

    return enhanced_prompt


def print_lore_size_analysis(general_lore_size, bot_lore_size, combined_lore_size):
    """
    Print detailed size analysis for lore content.

    Args:
        general_lore_size (int): Size of general lore content
        bot_lore_size (int): Size of bot-specific lore content
        combined_lore_size (int): Size of combined lore content
    """
    print(f"\n📊 LORE SIZE ANALYSIS:")
    print("=" * 50)
    print(f"General lore size:     {general_lore_size:>8,} characters")
    print(f"Bot-specific lore:     {bot_lore_size:>8,} characters")
    print(f"Combined lore size:    {combined_lore_size:>8,} characters")
    print("=" * 50)


def print_prompt_sizes(base_prompt, lore_content=""):
    """
    Print detailed size information about the prompts.

    Args:
        base_prompt (str): The base system prompt
        lore_content (str): Combined lore content
    """
    enhanced_prompt = create_enhanced_system_prompt(base_prompt, lore_content)

    print(f"\n📏 FINAL SYSTEM PROMPT SIZE ANALYSIS:")
    print("=" * 50)
    print(f"Base prompt size:      {len(base_prompt):>8,} characters")
    print(f"Lore content size:    {len(lore_content):>8,} characters")
    print(f"Final prompt size:     {len(enhanced_prompt):>8,} characters")
    print(
        f"Overhead:             {len(enhanced_prompt) - len(base_prompt) - len(lore_content):>8,} characters"
    )
    print("=" * 50)


if __name__ == "__main__":
    # Test the lore loading
    print("🧠 Lore Loader Test")
    print("=" * 30)

    lore = load_lore_files()
    if lore:
        print("\n📋 Sample of loaded lore:")
        print("-" * 40)
        print(lore[:500] + "..." if len(lore) > 500 else lore)

        # Test with a sample base prompt
        sample_base = "Du bist ein arkanes Kristallwesen in einer Fantasy Welt."
        print_prompt_sizes(sample_base, lore)
    else:
        print("No lore content found.")
