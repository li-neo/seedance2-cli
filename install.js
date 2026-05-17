#!/usr/bin/env node
/**
 * seedance2-cli 自动化安装脚本
 * 兼容 OpenClaw / Hermes / 其他 Agent 框架的自动安装
 *
 * 特性：
 * - 零交互安装（--yes 模式）
 * - 自动检测 python3 / pip 可用性
 * - 支持虚拟环境隔离（推荐）
 * - 详细的 JSON 状态输出（便于 Agent 解析）
 * - 失败时返回非零退出码
 *
 * 使用方式：
 *   curl -fsSL https://raw.githubusercontent.com/li-neo/seedance2-cli/main/install.js | node
 */

const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const PKG_NAME = 'seedance2-cli';
const REPO_URL = 'https://github.com/li-neo/seedance2-cli.git';

function log(level, message) {
  const timestamp = new Date().toISOString();
  const output = JSON.stringify({ timestamp, level, message, pkg: PKG_NAME });
  if (level === 'error') {
    console.error(output);
  } else {
    console.log(output);
  }
}

function runCommand(cmd, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, {
      stdio: options.silent ? 'pipe' : 'inherit',
      ...options,
    });

    let stdout = '';
    let stderr = '';

    if (options.silent) {
      child.stdout?.on('data', (data) => { stdout += data; });
      child.stderr?.on('data', (data) => { stderr += data; });
    }

    child.on('exit', (code) => {
      if (code === 0) {
        resolve({ code: 0, stdout, stderr });
      } else {
        reject(new Error(`Command failed with code ${code}: ${stderr || stdout}`));
      }
    });

    child.on('error', (err) => {
      reject(err);
    });
  });
}

function detectPython() {
  const candidates = [
    process.env.SEEDANCE_PYTHON,
    'python3',
    'python',
  ].filter(Boolean);

  for (const py of candidates) {
    try {
      execSync(`${py} --version`, { stdio: 'pipe' });
      return py;
    } catch {
      continue;
    }
  }
  return null;
}

function detectPip(python) {
  try {
    execSync(`${python} -m pip --version`, { stdio: 'pipe' });
    return true;
  } catch {
    return false;
  }
}

async function cloneRepo(targetDir) {
  if (fs.existsSync(targetDir)) {
    log('info', `Directory exists: ${targetDir}, pulling latest changes...`);
    await runCommand('git', ['-C', targetDir, 'pull'], { silent: true });
  } else {
    log('info', `Cloning repository to ${targetDir}...`);
    await runCommand('git', ['clone', REPO_URL, targetDir], { silent: true });
  }
}

async function installPythonDeps(python, requirementsPath) {
  const venvPath = path.join(path.dirname(requirementsPath), '.venv');

  if (!fs.existsSync(venvPath)) {
    log('info', 'Creating virtual environment...');
    await runCommand(python, ['-m', 'venv', venvPath], { silent: true });
  }

  const venvPython = process.platform === 'win32'
    ? path.join(venvPath, 'Scripts', 'python.exe')
    : path.join(venvPath, 'bin', 'python');

  log('info', `Installing Python dependencies with ${venvPython}...`);
  await runCommand(venvPython, ['-m', 'pip', 'install', '-r', requirementsPath], { silent: false });

  return venvPython;
}

async function main() {
  log('info', 'Starting automated installation...');

  // 1. 检测 Node.js
  try {
    execSync('node --version', { stdio: 'pipe' });
    log('info', 'Node.js is available');
  } catch {
    log('error', 'Node.js is not installed. Please install Node.js >= 18 first.');
    process.exit(1);
  }

  // 2. 检测 Python
  const python = detectPython();
  if (!python) {
    log('error', 'Python is not installed. Please install Python 3 first.');
    process.exit(1);
  }
  log('info', `Python detected: ${python}`);

  // 3. 检测 pip
  if (!detectPip(python)) {
    log('error', 'pip is not available. Please install pip first.');
    process.exit(1);
  }
  log('info', 'pip is available');

  // 4. 克隆仓库到临时目录
  const installDir = process.env.SEEDANCE_INSTALL_DIR || path.join(os.tmpdir(), PKG_NAME);
  try {
    await cloneRepo(installDir);
    log('info', `Repository ready at ${installDir}`);
  } catch (err) {
    log('error', `Failed to clone repository: ${err.message}`);
    process.exit(1);
  }

  // 5. 安装 Python 依赖
  const requirementsPath = path.join(installDir, 'requirements.txt');
  if (!fs.existsSync(requirementsPath)) {
    log('error', `requirements.txt not found at ${requirementsPath}`);
    process.exit(1);
  }

  try {
    const targetPython = await installPythonDeps(python, requirementsPath);
    log('info', `Python dependencies installed successfully. Python: ${targetPython}`);
  } catch (err) {
    log('error', `Failed to install Python dependencies: ${err.message}`);
    process.exit(1);
  }

  // 6. 验证 CLI 可用性
  try {
    const binPath = path.join(installDir, 'bin', 'seedance.js');
    await runCommand('node', [binPath, '--version'], { silent: true });
    log('info', 'CLI verification passed');
  } catch (err) {
    log('error', `CLI verification failed: ${err.message}`);
    process.exit(1);
  }

  // 7. 输出使用信息
  log('info', 'Installation completed successfully!');
  log('info', `Install directory: ${installDir}`);
  log('info', `To use: cd ${installDir} && node bin/seedance.js <command>`);
  log('info', 'Or: npx github:li-neo/seedance2-cli <command>');
}

main().catch((err) => {
  log('error', `Unexpected error: ${err.message}`);
  process.exit(1);
});
