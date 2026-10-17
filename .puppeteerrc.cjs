const path = require('node:path');
module.exports = {
  cacheDirectory: path.join(__dirname, '.cache', 'puppeteer'),
  temporaryDirectory: path.join(__dirname, '.cache', 'puppeteer-tmp'),
  'chrome-headless-shell': { skipDownload: true },
  firefox: { skipDownload: true },
};
