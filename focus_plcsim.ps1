Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
'@
$p = Get-Process -Id 2792
[Win32]::ShowWindow($p.MainWindowHandle, 1)
[Win32]::SetForegroundWindow($p.MainWindowHandle)
