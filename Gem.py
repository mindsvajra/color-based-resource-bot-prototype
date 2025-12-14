import win32gui
import numpy as np
from PIL import Image, ImageDraw
import time
import random
import keyboard
import cv2
import os
import pyautogui
import tkinter as tk
from tkinter import messagebox
from pynput.mouse import Button, Listener as MouseListener
import json
import threading
import math  # Added for sin/cos in flicks

# Constants - Customize these
BANK_COLOR = (183, 100, 43)  # RGB tuple for bank
GEM_ROCK_COLORS = [  # List of RGB tuples for different rock colors
    (151, 23, 149),  # Original color
    (161, 29, 160),  # Add more colors here, e.g., another variant
    (159, 28, 157),  # Example third color
    (134, 24, 133),
    (148, 27, 147),
    (136, 24, 135),
    (151, 27, 150),
    (158, 28, 157),
    (156, 28, 155),
    (144, 26, 143),
    (157, 28, 156),
    (154, 28, 153),
    (141, 25, 140),
    (163, 29, 162)
    # Add as many as needed
]
AVOID_COLORS = [  # Add RGB tuples for depleted rock colors or other avoid-at-all-costs colors here
    # Example: (100, 100, 100),  # Gray depleted
    # (50, 50, 50),  # Dark depleted
    # Add your found colors
    (255, 255, 0)
]
GEM_ITEM_COLORS = [  # List of RGB tuples for colors unique to gems in inventory (e.g., from outlines or item pixels)
    # Add your colors here, similar to GEM_ROCK_COLORS
    # Example: (0, 255, 0),  # Green outline or gem color
    # (255, 0, 0),  # Red highlight, etc.
    (6, 228, 149),
    (32, 232, 156),
    (37, 237, 160),
    (5, 232, 135),
    (33, 206, 151),
    (4, 206, 157),
    (25, 228, 153),
    (24, 206, 132),
    (34, 233, 162),
    (44, 241, 167)
]
DEPOSIT_ALL_IMAGE = 'deposit_all.png'  # Your existing file
ALWAYS_CLICK_IMAGE = 'alwaysclick.png'  # Add your image file here
ALWAYS_CLICK_THRESHOLD = 0.9  # Stricter threshold for always_click to reduce false positives
INVENTORY_SLOTS = 28
MAX_ROTATE_TRIES = 30
MAX_MINING_TIME = 7  # Increased timeout for walking + mining
MATCH_THRESHOLD = 0.6  # Lowered threshold for template matching to handle variations
PLAYER_CENTER_PAD_X = 0  # Tune to shift player center horizontally
PLAYER_CENTER_PAD_Y = 0  # Tune to shift player center vertically
PLAYER_RADIUS = 200  # Tune the radius for proximity limit
WAIT_FOR_RESPAWN = 1.0  # Seconds to wait for respawn within radius
CHECK_INTERVAL = 0.2  # Interval for checking during wait
INVENTORY_CHECK_INTERVAL = 1.0  # Slower check during mining to reduce spam (e.g., every 1 second)
SLOTS_FILE = 'slot_regions.json'
DO_NOT_CLICK_FILE = 'do_not_click_regions.json'
FLICK_CHANCE = 0.13  # 13% chance after ore click
MIN_FLICK_DIST = 23
MAX_FLICK_DIST = 435
FLICK_DURATION = (0.1, 0.3)  # Quick flick time range
NO_GEM_TIMEOUT = 6.0  # Seconds to wait before clicking another if no gem

# Global variables
hwnd = None
slot_regions = []  # List of (x, y, w, h) relative to client top-left
do_not_click_regions = []  # List of (x, y, w, h) for do not click areas
last_bank_side = None  # 'left' or 'right'

# Load saved slot regions if available
def load_slots():
    global slot_regions
    if os.path.exists(SLOTS_FILE):
        with open(SLOTS_FILE, 'r') as f:
            data = json.load(f)
            slot_regions = [(r['x'], r['y'], r['w'], r['h']) for r in data]

