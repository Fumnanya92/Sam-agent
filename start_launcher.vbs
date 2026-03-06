' start_launcher.vbs
' Launches the SAM floating button with zero console window flicker.
' This is what the desktop shortcut and Startup folder entry should point to.

Dim oShell, sDir, sPython, sScript
Set oShell = CreateObject("WScript.Shell")

' Resolve the directory that contains this .vbs file
sDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

' Prefer pythonw.exe (no console) — falls back to python.exe
On Error Resume Next
sPython = oShell.Exec("where pythonw").StdOut.ReadLine()
On Error GoTo 0

If Len(Trim(sPython)) = 0 Then
    sPython = "python"
Else
    sPython = Trim(sPython)
End If

sScript = sDir & "launcher.py"

' Run silently (2nd arg = window style 0 = hidden, 3rd arg = wait = False)
oShell.Run Chr(34) & sPython & Chr(34) & " " & Chr(34) & sScript & Chr(34), 0, False

Set oShell = Nothing
