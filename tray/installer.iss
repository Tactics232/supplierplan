[Setup]
AppName=Supplierplan
AppVersion=1.0
DefaultDirName={autopf}\Supplierplan
DefaultGroupName=Supplierplan
OutputBaseFilename=Supplierplan-Setup
OutputDir=dist
DisableProgramGroupPage=yes
PrivilegesRequired=admin

[Files]
Source: "dist\Supplierplan\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Supplierplan"; Filename: "{app}\Supplierplan.exe"
Name: "{group}\Supplierplan deinstallieren"; Filename: "{uninstallexe}"

[Tasks]
Name: "autostart"; Description: "Mit Windows starten"; Flags: unchecked

[Run]
Filename: "{app}\Supplierplan.exe"; Description: "Supplierplan jetzt starten"; Flags: nowait postinstall skipifsilent
