import subprocess

keys_to_test = ["enter", "backspace", "tab", "space", "escape"]

print("Testing ydotool key names...")

for k in keys_to_test:
    print(f"\n--- Testing '{k}' ---")
    print(f"Typing '{k}'. Watch for effect (newline, deletion, etc).")
    cmd = ["ydotool", "key", k]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"Error: {e}")

print("\nDone.")
