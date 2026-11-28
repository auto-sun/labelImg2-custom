#ifndef AppVersion
  #define AppVersion "2.8.8"
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

[CustomMessages]
english.UpgradeGuiBusy=Save your labels and close LabelImg2 Custom, then run Setup again. No application files have been replaced.
chinesesimplified.UpgradeGuiBusy=请保存标注并关闭 LabelImg2 Custom，再重新运行安装。尚未替换任何程序文件。
english.UpgradeMcpBusy=The LabelImg2 MCP process is still running or was restarted by its client. Disconnect LabelImg2 MCP in the agent client, then run Setup again. No application files have been replaced.
chinesesimplified.UpgradeMcpBusy=LabelImg2 MCP 仍在运行或被智能体客户端重新启动。请断开 LabelImg2 MCP 后重新运行安装。尚未替换任何程序文件。
english.UpgradeCheckFailed=Setup could not verify that LabelImg2 Custom and its MCP bridge are closed. Close them and run Setup again. No application files have been replaced.
chinesesimplified.UpgradeCheckFailed=无法确认 LabelImg2 Custom 和 MCP 已退出。请关闭这两项并重新运行安装。尚未替换任何程序文件。

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："; Flags: unchecked

[Files]
Source: "prepare_upgrade.ps1"; Flags: dontcopy
Source: "..\dist\LabelImg2Custom\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\{#AppExe}"; Check: ShouldCreateDesktopIcon

[Run]
Filename: "{app}\{#AppExe}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  HostPath, ScriptPath, Args: String;
  ExitCode: Integer;
begin
  Result := '';
  if not FileExists(ExpandConstant('{app}\LabelImg2Custom.exe')) and
     not FileExists(ExpandConstant('{app}\LabelImg2MCP.exe')) then
    Exit;

  try
    ExtractTemporaryFile('prepare_upgrade.ps1');
    HostPath := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
    ScriptPath := ExpandConstant('{tmp}\prepare_upgrade.ps1');
    Args := '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
      ScriptPath + '" -InstallDir "' + ExpandConstant('{app}\.') + '"';
    if not Exec(HostPath, Args, ExpandConstant('{tmp}'), SW_HIDE,
                ewWaitUntilTerminated, ExitCode) then
    begin
      Log('LabelImg2 upgrade preflight could not start: ' + IntToStr(ExitCode));
      Result := CustomMessage('UpgradeCheckFailed');
      Exit;
    end;
    Log('LabelImg2 upgrade preflight result: ' + IntToStr(ExitCode));
    case ExitCode of
      0: Result := '';
      10: Result := CustomMessage('UpgradeGuiBusy');
      11: Result := CustomMessage('UpgradeMcpBusy');
    else
      Result := CustomMessage('UpgradeCheckFailed');
    end;
  except
    Log('LabelImg2 upgrade preflight failed: ' + GetExceptionMessage);
    Result := CustomMessage('UpgradeCheckFailed');
  end;
end;

function ShouldCreateDesktopIcon(): Boolean;
begin
  Result := WizardIsTaskSelected('desktopicon') or
    FileExists(ExpandConstant('{autodesktop}\{#AppName}.lnk'));
end;
