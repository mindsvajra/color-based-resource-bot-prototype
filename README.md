[![Warning](https://img.shields.io/badge/WARNING-HIGH_BAN_RISK-red?style=for-the-badge)]()
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)]()
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)]()

# ⚠️ VERY HIGH RISK OF PERMANENT BAN ⚠️

**DO NOT USE THIS IN ANY LIVE MULTIPLAYER GAME (e.g., RuneScape-like environments).**

This is a personal prototype script for automated resource gathering (gem rock mining, banking, inventory management) using **pixel color detection** and basic computer vision. EMPHASIS on BASIC as it requires users to overlay their own colors on the game assets.

- It violates macroing/botting rules in games like Old School RuneScape (Jagex Rule 7).
- Jagex banned **over 746,000 macroing accounts in 2025 alone** (with a 23% increase in detections compared to prior years).
- False positives are rare (<1%), meaning most bans are accurate and permanent.


**This repository is for portfolio/educational purposes only** – to showcase Python implementations in:
- OpenCV (connected components, color masking)
- pyautogui (human-like mouse/keyboard simulation)
- Screen capture & region calibration
- Anti-detection attempts (random flicks, camera rotates, variable delays)

I do **not** endorse cheating. Use at your own risk – you will likely lose accounts/progress. No support for running it in real games.

If you're from Jagex: This is archived as a learning project; happy to remove if requested.

---

## Project Overview

A Tkinter-based bot that:
- Calibrates inventory slots and "do not click" regions
- Detects resources via multiple RGB colors (with avoid filters)
- Finds bank booth pixels
- Mines, waits for inventory fill, banks (template matching for "deposit all")
- Adds randomness: mouse flicks, camera rotation, variable timings

Tech stack:
- Python 3
- OpenCV (cv2)
- pyautogui
- Pillow (PIL)
- numpy
- win32gui (Windows-only)
- pynput, keyboard, tkinter

## Features Demonstrated
- Connected components for blob detection (rocks)
- Color masking + dilation to avoid depleted/exclude areas
- Proximity-based targeting (player center radius)
- Template matching for UI elements
- Human-like mouse movement (easing curves)
- JSON persistence for calibration

## Setup & Usage (For Educational Testing Only)
1. Install dependencies: `pip install opencv-python pyautogui pillow numpy pynput keyboard pywin32`
2. Prepare template images: `deposit_all.png`, `alwaysclick.png` (crop from your client)
3. Run the script
4. Use GUI to:
   - Set window title/handle
   - Calibrate 28 inventory slots (drag rectangles)
   - Optionally calibrate "do not click" regions
5. Press `` ` `` (backtick) to toggle bot

**Test in offline/single-player environments only.** Customize colors/constants at the top.

This project is to get feet wet in understanding image-detection cursor controls, it can be further refined with a "macro engine" with multi-template matching, 
OCR integration, anti-detection delays, and ML-based object recognition (using YOLO or similar, with which plenty of guides exist).

## Disclaimer (Again)
This is old code from learning CV/automation. Color bots are easily detectable – Jagex's systems flag unnatural patterns fast.

For legit portfolio ideas: Repurpose for desktop automation, image processing demos, or custom games.

Issues/PRs welcome for code improvements (not ban evasion).
