; Instalador do RedBlack Laser (Inno Setup 6). Gerado por instalador\gerar.ps1.
#ifndef Versao
  #define Versao "0.56.0"
#endif

[Setup]
AppId={{C826768E-6609-4716-9FAA-245038FF1BDA}
AppName=RedBlack Laser
AppVersion={#Versao}
AppVerName=RedBlack Laser {#Versao}
AppPublisher=RedBlack
AppCopyright=© 2026 RedBlack. Todos os direitos reservados. Desenvolvido pela RedBlack com o assistente de IA Claude Opus (Anthropic).
DefaultDirName={autopf}\RedBlack Laser
DefaultGroupName=RedBlack Laser
; instala sem pedir administrador (na pasta do usuário); quem for admin pode escolher todos os usuários
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=RedBlackLaser-{#Versao}-Setup
SetupIconFile=..\redblack\ui\app.ico
UninstallDisplayIcon={app}\RedBlackLaser.exe
LicenseFile=LICENCA.txt
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes

[Languages]
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "associar"; Description: "Abrir arquivos .rbl com o RedBlack Laser"; GroupDescription: "Arquivos:"

[Files]
Source: "..\dist\{#Versao}\RedBlackLaser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENCA.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\RedBlack Laser"; Filename: "{app}\RedBlackLaser.exe"
Name: "{group}\Desinstalar o RedBlack Laser"; Filename: "{uninstallexe}"
Name: "{autodesktop}\RedBlack Laser"; Filename: "{app}\RedBlackLaser.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.rbl"; ValueType: string; ValueName: ""; ValueData: "RedBlackLaser.Projeto"; Flags: uninsdeletevalue; Tasks: associar
Root: HKA; Subkey: "Software\Classes\RedBlackLaser.Projeto"; ValueType: string; ValueName: ""; ValueData: "Projeto RedBlack Laser"; Flags: uninsdeletekey; Tasks: associar
Root: HKA; Subkey: "Software\Classes\RedBlackLaser.Projeto\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\RedBlackLaser.exe,0"; Tasks: associar
Root: HKA; Subkey: "Software\Classes\RedBlackLaser.Projeto\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\RedBlackLaser.exe"" ""%1"""; Tasks: associar

[Run]
Filename: "{app}\RedBlackLaser.exe"; Description: "{cm:LaunchProgram,RedBlack Laser}"; Flags: nowait postinstall skipifsilent
