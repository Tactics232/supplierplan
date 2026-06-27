; DistDir/OutDir werden von tray/build.py per /D übergeben (Build außerhalb OneDrive).
; Fallback-Defaults, falls das Skript direkt (ohne Defines) kompiliert wird.
#ifndef DistDir
  #define DistDir "dist\Supplierplan"
#endif
#ifndef OutDir
  #define OutDir "dist"
#endif

[Setup]
AppName=Supplierplan
AppVersion=1.0
DefaultDirName={autopf}\Supplierplan
DefaultGroupName=Supplierplan
OutputBaseFilename=Supplierplan-Setup
OutputDir={#OutDir}
DisableProgramGroupPage=yes
PrivilegesRequired=admin

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Supplierplan"; Filename: "{app}\Supplierplan.exe"
Name: "{group}\Supplierplan deinstallieren"; Filename: "{uninstallexe}"

[Tasks]
Name: "autostart"; Description: "Mit Windows starten"; Flags: unchecked

; Autostart-Eintrag NUR wenn der Task angehakt ist. Wertname "Supplierplan" und
; das gequotete Exe (Leerzeichen in "Program Files") sind deckungsgleich mit dem
; In-App-Schalter (tray/autostart.py APP_NAME + app.py exe_command) -> idempotent,
; kein Doppel-Eintrag. uninsdeletevalue raeumt ihn bei Deinstallation weg.
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "Supplierplan"; \
  ValueData: """{app}\Supplierplan.exe"""; \
  Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\Supplierplan.exe"; Description: "Supplierplan jetzt starten"; Flags: nowait postinstall skipifsilent
