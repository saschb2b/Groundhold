; The Windows installer, groundhold-windows-x64-setup.exe (tools/release/pack_windows.py; NSIS 3, makensis
; in the packaging image on Linux): for the user who runs it, no administrator, into
; %LOCALAPPDATA%\Programs\Groundhold, with a Start menu entry, a desktop shortcut only if the player ticks
; it on the Finish page (unticked at first, as the README-first and the release's downloads say), and an
; uninstaller in Settings > Apps. Installing again over it updates it in place. The player's name,
; Builders and settings live in %APPDATA%\Godot\app_userdata\Groundhold, which it never touches.
; pack_windows.py passes VERSION (X.Y.Z), FILEVERSION (four numbers), STAGE (the folder the portable zip
; holds), ICON (packaging/icons/groundhold.ico), SIDE (packaging/icons/installer.bmp, the welcome and
; finish pages' picture in place of NSIS's stock wizard) and OUT.
Unicode true
!include "MUI2.nsh"

!define NAME "Groundhold"
!define ID "io.github.saschb2b.Groundhold"
!define UNINST "Software\Microsoft\Windows\CurrentVersion\Uninstall\${ID}"
!define EXE "Groundhold.exe"
!define PUBLISHER "Sascha Becker"

Name "${NAME}"
OutFile "${OUT}"
InstallDir "$LOCALAPPDATA\Programs\${NAME}"
InstallDirRegKey HKCU "Software\${ID}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "${NAME} ${VERSION}"

VIProductVersion "${FILEVERSION}"
VIFileVersion "${FILEVERSION}"
VIAddVersionKey "ProductName" "${NAME}"
VIAddVersionKey "ProductVersion" "${VERSION}"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "FileDescription" "${NAME} setup"
VIAddVersionKey "CompanyName" "${PUBLISHER}"
VIAddVersionKey "LegalCopyright" "Copyright (c) 2026 Sascha Becker, MIT License"

!define MUI_ICON "${ICON}"
!define MUI_UNICON "${ICON}"
!define MUI_WELCOMEFINISHPAGE_BITMAP "${SIDE}"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "${SIDE}"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TEXT "A co-op tower defense for one to four players.$\r$\n$\r$\nGroundhold installs for your account alone: no administrator is needed. Your name, Builders and settings are kept apart from the game and stay when you uninstall it.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Start ${NAME}"
!define MUI_FINISHPAGE_SHOWREADME ""
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Add a shortcut to the desktop"
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION DesktopShortcut

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Section
	SetOutPath "$INSTDIR"
	File "${STAGE}\${EXE}"
	File "${STAGE}\README-first.txt"
	File "${STAGE}\LICENSE.txt"
	SetOutPath "$INSTDIR\licenses"
	File "${STAGE}\licenses\*.txt"
	SetOutPath "$INSTDIR"
	CreateShortcut "$SMPROGRAMS\${NAME}.lnk" "$INSTDIR\${EXE}"
	WriteUninstaller "$INSTDIR\uninstall.exe"
	WriteRegStr HKCU "Software\${ID}" "InstallDir" "$INSTDIR"
	WriteRegStr HKCU "${UNINST}" "DisplayName" "${NAME}"
	WriteRegStr HKCU "${UNINST}" "DisplayVersion" "${VERSION}"
	WriteRegStr HKCU "${UNINST}" "Publisher" "${PUBLISHER}"
	WriteRegStr HKCU "${UNINST}" "DisplayIcon" "$INSTDIR\${EXE}"
	WriteRegStr HKCU "${UNINST}" "InstallLocation" "$INSTDIR"
	WriteRegStr HKCU "${UNINST}" "UninstallString" '"$INSTDIR\uninstall.exe"'
	WriteRegStr HKCU "${UNINST}" "QuietUninstallString" '"$INSTDIR\uninstall.exe" /S'
	WriteRegStr HKCU "${UNINST}" "URLInfoAbout" "https://saschb2b.github.io/Groundhold/"
	WriteRegStr HKCU "${UNINST}" "HelpLink" "https://github.com/saschb2b/Groundhold"
	WriteRegDWORD HKCU "${UNINST}" "EstimatedSize" ${SIZE_KB}
	WriteRegDWORD HKCU "${UNINST}" "NoModify" 1
	WriteRegDWORD HKCU "${UNINST}" "NoRepair" 1
SectionEnd

Function DesktopShortcut
	CreateShortcut "$DESKTOP\${NAME}.lnk" "$INSTDIR\${EXE}"
FunctionEnd

; (only what it installed: the folder may have been chosen by hand, and the player's own files live
; elsewhere and stay)
Section "Uninstall"
	Delete "$INSTDIR\${EXE}"
	Delete "$INSTDIR\README-first.txt"
	Delete "$INSTDIR\LICENSE.txt"
	Delete "$INSTDIR\licenses\*.txt"
	RMDir "$INSTDIR\licenses"
	Delete "$INSTDIR\uninstall.exe"
	RMDir "$INSTDIR"
	Delete "$SMPROGRAMS\${NAME}.lnk"
	Delete "$DESKTOP\${NAME}.lnk"
	DeleteRegKey HKCU "${UNINST}"
	DeleteRegKey HKCU "Software\${ID}"
SectionEnd
