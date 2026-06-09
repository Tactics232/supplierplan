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

[Run]
Filename: "{app}\Supplierplan.exe"; Description: "Supplierplan jetzt starten"; Flags: nowait postinstall skipifsilent
