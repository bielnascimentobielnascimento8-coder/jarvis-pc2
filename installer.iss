; Script do instalador do Jarvis - gerado automaticamente pelo GitHub Actions.
#define MyAppName "Jarvis"
#define MyAppVersion "1.0"
#define MyAppExeName "jarvis.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename=JarvisInstalador
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes

[Tasks]
Name: "startup"; Description: "Iniciar o Jarvis junto com o Windows"; GroupDescription: "Opções adicionais:"; Flags: unchecked

[Files]
Source: "dist\jarvis.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o Jarvis agora"; Flags: nowait postinstall skipifsilent
