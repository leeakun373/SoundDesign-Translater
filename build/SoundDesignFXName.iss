; Inno Setup installer for the FXName-only release.
;
; Usage:
; 1. python tools/build_fxname_release.py
; 2. Install Inno Setup 6
; 3. ISCC build\SoundDesignFXName.iss

#define MyAppName "SoundDesign FXName"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "SoundDesign Translator"
#define MyAppExeName "SoundDesignFXName.exe"

[Setup]
AppId={{D4A11867-07F5-4B2E-96D4-31D0E9C31B40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SoundDesign FXName
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=SoundDesignFXName_Setup_{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\dist\SoundDesignFXName\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\FXNAME_INSTALLER_PATHS.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
