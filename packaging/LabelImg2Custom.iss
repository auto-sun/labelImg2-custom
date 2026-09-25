#ifndef AppVersion
  #define AppVersion "2.5.1"
#endif

#define AppName "LabelImg2 Custom"
#define AppExe "LabelImg2Custom.exe"

[Setup]
AppId={{A12219E8-A756-4CC5-81FE-7650A6816E36}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=auto-sun
AppPublisherURL=https://github.com/auto-sun/labelImg2-custom
AppSupportURL=https://github.com/auto-sun/labelImg2-custom/issues
AppUpdatesURL=https://github.com/auto-sun/labelImg2-custom/releases
DefaultDirName={localappdata}\Programs\LabelImg2 Custom
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=LabelImg2Custom-{#AppVersion}-Setup
SetupIconFile=..\build\LabelImg2Custom.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："; Flags: unchecked

[Files]
Source: "..\dist\LabelImg2Custom\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent
