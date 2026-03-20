import os
p = r'C:\Users\ACER\OneDrive\Desktop\project\telegram-automation\photos\photo_2026-03-11_15-45-44.jpg'
print(f'Exists: {os.path.exists(p)}')
if os.path.exists(p):
    print(f'Size: {os.path.getsize(p)} bytes')
else:
    print('File NOT found!')
    # Покажем, что есть в папке
    folder = os.path.dirname(p)
    print(f'\nFolder contents ({folder}):')
    if os.path.exists(folder):
        for f in os.listdir(folder):
            print(f'  - {f}')
    else:
        print('Folder does not exist!')