# Save slot regions to file
def save_slots():
    with open(SLOTS_FILE, 'w') as f:
        json.dump([{'x': x, 'y': y, 'w': w, 'h': h} for x, y, w, h in slot_regions], f)

# Load do not click regions
def load_do_not_click():
    global do_not_click_regions
    if os.path.exists(DO_NOT_CLICK_FILE):
        with open(DO_NOT_CLICK_FILE, 'r') as f:
            data = json.load(f)
            do_not_click_regions = [(r['x'], r['y'], r['w'], r['h']) for r in data]

# Save do not click regions
def save_do_not_click():
    with open(DO_NOT_CLICK_FILE, 'w') as f:
        json.dump([{'x': x, 'y': y, 'w': w, 'h': h} for x, y, w, h in do_not_click_regions], f)

# Get drag rectangle from mouse input
def get_drag_rect():
    positions = [None, None]
    pressed = False

    def on_click(x, y, button, is_pressed):
        nonlocal pressed
        if button == Button.left:
            if is_pressed:
                positions[0] = (x, y)
                pressed = True
            else:
                if pressed:
                    positions[1] = (x, y)
                    pressed = False
                    return False  # Stop listener

    with MouseListener(on_click=on_click) as m:
        m.join()

    return positions[0], positions[1]

# Capture window screenshot using pyautogui (no foreground forcing here)
def capture_window(hwnd):
    rect = win32gui.GetClientRect(hwnd)
    left, top = win32gui.ClientToScreen(hwnd, (rect[0], rect[1]))
    width = rect[2] - rect[0]
    height = rect[3] - rect[1]
    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    return screenshot, left, top  # Return image and screen offsets for clicks

# Find location for ores using connected components (centroids)
def find_rock_location(img, colors, proximity_center=None, radius=None):
    pixels = np.array(img)
    height, width = pixels.shape[:2]
    
    # Create mask (union of color matches)
    mask = np.zeros((height, width), dtype=np.uint8)
    for color in colors:
        color_match = np.all(pixels == color, axis=-1)
        mask[color_match] = 255  # White for matches
    
    # Apply avoid filters: set mask to 0 where avoids are in 3x3 neighborhood
    avoid_mask = np.zeros_like(mask)
    for avoid_color in AVOID_COLORS:
        avoid_match = np.all(pixels == avoid_color, axis=-1)
        avoid_mask[avoid_match] = 255
    # Dilate avoids to cover 3x3 (or larger if needed)
    kernel = np.ones((3, 3), np.uint8)
    avoid_dilated = cv2.dilate(avoid_mask, kernel)
    mask[avoid_dilated > 0] = 0
    
    # Apply do_not_click regions: set mask to 0 in those areas
    for rx, ry, rw, rh in do_not_click_regions:
        mask[ry:ry+rh, rx:rx+rw] = 0  # Note: mask is (h, w), so y then x
    
    # Find connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    
    # Filter valid blobs (exclude background label 0, and small areas)
    min_area = 10  # Tune this based on your rocks (e.g., 20-50 pixels min)
    valid_centroids = []
    for i in range(1, num_labels):  # Skip background
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            cx, cy = centroids[i]  # Centroid (x, y) - note: x horizontal, y vertical
            valid_centroids.append((int(cx), int(cy)))
    
    if not valid_centroids:
        return None
    
    centroids_arr = np.array(valid_centroids)
    
    if proximity_center is None:
        # Random selection
        idx = random.randint(0, len(centroids_arr) - 1)
        return centroids_arr[idx]  # (x, y)
    else:
        # Closest within radius
        center_x, center_y = proximity_center
        distances = np.sqrt((centroids_arr[:, 0] - center_x)**2 + (centroids_arr[:, 1] - center_y)**2)
        if radius is not None:
            mask = distances <= radius
            if np.sum(mask) == 0:
                return None
            centroids_arr = centroids_arr[mask]
            distances = distances[mask]
        if len(centroids_arr) == 0:
            return None
        idx = np.argmin(distances)
        return tuple(centroids_arr[idx])  # (x, y)

