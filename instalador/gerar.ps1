# Gera dist\<versão>\RedBlackLaser\RedBlackLaser.exe, o ZIP portátil e o instalador dist\RedBlackLaser-<versão>-Setup.exe.
# Executar na raiz do projeto:  powershell -ExecutionPolicy Bypass -File instalador\gerar.ps1
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$versao = (python -c "import redblack; print(redblack.__version__)").Trim()

python -m PyInstaller --noconfirm --clean --windowed --name RedBlackLaser `
    --icon redblack\ui\app.ico --version-file instalador\versao.txt `
    --add-data "redblack\ui\app.ico;redblack\ui" --hidden-import pypdf --hidden-import serial --hidden-import serial.win32 `
    --hidden-import redblack.plugins.plano_corte --hidden-import redblack.plugins.plano_corte.janela `
    --hidden-import redblack.plugins.colorir_metal --hidden-import redblack.plugins.colorir_metal.janela `
    --hidden-import redblack.plugins.cilindros --hidden-import redblack.plugins.cilindros.janela `
    --hidden-import redblack.plugins.orcamento --hidden-import redblack.plugins.orcamento.janela `
    --exclude-module PIL --exclude-module numpy --exclude-module lxml --exclude-module yaml `
    --paths . --distpath "dist\$versao" --workpath build instalador\redblack_laser.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

# cada versão na sua pasta: um RedBlack aberto (de outra versão) não trava a geração
Copy-Item instalador\LICENCA.txt "dist\$versao\RedBlackLaser\LICENCA.txt" -Force
$zip = "dist\RedBlackLaser-$versao-portatil.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "dist\$versao\RedBlackLaser" -DestinationPath $zip

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 não encontrado (winget install JRSoftware.InnoSetup)" }
& $iscc "/DVersao=$versao" instalador\RedBlackLaser.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou" }
Get-ChildItem dist -File | Select-Object Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 1) } }
