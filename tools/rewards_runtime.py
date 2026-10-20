"""Lifetime and single-instance control for the local rewards helper. Stdlib only."""
import os
from pathlib import Path


class InstanceLock:
    """Hold one OS file lock per proxy directory; process exit releases it even after a crash."""
    def __init__(self, directory):
        self.path = Path(directory) / 'cs2_gc_rewards.lock'
        self.file = None

    def __enter__(self):
        self.file = self.path.open('a+b')
        self.file.seek(0, os.SEEK_END)
        if self.file.tell() == 0:
            self.file.write(b'0')
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            self.file = None
            return False
        return True

    def __exit__(self, *_):
        if self.file:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()
            self.file = None


class ParentProcess:
    """Keep a Windows process handle, so a reused PID cannot keep an orphan helper alive."""
    def __init__(self, pid=None):
        self.pid = pid
        self.handle = None
        self.kernel = None
        if pid is not None and (type(pid) is not int or pid <= 0):
            raise ValueError('Parent process ID must be positive')
        if pid is not None and os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            self.kernel.OpenProcess.restype = wintypes.HANDLE
            self.kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            self.kernel.WaitForSingleObject.restype = wintypes.DWORD
            self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            self.kernel.CloseHandle.restype = wintypes.BOOL
            self.handle = self.kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only

    def alive(self):
        if self.pid is None:
            return True  # manually launched diagnostic mode
        if self.kernel is not None:
            return bool(self.handle) and self.kernel.WaitForSingleObject(self.handle, 0) == 258
        # Portable test/manual fallback. Windows production uses the retained process handle.
        try:
            os.kill(self.pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def close(self):
        if self.kernel is not None and self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def serve_until_parent_exits(server, parent, after_request=None):
    server.timeout = 1
    while parent.alive():
        server.handle_request()
        if after_request:
            after_request()
