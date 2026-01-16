
[Setup]
AppName=CineBridge Pro
AppVersion=4.16.6
DefaultDirName={autopf}\CineBridge Pro
DefaultGroupName=CineBridge Pro
UninstallDisplayIcon={app}\CineBridgePro.exe
Compression=lzma2
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=CineBridgePro_Windows_Setup
SetupIconFile=assets\icon.ico
LicenseFile=LICENSE
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\CineBridgePro.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\CineBridge Pro"; Filename: "{app}\CineBridgePro.exe"
Name: "{autodesktop}\CineBridge Pro"; Filename: "{app}\CineBridgePro.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CineBridgePro.exe"; Description: "{cm:LaunchProgram,CineBridge Pro}"; Flags: nowait postinstall skipifsilent
