[Setup]
AppName=LaserShowDesigner
AppVersion=1.0.0
DefaultDirName={autopf}\LaserShowDesigner
DefaultGroupName=LaserShowDesigner
UninstallDisplayIcon={app}\LaserShowDesigner.exe
Compression=lzma2
SolidCompression=yes
OutputDir=release
OutputBaseFilename=LaserShowDesigner-v1.0.0-windows-x64
SetupIconFile=src\resources\logo.ico
; EV signing tool can be specified in InnoSetup but usually done post-build or via SignTool configuration
; SignTool=signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 /a $f

[Files]
Source: "dist\LaserShowDesigner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LaserShowDesigner"; Filename: "{app}\LaserShowDesigner.exe"
Name: "{autodesktop}\LaserShowDesigner"; Filename: "{app}\LaserShowDesigner.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\LaserShowDesigner.exe"; Description: "Launch LaserShowDesigner"; Flags: nowait postinstall skipifsilent
