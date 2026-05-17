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
 */

const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const PKG_NAME = 'seedance2-cli';
const REQUIREMENTS = path.join(__dirname, 'requirements.txt');

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

async function installPythonDeps(python, useVenv = false) {
  let targetPython = python;

  // 默认使用虚拟环境（推荐，避免系统 Python 权限问题）
  const venvPath = path.join(__dirname, '.venv');
  if (useVenv || !fs.existsSync(venvPath)) {
    if (!fs.existsSync(venvPath)) {
      log('info', 'Creating virtual environment...');
      await runCommand(python, ['-m', 'venv', venvPath], { silent: true });
    }

    const venvPython = process.platform === 'win32'
      ? path.join(venvPath, 'Scripts', 'python.exe')
      : path.join(venvPath, 'bin', 'python');

    targetPython = venvPython;
    log('info', `Using virtual environment: ${venvPath}`);
  } else if (fs.existsSync(venvPath)) {
    const venvPython = process.platform === 'win32'
      ? path.join(venvPath, 'Scripts', 'python.exe')
      : path.join(venvPath, 'bin', 'python');
    targetPython = venvPython;
    log('info', `Reusing virtual environment: ${venvPath}`);
  }

  const pipArgs = ['-m', 'pip', 'install', '-r', REQUIREMENTS];

  log('info', `Installing Python dependencies with ${targetPython}...`);
  await runCommand(targetPython, pipArgs);

  return targetPython;
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

  // 4. 安装 Python 依赖
  const useVenv = process.env.SEEDANCE_USE_VENV === '1';
  try {
    const targetPython = await installPythonDeps(python, useVenv);
    log('info', `Python dependencies installed successfully. Python: ${targetPython}`);
  } catch (err) {
    log('error', `Failed to install Python dependencies: ${err.message}`);
    process.exit(1);
  }

  // 5. 验证 CLI 可用性
  try {
    const binPath = path.join(__dirname, 'bin', 'seedance.js');
    await runCommand('node', [binPath, '--version'], { silent: true });
    log('info', 'CLI verification passed');
  } catch (err) {
    log('error', `CLI verification failed: ${err.message}`);
    process.exit(1);
  }

  log('info', 'Installation completed successfully!');
  log('info', 'Usage: npx github:li-neo/seedance2-cli <command>');
}

main().catch((err) => {
  log('error', `Unexpected error: ${err.message}`);
  process.exit(1);
});
