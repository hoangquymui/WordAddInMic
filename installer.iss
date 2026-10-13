[Setup]
AppName=STTWordH2M
AppVersion=1.0
DefaultDirName={autopf}\STTWordH2M
DefaultGroupName=STTWordH2M
OutputDir=Output
OutputBaseFilename=STTWordH2M_Setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=app_icon.ico

[Files]
Source: "dist\STTWordH2M\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\STTWordH2M"; Filename: "{app}\STTWordH2M.exe"
Name: "{autodesktop}\STTWordH2M"; Filename: "{app}\STTWordH2M.exe"
Name: "{userstartup}\STTWordH2M"; Filename: "{app}\STTWordH2M.exe"

[Run]
Filename: "cmd.exe"; Parameters: "/c net share STTWordH2M=""{app}\_internal"" /GRANT:Everyone,READ"; Flags: runhidden waituntilterminated
Filename: "{app}\STTWordH2M.exe"; Description: "Khoi dong STTWordH2M"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Office\16.0\WEF\TrustedCatalogs\{{sttword-001}}"; ValueType: string; ValueName: "Url"; ValueData: "\\localhost\STTWordH2M"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Office\16.0\WEF\TrustedCatalogs\{{sttword-001}}"; ValueType: dword; ValueName: "Flags"; ValueData: 1; Flags: uninsdeletekey

[UninstallRun]
Filename: "cmd.exe"; Parameters: "/c net share STTWordH2M /delete"; Flags: runhidden waituntilterminated
