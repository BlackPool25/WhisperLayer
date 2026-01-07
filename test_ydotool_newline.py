
import subprocess

print("Testing ydotool type with newlines...")
text = "Line 1\nLine 2\n  - Bullet point"
cmd = ["ydotool", "type", "--key-delay", "15", text]

try:
    subprocess.run(cmd, check=True)
    print("\n(Did it type multiple lines above?)")
except Exception as e:
    print(f"Error: {e}")
