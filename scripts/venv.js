#!/usr/bin/env node
const { spawnSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const repoRoot = path.resolve(__dirname, '..');
const venvDir = path.join(repoRoot, '.venv');
// axios and dotenv are loaded lazily by the `ping` subcommand so other
// commands don't fail when Node deps haven't been installed yet.

function venvPython() {
  const candidates = [
    path.join(venvDir, 'Scripts', 'python.exe'),
    path.join(venvDir, 'Scripts', 'python'),
    path.join(venvDir, 'bin', 'python')
  ];
  for (const p of candidates) if (fs.existsSync(p)) return p;
  return null;
}

function findSystemPython() {
  const candidates = [
    process.env.PYTHON,
    process.env.PYTHON3,
    'python3',
    'python'
  ].filter(Boolean);
  for (const cmd of candidates) {
    const res = spawnSync(cmd, ['-V'], { stdio: 'ignore' });
    if (!res.error) return cmd;
  }
  return null;
}

function whichPython() {
  const p = venvPython();
  if (p) return p;
  return findSystemPython();
}

function runCommand(cmd, args, opts = {}) {
  const child = spawn(cmd, args, Object.assign({ stdio: 'inherit' }, opts));
  child.on('close', code => process.exit(code));
  child.on('error', err => { console.error(err); process.exit(1); });
}

function ensureVenv() {
  if (fs.existsSync(venvDir)) return true;
  const python = findSystemPython();
  if (!python) {
    console.error('No Python found. Install Python 3 or set PYTHON/PYTHON3 env var.');
    return false;
  }
  console.log('Creating venv using:', python);
  const res = spawnSync(python, ['-m', 'venv', '.venv'], { cwd: repoRoot, stdio: 'inherit' });
  return res.status === 0;
}

function installDeps() {
  const py = whichPython();
  if (!py) {
    console.error('No Python found to install dependencies. Install Python 3 or set PYTHON/PYTHON3 env var.');
    return false;
  }
  const isMac = process.platform === 'darwin';
  const isArm64 = process.arch === 'arm64';

  // Helper to run pip commands
  function runPip(args) {
    console.log('Running:', py, args.join(' '));
    const res = spawnSync(py, args, { cwd: repoRoot, stdio: 'inherit' });
    if (res.error) {
      console.error('Failed to run', args.join(' '), res.error && res.error.message);
      return res;
    }
    return res;
  }

  // Upgrade pip first
  console.log('Upgrading pip in target Python...');
  runPip(['-m', 'pip', 'install', '--upgrade', 'pip']);

  // Install CPU-only PyTorch wheel to avoid pulling CUDA wheels
  console.log('Installing CPU PyTorch wheel from official index...');
  runPip(['-m', 'pip', 'install', '--no-cache-dir', '--index-url', 'https://download.pytorch.org/whl/cpu', 'torch']);

  // Finally install project requirements
  const req = path.join(repoRoot, 'requirements.txt');
  if (fs.existsSync(req)) {
    console.log('Installing project requirements from requirements.txt...');
    runPip(['-m', 'pip', 'install', '--no-cache-dir', '-r', req]);
  } else {
    console.log('requirements.txt not found; installing project in editable mode...');
    runPip(['-m', 'pip', 'install', '-e', repoRoot]);
  }
}

function runPyModule(mod, args = []) {
  const py = whichPython();
  const finalArgs = ['-m', mod, ...args];
  console.log('Using Python:', py);
  console.log('Running:', py + ' ' + finalArgs.join(' '));
  runCommand(py, finalArgs);
}

function runScript(scriptPath, args = []) {
  const py = whichPython();
  runCommand(py, [scriptPath, ...args]);
}

// Tail helper: print last N lines of log files (non-follow)
const TAIL_MAX_LINES = 50;
function tailFile(filePath, maxLines = TAIL_MAX_LINES) {
  if (!fs.existsSync(filePath)) {
    console.log(`-- ${filePath} (not found)`);
    return;
  }
  try {
    const raw = fs.readFileSync(filePath, { encoding: 'utf8' });
    const lines = raw.split(/\r?\n/);
    const last = lines.slice(-maxLines);
    console.log(`\n===== ${path.basename(filePath)} (last ${last.length} lines) =====`);
    console.log(last.join('\n'));
  } catch (e) {
    console.error(`Failed reading ${filePath}:`, e && e.message);
  }
}

function tailLogs() {
  const scriptsDir = path.join(repoRoot, 'scripts');
  const candidates = [
    path.join(scriptsDir, 'uvicorn.err.log'),
    path.join(scriptsDir, 'uvicorn.out.log'),
    path.join(scriptsDir, 'ngrok.err.log'),
    path.join(scriptsDir, 'ngrok.out.log')
  ];
  let foundAny = false;
  for (const f of candidates) if (fs.existsSync(f)) foundAny = true;
  if (!foundAny) {
    console.log('No known log files found in scripts/; expected uvicorn.*.log or ngrok.*.log');
    return;
  }
  for (const f of candidates) tailFile(f, TAIL_MAX_LINES);
}

// CLI
const argv = process.argv.slice(2);
const cmd = argv[0] || 'help';
const cmdArgs = argv.slice(1);

switch (cmd) {
  case 'help':
    // Print a short npm-level help first (matches scripts/npm_help.js)
    const npmHelp = [
      '',
      'Project npm commands (short guide):',
      '',
      '  npm install          # installs JS deps and runs `postinstall` to set up Python venv and deps',
      '  # or explicitly (if you prefer):',
      '  npm run install:py   # install Python deps into .venv (requirements.txt or editable install)',
      '  npm test             # runs pytest via the consolidated runner',
      '  npm start            # starts the backend (uvicorn) and ngrok if available (detached)',
      '  npm stop             # stop ngrok and uvicorn processes started by `npm start`',
      '  npm restart          # stop then start services (equivalent to stop + start)',
      '  npm run start:ui     # serve the dev frontend (equivalent to serve_dev_ui.ps1) — opens browser by default; use `--no-open` or set BROWSER=none to disable',
  '  npm run init_db     # initialize database (defaults to prod.db)',
  '  npm run status      # print DB counts for active users, lessons, and messages',

      '  npm run config       # create .env from .env.template (if missing) and open it in your editor',
      "  npm run update       # run 'git pull' and, if changes were pulled, restart services (stop then start)",
      '  npm run list         # list running ngrok and uvicorn processes',
      '  npm run tail         # print last 50 lines of uvicorn/ngrok logs (non-follow)',
      '',
      'For lower-level runner commands (venv, test args, run scripts):',
      '  node ./scripts/venv.js help',
      ''
    ];
    for (const l of npmHelp) console.log(l);

    // Then print the venv.js specific help
    console.log('Usage: node scripts/venv.js <command> [args]\n');
    console.log('Commands:');
    console.log('  ensure-venv       Create .venv if missing');
    console.log('  install           Install Python deps (requirements.txt or editable)');
    console.log('  test [pytest-args]  Run pytest');
    console.log('  run <script> [args] Run a Python script');
    console.log('  exec <python-args>  Run arbitrary python with args');
    console.log('  status            Print current DB counts for active users, lessons, and messages');
    process.exit(0);
    break;
  case 'ensure-venv':
    process.exit(ensureVenv() ? 0 : 1);
    break;
  case 'install':
    installDeps();
    break;
  case 'test':
    // ensure venv exists but don't fail if creation isn't possible
    if (!venvPython()) ensureVenv();
    // Run pytest with parallel execution by default (-n auto)
    // If user provides any args, use those directly without adding defaults
    // Handle npm test -- args (where args might be joined like "test -v")
    let testArgs;
    if (cmdArgs.length > 0) {
      // Flatten args - npm might pass "test -v" as single string
      // Filter out '--' which npm uses as separator but shouldn't be passed to pytest
      testArgs = cmdArgs.join(' ').split(' ').filter(Boolean).filter(arg => arg !== '--');
    } else {
      testArgs = ['--maxfail=3', '-n', 'auto', '-q'];
    }
    runPyModule('pytest', testArgs);
    break;
  case 'run':
    if (!cmdArgs[0]) {
      console.error('run requires a script path'); process.exit(2);
    }
    runScript(cmdArgs[0], cmdArgs.slice(1));
    break;
  case 'start-ui':
    // Start the dev UI static server in the foreground (matching serve_dev_ui.ps1)
    {
      const portIndex = cmdArgs.indexOf('--port');
      const port = portIndex >= 0 ? cmdArgs[portIndex + 1] : '3000';
      const apiPortIndex = cmdArgs.indexOf('--api-port');
      const apiPort = apiPortIndex >= 0 ? cmdArgs[apiPortIndex + 1] : '8000';
      const reload = cmdArgs.includes('--reload') || cmdArgs.includes('-r');
      const directApi = cmdArgs.includes('--direct-api') || cmdArgs.includes('-d');
      const noOpen = cmdArgs.includes('--no-open');

      // Build args for dev_static_server.py
      const argsForScript = ['scripts/dev_static_server.py', '--port', port, '--directory', 'static/dev_web_client', '--api-port', apiPort];
      if (directApi) argsForScript.push('--direct-api');
      if (reload) argsForScript.push('--reload');

      // Run in foreground so user can see logs
      // Print URL and try to open in default browser (unless --no-open or BROWSER=none)
      const uiUrl = `http://localhost:${port}/`;
      console.log('\nDev UI available at:', uiUrl);
      if (!noOpen && process.env.BROWSER !== 'none') {
        // Attempt to open the browser but handle errors gracefully so a
        // missing opener (e.g. xdg-open on headless WSL) does not crash the
        // runner. Print a friendly tip to the user instead.
        function tryOpen(url) {
          let cmd, args;
          if (process.platform === 'win32') {
            cmd = 'cmd'; args = ['/c', 'start', '""', url];
          } else if (process.platform === 'darwin') {
            cmd = 'open'; args = [url];
          } else {
            cmd = 'xdg-open'; args = [url];
          }
          try {
            const child = spawn(cmd, args);
            child.on('error', (err) => {
              console.log(`\nCould not open browser: ${err.message}`);
              console.log('You are running in a headless environment or the system opener is missing.');
              console.log('Options: 1) Start the UI with `--no-open`; 2) set `BROWSER=none` to disable auto-open; 3) install a system opener (e.g. `xdg-utils` on Linux/WSL).');
            });
          } catch (e) {
            console.log(`\nCould not open browser: ${e && e.message}`);
            console.log('You are running in a headless environment or the system opener is missing.');
            console.log('Options: 1) Start the UI with `--no-open`; 2) set `BROWSER=none` to disable auto-open; 3) install a system opener (e.g. `xdg-utils` on Linux/WSL).');
          }
        }
        tryOpen(uiUrl);
      }

      runScript(argsForScript[0], argsForScript.slice(1));
    }
    break;
  case 'ngrok':
    // Start ngrok only (detached) - allows running uvicorn in foreground separately
    {
      const scriptsDir = path.join(repoRoot, 'scripts');
      const ngrokOut = path.join(scriptsDir, 'ngrok.out.log');
      const ngrokErr = path.join(scriptsDir, 'ngrok.err.log');

      // Helper to start detached process with logs
      function startDetached(bin, args, outPath, errPath, pidFile) {
        try {
          const out = fs.openSync(outPath, 'a');
          const err = fs.openSync(errPath, 'a');
          const child = spawn(bin, args, { cwd: repoRoot, detached: true, stdio: ['ignore', out, err] });
          child.unref();
          try {
            if (pidFile) fs.writeFileSync(pidFile, String(child.pid));
          } catch (e) {
            // non-fatal if pid file cannot be written
          }
          return child.pid || null;
        } catch (err) {
          return null;
        }
      }

      // Start ngrok if available
      try {
        const check = spawnSync('ngrok', ['version']);
        if (check.status === 0) {
          const pid = startDetached('ngrok', ['http', '8000'], ngrokOut, ngrokErr, path.join(scriptsDir, 'ngrok.pid'));
          if (pid) {
            console.log('Started ngrok detached (PID:', pid, ', logs:', ngrokOut, ngrokErr + ')');
            console.log('\nNow you can run: npm run start:foreground');
          } else {
            console.error('Failed to start ngrok');
            process.exit(1);
          }
        } else {
          console.log('ngrok not found in PATH; skipping ngrok startup');
        }
      } catch (e) {
        console.log('ngrok not available; skipping');
      }
    }
    break;
  case 'start':
    // Start ngrok (detached) and uvicorn (detached) similar to start-linux.sh
    {
      const scriptsDir = path.join(repoRoot, 'scripts');
      const ngrokOut = path.join(scriptsDir, 'ngrok.out.log');
      const ngrokErr = path.join(scriptsDir, 'ngrok.err.log');
      const uvicornOut = path.join(scriptsDir, 'uvicorn.out.log');
      const uvicornErr = path.join(scriptsDir, 'uvicorn.err.log');
      // Clean previous logs to avoid stale noise
      [ngrokOut, ngrokErr, uvicornOut, uvicornErr].forEach(p => {
        try { fs.unlinkSync(p); } catch (_) {}
      });

      // Helper to start detached process with logs
      function startDetached(bin, args, outPath, errPath, pidFile) {
        try {
          const out = fs.openSync(outPath, 'a');
          const err = fs.openSync(errPath, 'a');
          const child = spawn(bin, args, { cwd: repoRoot, detached: true, stdio: ['ignore', out, err] });
          child.unref();
          try {
            if (pidFile) fs.writeFileSync(pidFile, String(child.pid));
          } catch (e) {
            // non-fatal if pid file cannot be written
          }
          return child.pid || null;
        } catch (err) {
          return null;
        }
      }

      // Ensure virtualenv exists and prefer venv Python for uvicorn
      ensureVenv();
      const venvPy = venvPython();
      let py = venvPy || whichPython();
      if (!py) {
        console.error('No Python available to start uvicorn. Install Python or create .venv');
        process.exit(1);
      }

      // Start ngrok if available
      let ngrokStarted = false;
      try {
        const check = spawnSync('ngrok', ['version']);
        if (check.status === 0) {
          ngrokStarted = startDetached('ngrok', ['http', '8000'], ngrokOut, ngrokErr);
          if (ngrokStarted) console.log('Started ngrok detached (logs:', ngrokOut, ngrokErr + ')');
        } else {
          console.log('ngrok not found in PATH; skipping ngrok startup');
        }
      } catch (e) {
        console.log('ngrok not available; skipping');
      }

      // Determine uvicorn command
      py = whichPython();
      let uvBin = null;
      let uvArgs = null;
      try {
        const uvCheck = spawnSync('uvicorn', ['--version']);
        if (uvCheck.status === 0) {
          uvBin = 'uvicorn';
          uvArgs = ['src.api.app:app', '--host', '127.0.0.1', '--port', '8000'];
          } else {
          // fall back to python -m uvicorn
          uvBin = py;
          uvArgs = ['-m', 'uvicorn', 'src.api.app:app', '--host', '127.0.0.1', '--port', '8000'];
          }
        } catch (e) {
        uvBin = py;
        uvArgs = ['-m', 'uvicorn', 'src.api.app:app', '--host', '127.0.0.1', '--port', '8000'];
        }

      // Start uvicorn detached
      const uvStarted = startDetached(uvBin, uvArgs, uvicornOut, uvicornErr);
      if (uvStarted) console.log('Started uvicorn detached (logs:', uvicornOut, uvicornErr + ')');
        else {
          console.error('Failed to start uvicorn; check that uvicorn is installed in the venv');
          process.exit(1);
      }

      console.log('\nTo view logs:');
      console.log('  tail -f', uvicornErr, uvicornOut);

      // Wait a bit for services to start, then print last 50 lines of logs
      console.log('\nWaiting 10 seconds, then printing last 50 lines from logs to confirm startup...');
      setTimeout(() => {
        try {
          // Use the internal tailLogs function defined above instead of an external script
          tailLogs();
        } catch (e) {
          console.error('Failed to show tail logs:', e && e.message);
        }
        process.exit(0);
      }, 10000);
    }
    break;
  case 'update':
    // Run 'git pull' and restart services if updates were pulled
    {
      console.log('Running git pull...');
      const gitRes = spawnSync('git', ['pull'], { cwd: repoRoot, encoding: 'utf8' });
      const out = (gitRes.stdout || '') + (gitRes.stderr || '');
      if (gitRes.error) {
        console.error('git pull failed to start:', gitRes.error.message || gitRes.error);
        process.exit(1);
      }

      if (gitRes.status !== 0) {
        console.error('git pull failed:', out);
        process.exit(gitRes.status || 1);
      }

      if (/Already up[ -]?to date\.|Already up-to-date\./i.test(out) || /Already up to date/i.test(out)) {
        console.log('Repository already up to date; nothing to do.');
        process.exit(0);
      }

      console.log('Updates pulled from remote:\n', out);
      console.log('Stopping services (if running)...');
      // call stop via node process to reuse stop logic
      try {
        const node = process.execPath || 'node';
        const runner = path.join(__dirname, 'venv.js');
        spawnSync(node, [runner, 'stop'], { stdio: 'inherit', cwd: repoRoot });
      } catch (e) {
        console.warn('Failed to run stop command:', e && e.message);
      }

      console.log('Starting services...');
      try {
        const node = process.execPath || 'node';
        const runner = path.join(__dirname, 'venv.js');
        spawnSync(node, [runner, 'start'], { stdio: 'inherit', cwd: repoRoot });
      } catch (e) {
        console.error('Failed to run start command:', e && e.message);
        process.exit(1);
      }

      console.log('Update/install restart complete.');
      process.exit(0);
    }
    break;
  case 'stop':
    // Stop ngrok and uvicorn processes (cross-platform)
    {
      function safeRun(cmd, args) {
        try { return spawnSync(cmd, args || [], { cwd: repoRoot }); } catch (e) { return { status: 1 }; }
      }

      // Attempt to find processes listening on port 8000 and terminate them first.
      const targetPort = process.env.PORT || '8000';
      const killedPids = new Set();

      function killPid(pid, reason) {
        try {
          if (process.platform === 'win32') {
            // Try taskkill first
            let res = spawnSync('taskkill', ['/PID', pid, '/F']);
            if (res && res.status === 0) {
              console.log(`Killed PID ${pid}${reason ? ' (' + reason + ')' : ''}`);
              killedPids.add(pid);
              return;
            }

            // Try PowerShell Stop-Process
            try {
              const psRes = spawnSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', `Stop-Process -Id ${pid} -Force -ErrorAction SilentlyContinue`], { encoding: 'utf8' });
              if (psRes && psRes.status === 0) {
                console.log(`Killed PID ${pid}${reason ? ' (' + reason + ')' : ''} via PowerShell`);
                killedPids.add(pid);
                return;
              }
            } catch (_) {}

            // Try taskkill with process tree
            res = spawnSync('taskkill', ['/PID', pid, '/F', '/T']);
            if (res && res.status === 0) {
              console.log(`Killed PID ${pid}${reason ? ' (' + reason + ')' : ''} (tree)`);
              killedPids.add(pid);
              return;
            }

            console.log('Failed to kill PID', pid, '(taskkill/powershell attempts returned non-zero). You may need elevated privileges.');
          } else {
            // POSIX: try graceful TERM then SIGKILL
            let res = spawnSync('kill', ['-TERM', pid]);
            if (res && res.status === 0) {
              console.log(`Killed PID ${pid}${reason ? ' (' + reason + ')' : ''}`);
              killedPids.add(pid);
              return;
            }
            res = spawnSync('kill', ['-9', pid]);
            if (res && res.status === 0) {
              console.log(`Killed PID ${pid}${reason ? ' (' + reason + ')' : ''} (SIGKILL)`);
              killedPids.add(pid);
              return;
            }
            console.log('Failed to kill PID', pid, '(kill attempts returned non-zero)');
          }
        } catch (e) {
          console.log('Failed to kill PID', pid, e && e.message);
        }
      }

      if (process.platform === 'win32') {
        // On Windows we only stop ngrok. Uvicorn runs in its own terminal
        // window and should not be killed by this command.
        console.log('Stopping ngrok only (Windows). Uvicorn is not touched.');
        const scriptsDir = path.join(repoRoot, 'scripts');
        const pidFile = path.join(scriptsDir, 'ngrok.pid');
        let stopped = false;

        try {
          if (fs.existsSync(pidFile)) {
            const pid = fs.readFileSync(pidFile, 'utf8').trim();
            if (pid) {
              const res = spawnSync('taskkill', ['/PID', pid, '/F']);
              if (res && res.status === 0) {
                console.log('Stopped ngrok (pid ' + pid + ') via pid file.');
                stopped = true;
                try { fs.unlinkSync(pidFile); } catch (_) {}
              } else {
                console.log('taskkill by pid failed; will try by image name.');
              }
            }
          }
        } catch (e) {
          // non-fatal; continue to image-name fallback
        }

        if (!stopped) {
          try {
            const res2 = spawnSync('taskkill', ['/IM', 'ngrok.exe', '/F']);
            if (res2 && res2.status === 0) {
              console.log('Stopped ngrok by image name (ngrok.exe).');
              stopped = true;
            } else {
              console.log('No ngrok process found via taskkill, or taskkill failed. It may not be running.');
            }
          } catch (e) {
            console.log('Failed to run taskkill to stop ngrok:', e && e.message);
          }
        }

        process.exit(0);
      } else {
        console.log('Stopping services on POSIX (attempting port-based detection first)...');

        // Prefer lsof if available
        try {
          const lsof = spawnSync('lsof', ['-ti', `:${targetPort}`], { encoding: 'utf8' });
          if (lsof && lsof.stdout && lsof.stdout.trim()) {
            const pids = lsof.stdout.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
            for (const pid of pids) if (!killedPids.has(pid)) killPid(pid, `listening on port ${targetPort}`);
          }
        } catch (e) {
          // lsof not available; try ss
        }

        if (killedPids.size === 0) {
          try {
            const ss = spawnSync('ss', ['-ltnp'], { encoding: 'utf8' });
            if (ss && ss.stdout) {
              const lines = ss.stdout.split(/\r?\n/);
              for (const l of lines) {
                if (l.indexOf(':' + targetPort) >= 0) {
                  // try to extract pid=1234
                  const m = l.match(/pid=(\d+),/);
                  if (m && m[1]) {
                    const pid = m[1];
                    if (!killedPids.has(pid)) killPid(pid, `listening on port ${targetPort}`);
                  }
                }
              }
            }
          } catch (e) {
            // ss not available; try netstat
          }
        }

        if (killedPids.size === 0) {
          try {
            const net = spawnSync('netstat', ['-ltnp'], { encoding: 'utf8' });
            if (net && net.stdout) {
              const lines = net.stdout.split(/\r?\n/);
              for (const l of lines) {
                if (l.indexOf(':' + targetPort) >= 0) {
                  const m = l.match(/\b(\d+)\/(?:[^\s]+)/);
                  if (m && m[1]) {
                    const pid = m[1];
                    if (!killedPids.has(pid)) killPid(pid, `listening on port ${targetPort}`);
                  } else {
                    // Older netstat formats may put PID at end
                    const parts = l.trim().split(/\s+/);
                    const pid = parts[parts.length - 1];
                    if (pid && !isNaN(Number(pid)) && !killedPids.has(pid)) killPid(pid, `listening on port ${targetPort}`);
                  }
                }
              }
            }
          } catch (e) {
            // ignore
          }
        }

        // Always try to stop ngrok/uvicorn by pattern in case they're not on the target port.
        console.log('Stopping services by pattern matching (pgrep/pkill)...');
        const patterns = ['ngrok.*8000', 'ngrok', 'uvicorn', 'python.*uvicorn'];
        let anyFound = false;
        for (const pat of patterns) {
          try {
            const list = spawnSync('pgrep', ['-a', '-f', pat], { encoding: 'utf8' });
            if (list && list.stdout && list.stdout.trim()) {
              anyFound = true;
              console.log(`\nProcesses matching /${pat}/:`);
              console.log(list.stdout.trim());
              const pids = list.stdout.split(/\r?\n/).map(l => (l || '').trim().split(/\s+/)[0]).filter(Boolean);
              for (const pid of pids) if (!killedPids.has(pid)) killPid(pid, `matched /${pat}/`);
            }
          } catch (e) {
            // pgrep might not be available; continue
          }
        }

        if (!anyFound) {
          console.log('Attempting pkill as a last resort...');
          for (const p of ['ngrok.*8000', 'ngrok', 'uvicorn', 'python.*uvicorn']) {
            try {
              const r = spawnSync('pkill', ['-f', p], { encoding: 'utf8' });
              if (r && (r.status === 0)) console.log(`pkill matched pattern /${p}/ and exited 0`);
              else if (r && r.status !== 0 && r.stderr) console.log(`pkill pattern /${p}/ exited ${r.status}: ${r.stderr.trim()}`);
            } catch (e) {
              // ignore
            }
          }
        }
      }

      // Verify whether any processes are still listening on the target port
      try {
        const remaining = [];
        if (process.platform === 'win32') {
          const net2 = spawnSync('netstat', ['-ano'], { encoding: 'utf8' });
          if (net2 && net2.stdout) {
            const lines2 = net2.stdout.split(/\r?\n/);
            for (const l of lines2) {
              if (l && l.indexOf(':' + targetPort) >= 0 && /LISTENING/i.test(l)) {
                const parts = l.trim().split(/\s+/);
                const pid = parts[parts.length - 1];
                if (pid && !killedPids.has(pid)) remaining.push(pid);
              }
            }
          }
        } else {
          try {
            const lsof2 = spawnSync('lsof', ['-ti', `:${targetPort}`], { encoding: 'utf8' });
            if (lsof2 && lsof2.stdout && lsof2.stdout.trim()) {
              const pids = lsof2.stdout.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
              for (const pid of pids) if (!killedPids.has(pid)) remaining.push(pid);
            }
          } catch (e) {}
          try {
            const net2 = spawnSync('netstat', ['-ltnp'], { encoding: 'utf8' });
            if (net2 && net2.stdout) {
              const lines2 = net2.stdout.split(/\r?\n/);
              for (const l of lines2) {
                if (l && l.indexOf(':' + targetPort) >= 0) {
                  const m = l.match(/\b(\d+)\/(?:[^\s]+)/);
                  if (m && m[1] && !killedPids.has(m[1])) remaining.push(m[1]);
                }
              }
            }
          } catch (e) {}
        }

        if (remaining.length) {
          console.warn('Warning: some processes are still listening on port', targetPort, ':', Array.from(new Set(remaining)).join(', '));
          console.warn('You may need to run the stop command with elevated privileges or inspect the processes with `tasklist`/`ps -ef`.');
        } else {
          console.log('Stop command completed. No remaining listeners detected on port', targetPort + '.');
        }
      } catch (e) {
        console.log('Stop command completed. Verify processes are stopped with `ps`/`tasklist`.');
      }
      // List matching processes after stop so user can verify
      if (process.platform === 'win32') {
        console.log('\nListing processes matching ngrok or uvicorn (Windows) after stop...');
        try {
          // Exclude the listing PowerShell process itself by filtering by ProcessId -ne $PID
          const psListPost = spawnSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -and ($_.CommandLine -match 'ngrok' -or $_.CommandLine -match 'uvicorn') } | Select-Object ProcessId, CommandLine | Format-List"], { encoding: 'utf8' });
          if (psListPost && psListPost.stdout && psListPost.stdout.trim()) {
            console.log(psListPost.stdout);
          } else {
            console.log('No matching processes found.');
          }
        } catch (e) {
          console.error('Failed to list processes via PowerShell after stop:', e && e.message);
        }
      }
      process.exit(0);
    }
    break;
    case 'list':
      // List running ngrok and uvicorn processes (cross-platform)
      {
        if (process.platform === 'win32') {
          console.log('Listing processes matching ngrok or uvicorn (Windows)...');
          try {
            // Exclude the listing helper itself by ensuring ProcessId -ne $PID
            // Use same detection as the 'stop' pre-scan: include net TCP owners
            // and commandline matches, and exclude the listing helper itself.
            // Use an explicit array collection and concatenation in PowerShell
            // to avoid runtime errors when the + operator isn't defined for
            // the returned object types (op_Addition errors).
            const psCommand = "& { $p1 = @(Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess); $p2 = @(Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -and ($_.CommandLine -match 'ngrok' -or $_.CommandLine -match 'uvicorn') } | Select-Object -ExpandProperty ProcessId); $all = ($p1 + $p2) | Sort-Object -Unique; if ($all -and $all.Count -gt 0) { foreach ($procId in $all) { Get-CimInstance Win32_Process -Filter \"ProcessId=$procId\" | Select-Object ProcessId, CommandLine } } else { Write-Output 'No matching processes found.' } }";
            const ps = spawnSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', psCommand], { encoding: 'utf8' });
            if (ps.stdout && ps.stdout.trim()) console.log(ps.stdout);
            else if (ps.stderr && ps.stderr.trim()) console.error(ps.stderr);
            else console.log('No matching processes found.');
          } catch (e) {
            console.error('Failed to list processes via PowerShell:', e && e.message);
          }
        } else {
          console.log('Listing processes matching ngrok or uvicorn (POSIX)...');
          try {
            const ng = spawnSync('pgrep', ['-a', 'ngrok'], { encoding: 'utf8' });
            const uv = spawnSync('pgrep', ['-a', 'uvicorn'], { encoding: 'utf8' });
            let printed = false;
            if (ng && ng.stdout && ng.stdout.trim()) { console.log(ng.stdout); printed = true; }
            if (uv && uv.stdout && uv.stdout.trim()) { console.log(uv.stdout); printed = true; }
            if (!printed) {
              // fallback to ps aux | grep
              const ps = spawnSync('ps', ['aux'], { encoding: 'utf8' });
              if (ps && ps.stdout) {
                const lines = ps.stdout.split(/\r?\n/).filter(l => /ngrok|uvicorn/.test(l));
                if (lines.length) console.log(lines.join('\n'));
                else console.log('No matching processes found.');
              } else {
                console.log('No matching processes found.');
              }
            }
          } catch (e) {
            console.error('Failed to list processes:', e && e.message);
          }
        }
        process.exit(0);
      }
      break;
    case 'status':
      // Print status counts from the currently configured DB
      if (!venvPython()) ensureVenv();
      runScript(path.join(repoRoot, 'scripts', 'inspect', 'inspect_status.py'));
      break;
  case 'tail':
    // Print last N lines of service logs (non-follow)
    tailLogs();
    process.exit(0);
    break;
  case 'exec':
    const py = whichPython();
    runCommand(py, cmdArgs);
    break;
  case 'config':
    // Ensure .env exists by copying .env.template and open in editor
    {
      const templatePath = path.join(repoRoot, '.env.template');
      const envPath = path.join(repoRoot, '.env');
      if (!fs.existsSync(envPath)) {
        if (fs.existsSync(templatePath)) {
          fs.copyFileSync(templatePath, envPath);
          console.log('.env created from .env.template');
        } else {
          console.warn('.env.template not found; creating empty .env');
          fs.writeFileSync(envPath, '');
        }
      } else {
        console.log('.env already exists; leaving untouched');
      }

      // Open editor: prefer $EDITOR, fallback to platform default opener
      const fileToOpen = envPath;
      // Prefer nano on POSIX when available (unless explicitly disabled via EDITOR=none).
      let editor = process.env.EDITOR;
      if (process.platform !== 'win32') {
        // If nano exists on PATH, prefer it regardless of existing EDITOR (user requested enforcement).
        try {
          const which = spawnSync('which', ['nano'], { encoding: 'utf8' });
          if (which && which.status === 0 && which.stdout && which.stdout.trim()) {
            if (process.env.EDITOR !== 'none') editor = 'nano';
          } else if (!editor) {
            editor = 'vi';
          }
        } catch (e) {
          if (!editor) editor = 'vi';
        }
      }

      if (editor && editor !== 'none') {
        console.log('Opening .env in editor:', editor);
        const parts = editor.split(' ');
        const cmdEditor = parts[0];
        const args = parts.slice(1).concat([fileToOpen]);
        const ed = spawn(cmdEditor, args, { stdio: 'inherit' });
        ed.on('close', code => process.exit(code));
        ed.on('error', err => { console.error('Failed to launch editor:', err); process.exit(1); });
      } else {
        // Platform default opener (or editor explicitly disabled via EDITOR=none)
        if (process.platform === 'win32') {
          spawn('cmd', ['/c', 'start', '""', fileToOpen]);
        } else if (process.platform === 'darwin') {
          spawn('open', [fileToOpen]);
        } else {
          spawn('xdg-open', [fileToOpen]);
        }
        process.exit(0);
      }
    }
    break;
  default:
    console.error('Unknown command:', cmd); process.exit(2);
}
