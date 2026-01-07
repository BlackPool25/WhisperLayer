
from whisperlayer.system import TextInjector
import subprocess
import time

print("Testing TextInjector key mapping...")
t = TextInjector()

# Test cases
test_keys = ["return", "enter", "Return", "Enter"]

for key in test_keys:
    print(f"\nScanning key: '{key}'")
    # We want to see what ydotool command is generated without actually running it if possible, 
    # but we can't easily mock. We'll modify the system.py to print debug or just trust the logic.
    # Let's just run it effectively.
    
    # We can inspect the key mapping directly since it's inside the function, 
    # but we can't access local var KEYCODES.
    
    # Let's copy the logic here to verify
    KEYCODES = {
        "return": 28, "enter": 28, "kp_enter": 96,
    }
    
    key_lower = key.lower().strip()
    
    print(f"Lowered key: '{key_lower}'")
    
    if key_lower in KEYCODES:
        kc = KEYCODES[key_lower]
        print(f"Mapped to Keycode: {kc}")
        cmd = f"ydotool key {kc}:1 {kc}:0"
        print(f"Generated Command: {cmd}")
    else:
        print("NOT FOUND in simple map")

print("\nRunning actual type_key('return')...")
try:
    # This might fail if ydotool not installed/running, but we want to see if it syntax errors
    t.type_key("return")
    print("Function executed without python error.")
except Exception as e:
    print(f"Error: {e}")
