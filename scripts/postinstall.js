#!/usr/bin/env node
/**
 * postinstall 钩子：安装 Python 依赖
 * 当用户通过 npm install 安装此包时，自动执行 pip install -r requirements.txt
 */

const { spawn } = require('child_process');
const path = require('path');

const requirements = path.join(__dirname, '..', 'requirements.txt');
const python = process.env.SEEDANCE_PYTHON || 'python3';

console.log('[seedance2-cli] Installing Python dependencies...');

const child = spawn(python, ['-m', 'pip', 'install', '-r', requirements], {
  stdio: 'inherit',
});

child.on('exit', (code) => {
  if (code !== 0) {
    console.error('[seedance2-cli] Python dependency installation failed.');
    console.error(`[seedance2-cli] You may need to run manually: ${python} -m pip install -r ${requirements}`);
  } else {
    console.log('[seedance2-cli] Python dependencies installed successfully.');
  }
  process.exit(code ?? 0);
});

child.on('error', (err) => {
  console.error(`[seedance2-cli] Failed to run pip: ${err.message}`);
  process.exit(1);
});
