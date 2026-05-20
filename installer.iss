#define AppName      "SciAnalyzer"
#define AppVersion   "1.0.0"
#define AppPublisher "SciAnalyzer"
#define AppExeName   "SciAnalyzer.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
; Install to %LOCALAPPDATA% — no UAC/admin rights needed
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=SciAnalyzer_Setup
SetupIconFile=paigeForStatusBar.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; No admin rights required
PrivilegesRequired=lowest
; Uninstaller
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; ── Python application (built by PyInstaller) ──────────────────────────────
Source: "dist\SciAnalyzer\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

; ── Bundled ollama.exe + CPU backend DLLs ─────────────────────────────────
; build.bat copies ollama.exe and lib/ollama/ggml-*.dll from the Ollama
; installation. Without lib/ollama/ ollama.exe has no CPU backend to load.
Source: "ollama.exe"; DestDir: "{app}"; Flags: ignoreversion nocompression
Source: "_ollama_lib\ggml-base.dll";             DestDir: "{app}\lib\ollama"; Flags: ignoreversion
Source: "_ollama_lib\ggml-cpu-alderlake.dll";    DestDir: "{app}\lib\ollama"; Flags: ignoreversion
Source: "_ollama_lib\ggml-cpu-haswell.dll";      DestDir: "{app}\lib\ollama"; Flags: ignoreversion
Source: "_ollama_lib\ggml-cpu-icelake.dll";      DestDir: "{app}\lib\ollama"; Flags: ignoreversion
Source: "_ollama_lib\ggml-cpu-sandybridge.dll";  DestDir: "{app}\lib\ollama"; Flags: ignoreversion
Source: "_ollama_lib\ggml-cpu-skylakex.dll";     DestDir: "{app}\lib\ollama"; Flags: ignoreversion
Source: "_ollama_lib\ggml-cpu-sse42.dll";        DestDir: "{app}\lib\ollama"; Flags: ignoreversion
Source: "_ollama_lib\ggml-cpu-x64.dll";          DestDir: "{app}\lib\ollama"; Flags: ignoreversion

; ── Document templates (copy to user's APPDATA once) ───────────────────────
Source: "ШаблоныДокументов\*"; \
  DestDir: "{userappdata}\{#AppName}\ШаблоныДокументов"; \
  Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist

; ── Bundled Ollama model files ──────────────────────────────────────────────
; nocompression: GGUF weight blobs are quantized floats — lzma2 saves <5%
; but wastes 10+ minutes. Store them as-is; only compress the app code above.
Source: "_model_staging\blobs\*"; \
  DestDir: "{userappdata}\{#AppName}\models\blobs"; \
  Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist nocompression

Source: "_model_staging\manifests\*"; \
  DestDir: "{userappdata}\{#AppName}\models\manifests"; \
  Flags: ignoreversion recursesubdirs createallsubdirs onlyifdoesntexist

[Dirs]
Name: "{userappdata}\{#AppName}"
Name: "{userappdata}\{#AppName}\НайденныеСтатьи"
Name: "{userappdata}\{#AppName}\СозданныеДокументы"
Name: "{userappdata}\{#AppName}\models"

[Registry]
; ── Persistent env vars so `ollama list` works in any terminal ─────────────
; OLLAMA_MODELS — tells Ollama where to find models
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; \
  ValueName: "OLLAMA_MODELS"; \
  ValueData: "{userappdata}\{#AppName}\models"; \
  Flags: uninsdeletevalue

; Add {app} to user PATH so `ollama` command works without full path
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; \
  ValueName: "Path"; \
  ValueData: "{olddata};{app}"; \
  Check: PathNeedsApp()

[Icons]
Name: "{group}\{#AppName}"; \
  Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; \
  Filename: "{app}\{#AppExeName}"; \
  Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; \
  Description: "Запустить {#AppName}"; \
  Flags: nowait postinstall skipifsilent

[Code]
function PathNeedsApp(): Boolean;
var
  Path: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Path) then
    Path := '';
  Result := Pos(ExpandConstant('{app}'), Path) = 0;
end;
