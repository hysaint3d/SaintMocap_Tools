"""Standalone worker, no bpy imports. Reserved for the native transport adapter."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time


def run(directory, parent_pid, product, year):
    directory = Path(directory)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.WaitForSingleObject.restype = ctypes.c_ulong
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x00100000, False, parent_pid)
    if not handle:
        raise OSError('Cannot monitor Blender parent process')
    try:
        while not (directory / 'stop').exists():
            if kernel.WaitForSingleObject(handle, 0) != 258:
                break
            payload = dict(pid=os.getpid(), parent_pid=parent_pid,
                product=product, year=year, heartbeat=time.time(),
                transport='NOT_IMPLEMENTED', connected=False)
            tmp = directory / 'status.tmp'
            tmp.write_text(json.dumps(payload), encoding='utf-8')
            tmp.replace(directory / 'status.json')
            time.sleep(0.25)
    finally:
        kernel.CloseHandle(handle)

if __name__ == '__main__':
    run(sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4])
