"""
Тест ввода на Windows
"""
import sys
import msvcrt

print("Тест ввода msvcrt")
print("Нажмите любую клавишу...")

# Ждём клавишу
while True:
    if msvcrt.kbhit():
        char = msvcrt.getwche()
        print(f"Нажато: {char}")
        if char == '\r' or char == '\n':
            break

print("\nВведите строку:")
line = ""
while True:
    if msvcrt.kbhit():
        char = msvcrt.getwche()
        if char == '\r' or char == '\n':
            break
        elif char == '\x08':  # Backspace
            line = line[:-1]
            print("\b \b", end="", flush=True)
        else:
            line += char
            print(char, end="", flush=True)

print(f"\nВведено: '{line}'")