# Find location for bank using original pixel-based method
def find_bank_location(img, color, proximity_center=None, radius=None):
    width, height = img.size
    pixels = np.array(img)
    matches = np.all(pixels == color, axis=-1)
    yx = np.argwhere(matches)  # yx: [row (y vertical), col (x horizontal)]
    if len(yx) == 0:
        return None

    # Filter out avoid colors: check if position or 3x3 neighborhood has avoid color
    filtered_yx = []
    for y, x in yx:
        avoid_found = False
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    pixel_color = tuple(pixels[ny, nx])
                    if pixel_color in AVOID_COLORS:
                        avoid_found = True
                        break
            if avoid_found:
                break
        if not avoid_found:
            filtered_yx.append((y, x))

    if len(filtered_yx) == 0:
        return None

    # Filter out do not click regions
    clickable_yx = []
    for y, x in filtered_yx:
        can_click = True
        for rx, ry, rw, rh in do_not_click_regions:
            if rx <= x < rx + rw and ry <= y < ry + rh:
                can_click = False
                break
        if can_click:
            clickable_yx.append((y, x))

    if len(clickable_yx) == 0:
        return None
    yx = np.array(clickable_yx)

    if proximity_center is None:
        # Original: pick random
        idx = random.randint(0, len(yx) - 1)
        y, x = yx[idx]
        return int(x), int(y)  # Return (horizontal, vertical) as int
    else:
        # Proximity: pick closest to center within radius
        center_x, center_y = proximity_center  # (horizontal, vertical)
        distances = np.sqrt((yx[:, 1] - center_x)**2 + (yx[:, 0] - center_y)**2)
        if radius is not None:
            mask = distances <= radius
            if np.sum(mask) == 0:
                return None  # None within radius
            yx = yx[mask]
            distances = distances[mask]
        if len(yx) == 0:
            return None
        idx = np.argmin(distances)
        y, x = yx[idx]
        return int(x), int(y)

# Real click with natural mouse movement
def real_click(left, top, x, y):
    screen_x = left + x
    screen_y = top + y
    pyautogui.moveTo(screen_x, screen_y, duration=random.uniform(0.1, 0.5), tween=pyautogui.easeInOutQuad)
    pyautogui.click()
    return pyautogui.position()  # Return new mouse pos after click

# Simulate a random mouse flick (quick movement in random direction)
def random_mouse_flick():
    angle = random.uniform(0, 2 * math.pi)  # Random angle in radians
    dist = random.uniform(MIN_FLICK_DIST, MAX_FLICK_DIST)
    dx = int(dist * math.cos(angle))
    dy = int(dist * math.sin(angle))
    duration = random.uniform(*FLICK_DURATION)
    pyautogui.moveRel(dx, dy, duration=duration, tween=pyautogui.easeInOutQuad)  # Use quad for slight curve feel

# Rotate camera in a fixed direction
def rotate_camera(direction, duration=None):
    pyautogui.keyDown(direction)
    if duration is None:
        time.sleep(random.uniform(2.0, 3.0))
    else:
        time.sleep(duration)
    pyautogui.keyUp(direction)

# Check if slot has an item via color matching (replaces template matching)
def has_item_in_slot(slot_img):
    pixels = np.array(slot_img)
    for color in GEM_ITEM_COLORS:
        if np.any(np.all(pixels == color, axis=-1)):
            return True
    return False

# Get slot region (now from pre-calibrated list)
def get_slot_region(slot_index):
    return slot_regions[slot_index]

