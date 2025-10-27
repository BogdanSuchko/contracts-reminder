import ctypes
from ctypes import wintypes
import struct

# --- Part 1: Setup and Primitives ---
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
ntdll = ctypes.WinDLL('ntdll')

VirtualAlloc = kernel32.VirtualAlloc
VirtualAlloc.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
VirtualAlloc.restype = wintypes.LPVOID

GetProcAddress = kernel32.GetProcAddress
GetProcAddress.argtypes = [wintypes.HMODULE, wintypes.LPCSTR]
GetProcAddress.restype = ctypes.c_void_p

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
PAGE_EXECUTE_READWRITE = 0x40

class UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT), 
                ("MaximumLength", wintypes.USHORT), 
                ("Buffer", ctypes.c_wchar_p)]

class OBJECT_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Length", wintypes.ULONG), 
                ("RootDirectory", wintypes.HANDLE), 
                ("ObjectName", ctypes.POINTER(UNICODE_STRING)),
                ("Attributes", wintypes.ULONG), 
                ("SecurityDescriptor", wintypes.LPVOID), 
                ("SecurityQualityOfService", wintypes.LPVOID)]

class IO_STATUS_BLOCK(ctypes.Structure):
    _fields_ = [("Status", wintypes.LONG), 
                ("Information", ctypes.c_void_p)]

# --- Part 2: The JIT Syscall Factory ---
def get_syscall_number(function_name_bytes):
    func_addr = GetProcAddress(ntdll._handle, function_name_bytes)
    if not func_addr:
        raise OSError(f"Could not find function {function_name_bytes.decode()} in ntdll.dll")
    syscall_number = ctypes.c_uint32.from_address(func_addr + 4).value
    return syscall_number

def create_syscall_stub(syscall_number, argtypes, restype):
    machine_code = (
        b'\x4C\x8B\xD1' +
        b'\xB8' + struct.pack('<I', syscall_number) +
        b'\x0F\x05' +
        b'\xC3'
    )
    code_buffer = VirtualAlloc(None, len(machine_code), MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
    if not code_buffer:
        raise OSError(f"VirtualAlloc failed: {ctypes.get_last_error()}")
    ctypes.memmove(code_buffer, machine_code, len(machine_code))
    SyscallFuncType = ctypes.CFUNCTYPE(restype, *argtypes)
    return SyscallFuncType(code_buffer)

# --- Part 3: Main Execution ---
if __name__ == "__main__":
    print("[*] --- Deepest Level User-Mode Execution ---")
    print("[*] Discovering syscall numbers from ntdll.dll...")
    
    try:
        syscall_open  = get_syscall_number(b'NtOpenFile')
        syscall_write = get_syscall_number(b'NtWriteFile')
        syscall_close = get_syscall_number(b'NtClose')
        print(f"    -> NtOpenFile:  {hex(syscall_open)}")
        print(f"    -> NtWriteFile: {hex(syscall_write)}")
        print(f"    -> NtClose:     {hex(syscall_close)}")
    except OSError as e:
        print(f"[!] Discovery failed: {e}")
        exit(1)
    
    print("[*] Generating machine code stubs for syscalls...")
    direct_NtOpenFile = create_syscall_stub(
        syscall_open, 
        [ctypes.POINTER(wintypes.HANDLE), wintypes.ULONG, ctypes.POINTER(OBJECT_ATTRIBUTES), 
         ctypes.POINTER(IO_STATUS_BLOCK), wintypes.ULONG, wintypes.ULONG], 
        wintypes.LONG
    )
    direct_NtWriteFile = create_syscall_stub(
        syscall_write, 
        [wintypes.HANDLE, wintypes.HANDLE, wintypes.LPVOID, wintypes.LPVOID, 
         ctypes.POINTER(IO_STATUS_BLOCK), wintypes.LPVOID, wintypes.ULONG, 
         wintypes.LPVOID, wintypes.LPVOID], 
        wintypes.LONG
    )
    direct_NtClose = create_syscall_stub(
        syscall_close, 
        [wintypes.HANDLE], 
        wintypes.LONG
    )
    
    print("[*] JIT compilation complete. Stubs are ready in executable memory.")
    
    file_handle = wintypes.HANDLE()
    try:
        print("[*] Executing direct NtOpenFile syscall...")
        nt_name = r"\??\CONOUT$"
        us_buf = ctypes.create_unicode_buffer(nt_name)
        us = UNICODE_STRING()
        
        # CRITICAL FIX: Length must be in bytes and NOT include null terminator
        us.Length = len(nt_name) * 2  # 2 bytes per wide character
        us.MaximumLength = (len(nt_name) + 1) * 2  # Include space for null terminator
        us.Buffer = ctypes.cast(us_buf, ctypes.c_wchar_p)
        
        obj_attr = OBJECT_ATTRIBUTES(
            Length=ctypes.sizeof(OBJECT_ATTRIBUTES),
            RootDirectory=None,
            ObjectName=ctypes.pointer(us),
            Attributes=0x40,  # OBJ_CASE_INSENSITIVE
            SecurityDescriptor=None,
            SecurityQualityOfService=None
        )
       
        iosb = IO_STATUS_BLOCK()
        GENERIC_READ_WRITE = 0xC0000000
        FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
       
        status = direct_NtOpenFile(
            ctypes.byref(file_handle),
            GENERIC_READ_WRITE,
            ctypes.byref(obj_attr),
            ctypes.byref(iosb),
            7,  # FILE_SHARE_READ | WRITE | DELETE
            FILE_SYNCHRONOUS_IO_NONALERT
        )
        if status != 0:
            raise OSError(f"direct_NtOpenFile syscall failed NTSTATUS=0x{status & 0xFFFFFFFF:08X}")
       
        print(f"    -> Success. Acquired console handle: {hex(file_handle.value)}")
       
        print("[*] Executing direct NtWriteFile syscall...")
        message = b"Hello, World! (from a fully native, direct syscall sequence)\r\n"
        msg_buf = ctypes.create_string_buffer(message)
       
        iosb.Status = 0
        iosb.Information = 0
        status = direct_NtWriteFile(
            file_handle, None, None, None,
            ctypes.byref(iosb),
            msg_buf,
            len(message),
            None, None
        )
        if status != 0:
            raise OSError(f"direct_NtWriteFile syscall failed NTSTATUS=0x{status & 0xFFFFFFFF:08X}")
        print(f"    -> Success. Wrote {iosb.Information} bytes to console.")
        print("\n--- OUTPUT ---")
        
    except OSError as e:
        print(f"[!] An error occurred: {e}")
    finally:
        if file_handle.value:
            print("--- END OUTPUT ---\n")
            print("[*] Executing direct NtClose syscall...")
            status = direct_NtClose(file_handle)
            if status == 0:
                print("    -> Success. Handle closed.")
            else:
                print(f"    -> Warning: NtClose failed with status {hex(status)}")

