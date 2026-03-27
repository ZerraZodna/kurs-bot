# IMMEDIATE RUFF FIX (Copy-paste these exactly)

## 1. Verify Python 3.12 works
```bash
python3.12 --version
```

## 2. Create venv
```bash
rm -rf .venv
python3.12 -m venv .venv
ls .venv/bin/activate
```

## 3. Activate + Install
```bash
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

## 4. Test pre-commit
```bash
pre-commit run --all-files
```

## 5. Run app
```bash
uvicorn src.api.app:app --reload --port 8000
```

---

**Original ruff TOML error FIXED** by pyproject.toml → requires-python=">=3.10" + target-version="py310"
