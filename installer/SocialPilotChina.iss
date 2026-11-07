[Setup]
AppId={{C8D2C2D7-4F5C-4F3B-A8E0-202611070001}
AppName=SocialPilot China
AppVersion=0.1.1
DefaultDirName={autopf}\SocialPilot China
DefaultGroupName=SocialPilot China
OutputDir=..\dist-installer
OutputBaseFilename=SocialPilotChina_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\SocialPilotChina.exe

[Files]
Source: "..\dist\SocialPilotChina\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\SocialPilot China"; Filename: "{app}\SocialPilotChina.exe"
Name: "{autodesktop}\SocialPilot China"; Filename: "{app}\SocialPilotChina.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："
