Param(
    [switch]$DeleteExisting,
    [switch]$Yes
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")

# Ensure project root is on PYTHONPATH so `import src` works
$env:PYTHONPATH = $ProjectRoot.Path

# Prefer the project's venv python if it exists
$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

# Decide whether to delete existing system templates:
if ($DeleteExisting) {
    $delete = "True"
} elseif ($Yes) {
    # -Yes implies user confirmed deletion
    $delete = "True"
} else {
    # Prompt interactively; if prompting fails (non-interactive), default to no
    try {
        $ans = Read-Host "Delete existing system prompt templates? [y/N]"
        $ans = $ans.Trim().ToLower()
        if ($ans -in @('y','yes')) { $delete = 'True' } else { $delete = 'False' }
    } catch {
        $delete = 'False'
    }
}

$scriptPath = Join-Path $ScriptDir "utils\seed_prompt_templates.py"

$pyCode = "import sys, importlib.util; sys.path.insert(0, r'$($ProjectRoot.Path)'); spec = importlib.util.spec_from_file_location('seed_prompt_templates', r'$scriptPath'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); mod.seed(delete_existing_system=$delete)"

# Run the code
& $python -c $pyCode

Exit $LASTEXITCODE
