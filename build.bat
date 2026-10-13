@echo off
echo Dang xoa cac ban build cu...
rmdir /s /q build dist 2>nul
echo Dang build STTWordH2M.exe...
pyinstaller -y --clean stt_word.spec
echo Xong! Thu muc dist\STTWordH2M da san sang cho Inno Setup.
pause
