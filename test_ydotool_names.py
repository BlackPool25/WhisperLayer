r
2
import subprocess

def test_key(name):
    print(f"--- Testing '{name}' ---")
    print(f"Typing '{name}'. You should see a newline if it works.")
    cmd = ["ydotool", "key", name]
    try:
        subprocess.run(cmd, check=True)
        print("\n(Did a newline appear above?)")
    except Exception as e:
        print(f"Error: {e}")

print("Start Test")
test_key("Return")
test_key("enter")
test_key("28")
print("End Test")
