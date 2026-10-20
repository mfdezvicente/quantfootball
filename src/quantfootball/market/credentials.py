"""Load an environment key or a Windows DPAPI-protected local credential."""

import ctypes
import os
from pathlib import Path


def credential_path(root):
    return Path(root) / "data/raw/credentials/the_odds_api.dpapi"


def credential_status(root):
    return {"environment_key_present": bool(os.environ.get("ODDS_API_KEY", "").strip()),
            "protected_file_present": credential_path(root).is_file(),
            "protected_file": str(credential_path(root)),
            "key_is_never_printed": True}


def load_api_key(root):
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if not key:
        path = credential_path(root)
        if not path.is_file():
            raise ValueError("Falta la clave. Ejecuta scripts/configure_odds_api.ps1 o configura ODDS_API_KEY.")
        if os.name != "nt":
            raise ValueError("La clave local usa Windows DPAPI. En otro sistema utiliza ODDS_API_KEY.")
        from ctypes import wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

        try:
            encrypted = bytes.fromhex(path.read_text(encoding="utf-8-sig").strip())
        except (OSError, ValueError):
            raise ValueError("El archivo de credenciales no es válido. Configura de nuevo la clave.") from None
        buffer = ctypes.create_string_buffer(encrypted)
        source = Blob(len(encrypted), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        target = Blob()
        crypt = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        crypt.CryptUnprotectData.restype = wintypes.BOOL
        kernel.LocalFree.argtypes, kernel.LocalFree.restype = [ctypes.c_void_p], ctypes.c_void_p
        if not crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1,
                                      ctypes.byref(target)):
            raise ValueError("No se puede descifrar la clave con este perfil de Windows.")
        try:
            try:
                key = ctypes.string_at(target.data, target.size).decode("utf-16-le").strip()
            except UnicodeError:
                raise ValueError("La clave descifrada no tiene un formato válido.") from None
        finally:
            kernel.LocalFree(target.data)
    if not key or len(key) > 512 or any(c.isspace() or not c.isascii() for c in key):
        raise ValueError("La clave tiene un formato no válido; vuelve a configurarla.")
    return key
