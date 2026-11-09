const fs = require('node:fs');
const path = require('node:path');
// Puppeteer creates browser profiles here but not the directory itself.
const temporaryDirectory = path.join(__dirname, '.cache', 'puppeteer-tmp');
fs.mkdirSync(temporaryDirectory, { recursive: true });
module.exports = {
  cacheDirectory: path.join(__dirname, '.cache', 'puppeteer'),
  temporaryDirectory,
  'chrome-headless-shell': { skipDownload: true },
  firefox: { skipDownload: true },
};