# Find the next empty slot index
def find_next_empty_slot(img):
    for i in range(INVENTORY_SLOTS):
        x, y, w, h = get_slot_region(i)
        if x < 0 or y < 0:
            continue
        slot_img = img.crop((x, y, x + w, y + h))
        if not has_item_in_slot(slot_img):
            return i
    return None  # Inventory full

# Check for deposit all using template matching (without clicking)
def find_deposit_all(img):
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    if not os.path.exists(DEPOSIT_ALL_IMAGE):
        print("Deposit all template missing!")
        return None
    template = cv2.imread(DEPOSIT_ALL_IMAGE, cv2.IMREAD_COLOR)
    if template is None:
        print("Failed to load template!")
        return None
    result = cv2.matchTemplate(cv_img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val >= MATCH_THRESHOLD:
        click_x = max_loc[0] + template.shape[1] // 2
        click_y = max_loc[1] + template.shape[0] // 2
        return (click_x, click_y)
    return None

# Check for always-click image using template matching
def find_always_click(img):
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    if not os.path.exists(ALWAYS_CLICK_IMAGE):
        print("Always click template missing!")
        return None
    template = cv2.imread(ALWAYS_CLICK_IMAGE, cv2.IMREAD_COLOR)
    if template is None:
        print("Failed to load always click template!")
        return None
    result = cv2.matchTemplate(cv_img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val >= ALWAYS_CLICK_THRESHOLD:  # Use the stricter threshold here
        click_x = max_loc[0] + template.shape[1] // 2
        click_y = max_loc[1] + template.shape[0] // 2
        return (click_x, click_y)
    return None

# Click always-click if found
def click_always_click(hwnd, left, top, pos):
    real_click(left, top, *pos)
    return True

# Click deposit all
def click_deposit_all(hwnd, left, top, pos):
    real_click(left, top, *pos)
    return True

# Update last bank side based on position
def update_bank_side(bank_pos, width):
    global last_bank_side
    if bank_pos[0] < width // 2:
        last_bank_side = 'left'
    else:
        last_bank_side = 'right'

# Main bot loop
def run_bot():
    global running, hwnd, last_bank_side
    mining_start_time = None
    last_mouse_pos = None
    foreground_warning_printed = False
    bank_initialized = False

    while True:
        if hwnd is None or win32gui.GetForegroundWindow() != hwnd:
            if not foreground_warning_printed:
                print("Window not set or not in foreground - pausing until focused...")
                foreground_warning_printed = True
            time.sleep(1)
            continue
        else:
            foreground_warning_printed = False

        if not running:
            time.sleep(0.1)
            continue

        if len(slot_regions) != 28:
            print("Inventory not calibrated! Please calibrate via GUI.")
            time.sleep(1)
            continue

        img, left, top = capture_window(hwnd)
        if img is None:
            print("Capture failed - ensure window visible.")
            time.sleep(1)
            continue

        width, height = img.size

        # Initial bank find
        if not bank_initialized:
            print("Initializing bank position...")
            player_center = (width // 2 + PLAYER_CENTER_PAD_X, height // 2 + PLAYER_CENTER_PAD_Y)
            bank_pos = find_bank_location(img, BANK_COLOR, proximity_center=player_center, radius=None)
            direction = random.choice(['left', 'right'])  # Initial random
            tries = 0
            while bank_pos is None and tries < MAX_ROTATE_TRIES and running:
                rotate_camera(direction)
                time.sleep(random.uniform(0.8, 1.5))
                img, left, top = capture_window(hwnd)
                if img is None:
                    tries += 1
                    continue
                width, height = img.size
                player_center = (width // 2 + PLAYER_CENTER_PAD_X, height // 2 + PLAYER_CENTER_PAD_Y)
                bank_pos = find_bank_location(img, BANK_COLOR, proximity_center=player_center, radius=None)
                tries += 1

            if bank_pos is None and running:
                print("Bank not found during initialization - zooming out...")
                pyautogui.scroll(100)
                time.sleep(random.uniform(1.0, 2.0))
                continue

            if bank_pos:
                update_bank_side(bank_pos, width)
                print(f"Bank initialized on {last_bank_side} side.")
                bank_initialized = True
            continue

        next_empty = find_next_empty_slot(img)
        current_count = next_empty if next_empty is not None else 28

        is_banking = False

        # Bank if full
        if next_empty is None:
            is_banking = True
            print("Inventory full - searching for bank...")
            player_center = (width // 2 + PLAYER_CENTER_PAD_X, height // 2 + PLAYER_CENTER_PAD_Y)
            bank_pos = find_bank_location(img, BANK_COLOR, proximity_center=player_center, radius=None)
            if last_bank_side == 'left':
                direction = 'right'
            elif last_bank_side == 'right':
                direction = 'left'
            else:
                direction = random.choice(['left', 'right'])
            tries = 0
            while bank_pos is None and tries < MAX_ROTATE_TRIES and running:
                rotate_camera(direction)
                time.sleep(random.uniform(0.8, 1.5))
                img, left, top = capture_window(hwnd)
                if img is None:
                    tries += 1
                    continue
                width, height = img.size
                player_center = (width // 2 + PLAYER_CENTER_PAD_X, height // 2 + PLAYER_CENTER_PAD_Y)
                bank_pos = find_bank_location(img, BANK_COLOR, proximity_center=player_center, radius=None)
                tries += 1

            if bank_pos is None and running:
                print("Bank not found after rotations - zooming out...")
                pyautogui.scroll(100)  # Scroll up to zoom out (adjust if needed)
                time.sleep(random.uniform(1.0, 2.0))
                continue  # Retry in next loop after zoom

            if bank_pos and running:
                update_bank_side(bank_pos, width)
                print("Bank found - moving cursor...")
                screen_x = left + bank_pos[0]
                screen_y = top + bank_pos[1]
                pyautogui.moveTo(screen_x, screen_y, duration=random.uniform(0.5, 1.0), tween=pyautogui.easeInOutQuad)
                time.sleep(random.uniform(0.2, 0.5))
                current_color = pyautogui.pixel(int(screen_x), int(screen_y))
                if current_color == BANK_COLOR:
                    print("Color confirmed - clicking...")
                    pyautogui.click()
                    time.sleep(random.uniform(0.5, 1.0))
                    # Wait for deposit all to appear
                    deposit_start = time.time()
                    deposit_pos = None
                    while time.time() - deposit_start < 10 and deposit_pos is None and running:  # Timeout 10 sec
                        time.sleep(0.5)  # Non-spam check
                        img, left, top = capture_window(hwnd)
                        if img is None:
                            continue
                        deposit_pos = find_deposit_all(img)
                    if deposit_pos and running:
                        if click_deposit_all(hwnd, left, top, deposit_pos):
                            print("Deposited - closing bank...")
                            time.sleep(random.uniform(0.3, 0.6))
                            pyautogui.press('esc')
                            time.sleep(random.uniform(0.5, 1.0))
                    else:
                        print("Deposit all not found within timeout.")
                else:
                    print("Color mismatch - not clicking.")
            is_banking = False
            continue

        # Check for always-click image (unless banking)
        if not is_banking:
            always_click_pos = find_always_click(img)
            if always_click_pos:
                print("Always-click image detected - clicking...")
                click_always_click(hwnd, left, top, always_click_pos)
                time.sleep(random.uniform(0.5, 1.0))  # Short delay after click

        # Find rock (prioritize within radius, wait for respawn, then full screen if needed)
        player_center = (width // 2 + PLAYER_CENTER_PAD_X, height // 2 + PLAYER_CENTER_PAD_Y)
        rock_pos = find_rock_location(img, GEM_ROCK_COLORS, proximity_center=player_center, radius=PLAYER_RADIUS)

        if rock_pos is None:
            # Wait up to WAIT_FOR_RESPAWN seconds for respawn within radius
            print("No rock within radius - waiting for respawn...")
            start_wait = time.time()
            while time.time() - start_wait < WAIT_FOR_RESPAWN and rock_pos is None and running:
                time.sleep(CHECK_INTERVAL)
                img, left, top = capture_window(hwnd)
                if img is None:
                    continue
                width, height = img.size
                player_center = (width // 2 + PLAYER_CENTER_PAD_X, height // 2 + PLAYER_CENTER_PAD_Y)
                rock_pos = find_rock_location(img, GEM_ROCK_COLORS, proximity_center=player_center, radius=PLAYER_RADIUS)

        if rock_pos is None:
            # Now search full screen (closest to center), with rotations if needed
            print("No rock within radius after wait - searching full screen...")
            rock_pos = find_rock_location(img, GEM_ROCK_COLORS, proximity_center=player_center, radius=None)
            tries = 0
            while rock_pos is None and tries < MAX_ROTATE_TRIES and running:
                direction = random.choice(['left', 'right'])
                rotate_camera(direction)
                time.sleep(random.uniform(0.8, 1.5))
                img, left, top = capture_window(hwnd)
                if img is None:
                    tries += 1
                    continue
                width, height = img.size
                player_center = (width // 2 + PLAYER_CENTER_PAD_X, height // 2 + PLAYER_CENTER_PAD_Y)
                rock_pos = find_rock_location(img, GEM_ROCK_COLORS, proximity_center=player_center, radius=None)
                tries += 1

        if rock_pos and running:
            print("Rock found - mining...")
            print(f"Current inventory count: {current_count}")
            time.sleep(random.uniform(0.1, 0.3))
            last_mouse_pos = real_click(left, top, *rock_pos)
            # Random flick after click
            if random.random() < FLICK_CHANCE:
                print("Performing random mouse flick...")
                random_mouse_flick()
            mining_start_time = time.time()

            # Wait for gem to be added to inventory, check slower to reduce spam
            while time.time() - mining_start_time < MAX_MINING_TIME and running:
                time.sleep(INVENTORY_CHECK_INTERVAL)  # Slower check interval
                img_check, left_check, top_check = capture_window(hwnd)
                if img_check is None:
                    continue
                width_check, height_check = img_check.size
                player_center_check = (width_check // 2 + PLAYER_CENTER_PAD_X, height_check // 2 + PLAYER_CENTER_PAD_Y)
                bank_pos_check = find_bank_location(img_check, BANK_COLOR, proximity_center=player_center_check, radius=None)
                if bank_pos_check:
                    update_bank_side(bank_pos_check, width_check)
                elif last_bank_side is not None:
                    if last_bank_side == 'left':
                        adjust_direction = 'right'
                    else:
                        adjust_direction = 'left'
                    rotate_camera(adjust_direction, duration=random.uniform(0.2, 0.5))
                slot_x, slot_y, slot_w, slot_h = get_slot_region(next_empty)
                slot_img = img_check.crop((slot_x, slot_y, slot_x + slot_w, slot_y + slot_h))
                if has_item_in_slot(slot_img):
                    print("Gem obtained.")
                    break
                # Check for no gem timeout
                if time.time() - mining_start_time > NO_GEM_TIMEOUT:
                    print("No gem after 6 seconds - clicking another rock.")
                    break
            mining_start_time = None

        # Random camera rotate (not during mining, lower chance)
        if random.random() < 0.05 and mining_start_time is None and running:
            direction = random.choice(['left', 'right'])
            rotate_camera(direction)

        # Update last mouse pos if no click happened this loop
        last_mouse_pos = pyautogui.position()

        time.sleep(random.uniform(0.2, 0.5))  # Loop delay

# Toggle bot running state
running = False
def toggle_bot():
    global running
    running = not running
    print("Bot " + ("started" if running else "paused"))

keyboard.add_hotkey('`', toggle_bot)

# GUI setup
root = tk.Tk()
root.title("Gem Mining Bot")

# Window title entry
tk.Label(root, text="Window Title:").pack()
window_entry = tk.Entry(root)
window_entry.pack()

# Set window button
def set_window():
    global hwnd
    title = window_entry.get()
    hwnd = win32gui.FindWindow(None, title)
    if hwnd:
        messagebox.showinfo("Success", f"Window '{title}' found (HWND: {hwnd}).")
    else:
        messagebox.showerror("Error", f"Window '{title}' not found! Check the exact title.")

tk.Button(root, text="Set Window", command=set_window).pack()

# Calibrate inventory button
def calibrate_inventory():
    global slot_regions
    if not hwnd:
        messagebox.showerror("Error", "Set the window first!")
        return
    slot_regions = []
    i = 0
    while i < 28:
        messagebox.showinfo("Calibrate Slot", f"Focus the game window.\nClick and drag to select area for slot {i+1}.\nRelease mouse to confirm.")
        start, end = get_drag_rect()
        # Get current window position
        rect = win32gui.GetClientRect(hwnd)
        l, t = win32gui.ClientToScreen(hwnd, (rect[0], rect[1]))
        # Calculate relative coords
        rel_x1 = min(start[0], end[0]) - l
        rel_y1 = min(start[1], end[1]) - t
        rel_x2 = max(start[0], end[0]) - l
        rel_y2 = max(start[1], end[1]) - t
        w = rel_x2 - rel_x1
        h = rel_y2 - rel_y1
        confirm_selection = messagebox.askyesno("Confirm Selection", f"Selected relative rect: ({rel_x1}, {rel_y1}, {w}, {h})\nIs this correct? (Yes to add, No to redo)")
        if confirm_selection:
            slot_regions.append((rel_x1, rel_y1, w, h))
            i += 1
        # No else, redo
    save_slots()
    messagebox.showinfo("Success", "Inventory calibration complete and saved.")

tk.Button(root, text="Calibrate Inventory", command=calibrate_inventory).pack()

# Calibrate do not click regions button
def calibrate_do_not_click():
    global do_not_click_regions
    if not hwnd:
        messagebox.showerror("Error", "Set the window first!")
        return
    do_not_click_regions = []
    while True:
        messagebox.showinfo("Calibrate Do Not Click", "Focus the game window.\nClick and drag to select a do not click region.\nRelease mouse to confirm.")
        start, end = get_drag_rect()
        # Get current window position
        rect = win32gui.GetClientRect(hwnd)
        l, t = win32gui.ClientToScreen(hwnd, (rect[0], rect[1]))
        # Calculate relative coords
        rel_x1 = min(start[0], end[0]) - l
        rel_y1 = min(start[1], end[1]) - t
        rel_x2 = max(start[0], end[0]) - l
        rel_y2 = max(start[1], end[1]) - t
        w = rel_x2 - rel_x1
        h = rel_y2 - rel_y1
        confirm_selection = messagebox.askyesno("Confirm Selection", f"Selected relative rect: ({rel_x1}, {rel_y1}, {w}, {h})\nIs this correct? (Yes to add, No to redo)")
        if confirm_selection:
            do_not_click_regions.append((rel_x1, rel_y1, w, h))
            add_more = messagebox.askyesno("Add More", "Add another do not click region?")
            if not add_more:
                break
        # If not confirm, redo this one
    save_do_not_click()
    messagebox.showinfo("Success", "Do not click regions calibration complete and saved.")

tk.Button(root, text="Calibrate Do Not Click Regions", command=calibrate_do_not_click).pack()

# Instructions label
tk.Label(root, text="Press 'q' to toggle bot (start/pause).\nEnsure game window is visible and not minimized.").pack()

# Load on start
load_slots()
load_do_not_click()

# Start bot loop in thread
threading.Thread(target=run_bot, daemon=True).start()

# Run GUI
root.mainloop()