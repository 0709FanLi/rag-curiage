import fs from 'node:fs';
import path from 'node:path';

function format_date(date) {
  const y = String(date.getFullYear());
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  const hh = String(date.getHours()).padStart(2, '0');
  const mm = String(date.getMinutes()).padStart(2, '0');
  return `${y}.${m}.${d} ${hh}:${mm}`;
}

function bump_patch(version) {
  const parts = String(version || '').trim().split('.');
  const major = Number(parts[0] || 0);
  const minor = Number(parts[1] || 0);
  const patch = Number(parts[2] || 0);
  if ([major, minor, patch].some((n) => Number.isNaN(n) || n < 0)) {
    return '0.0.1';
  }
  return `${major}.${minor}.${patch + 1}`;
}

function read_version_text(text) {
  const lines = String(text || '').split(/\r?\n/);
  const version_line = lines.find((l) => l.toLowerCase().startsWith('version:'));
  const version = version_line ? version_line.split(':').slice(1).join(':').trim() : '0.0.0';
  return version;
}

const project_root = path.resolve(process.cwd());
const version_file = path.join(project_root, 'verson.txt');
const public_dir = path.join(project_root, 'public');
const public_version_file = path.join(public_dir, 'verson.txt');

const now = new Date();
const today = format_date(now);

let current_text = '';
if (fs.existsSync(version_file)) {
  current_text = fs.readFileSync(version_file, 'utf8');
}

const current_version = read_version_text(current_text);
const next_version = bump_patch(current_version);

const next_text = `version: ${next_version}\n发布时间：${today}\n`;

fs.writeFileSync(version_file, next_text, 'utf8');
fs.mkdirSync(public_dir, { recursive: true });
fs.writeFileSync(public_version_file, next_text, 'utf8');

process.stdout.write(`[bump_version] ${current_version} -> ${next_version} (${today})\n`);


