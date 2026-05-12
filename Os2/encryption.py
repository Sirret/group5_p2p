from cryptography.fernet import Fernet

# Both Alice and Bob must have this exact key.
SHARED_KEY = b'owT8oXacYmUW4EEgG0Of1643XSOJvC96P6_LxXeSUcQ='

def encrypt_message(plaintext, key):
    """Encrypts a string and returns a string"""
    f = Fernet(key)
    #  we encode the string first then we use bytes
    ciphertext = f.encrypt(plaintext.encode())
    return ciphertext.decode()

def decrypt_message(ciphertext, key):
    """Decrypts a string and returns the original plaintext"""
    f = Fernet(key)
    #  convert  ciphertext string back to bytes to decrypt
    plaintext = f.decrypt(ciphertext.encode())
    return plaintext.decode()