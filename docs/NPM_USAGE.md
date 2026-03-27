# NPM Usage for this repository

Quick notes to get started with npm in this project:

- Install dependencies (create `package-lock.json`):

```powershell
cd D:\dev\kurs-bot
npm install
```

- Run the package script named `test`:

```powershell
npm test
# or
yarn test
```

This repository includes a PowerShell test runner at the project root: `run_tests.ps1`.
The repository now uses a single, cross-platform Node runner at `scripts/venv.js` to centralize Python venv actions and avoid per-shell scripts. This keeps `package.json` minimal and makes `npm` the single entry point for install/run/test.

Common commands:

```powershell
cd D:\dev\kurs-bot
npm install          # installs JS deps + Python deps from pyproject.toml via postinstall (editable -e .[dev])
# or explicitly (if you prefer):
npm run install:py   # install Python deps into .venv from pyproject.toml (editable -e .[dev])
npm test             # runs pytest via the consolidated runner
npm start            # starts the backend (uvicorn) and ngrok if available (detached)
npm stop             # stop ngrok and uvicorn processes started by `npm start`
npm restart          # stop then start services (equivalent to stop + start)
npm run start:ui     # serve the dev frontend (equivalent to serve_dev_ui.ps1)
	# Note: `npm run start:ui` prints the dev UI URL (e.g. http://localhost:3000/) and
	# attempts to open it in your default browser. To skip opening the browser use
	# `npm run start:ui -- --no-open` or set the environment variable `BROWSER=none`.
npm run config       # create .env from .env.template (if missing) and open it in your editor
npm run update       # run 'git pull' and, if changes were pulled, restart services (stop then start)
npm run ping         # check Telegram API and Ollama endpoints based on .env
npm run list         # list running ngrok and uvicorn processes
```

Notes:
- The runner prefers `.venv` python if present. If `.venv` is missing, `npm install` will run the `postinstall` script which invokes the runner to create `.venv` (if `python` is on PATH) and install Python dependencies. You can still run `npm run install:py` explicitly when needed.
- You can call the runner directly with subcommands: `node ./scripts/venv.js help`.

Quick note: `npm test -- -s`

 - **What it does:** passes arguments after `--` through to the underlying test runner. In our setup the Node runner runs `python -m pytest`, so `npm test -- -s` becomes `python -m pytest -s` which runs pytest with "capture disabled" (prints test stdout/stderr live).
 - **When to use:** useful when you want to see printed debug output from tests (for example temporary debug prints in `src/services/*`), or to preserve test output ordering for debugging flaky tests.
 - **Common variants:**
	 - `npm test -- -k <expr>` run only tests matching `<expr>`
	 - `npm test -- -q` quieter pytest output
	 - `npm test -- -x` stop after first failure

Recommendation:

 - For fastest local iteration prefer `npm run test:fast` (if available) which invokes pytest directly and avoids the Node wrapper overhead. Use `npm test -- <pytest-args>` when you need the runner's environment setup or to capture live test output (`-s`).

- To run the local binary directly (prefers node_modules/.bin):

```powershell
npx <binary> [args]
```

- For cross-platform environment variables in scripts, consider adding `cross-env` as a devDependency and invoking it in `package.json` scripts.

You can now add JS dependencies (e.g., build tools or frontend libs) and define scripts in `package.json` to integrate with the Python backend or CI.
