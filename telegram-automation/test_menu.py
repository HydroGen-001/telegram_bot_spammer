"""
Тест меню
"""
import asyncio

async def async_func():
    print("[ASYNC] Функция запущена")
    await asyncio.sleep(1)
    print("[ASYNC] Функция завершена")
    return True

def menu():
    while True:
        print("\n1. Тест async")
        print("2. Выход")
        choice = input("Выбор: ").strip()
        
        if choice == '1':
            print("[MENU] Запуск asyncio.run()...")
            result = asyncio.run(async_func())
            print(f"[MENU] Результат: {result}")
        elif choice == '2':
            break

if __name__ == "__main__":
    menu()
