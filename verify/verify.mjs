import {fileURLToPath} from 'node:url';
import { spawn } from 'node:child_process';
import { chromium } from 'playwright-core';

const server = spawn(fileURLToPath(new URL('../rust-server/target/release/videotest-server',import.meta.url)), { stdio: 'ignore' });
await new Promise(r => setTimeout(r, 800));

const browser = await chromium.launch({ channel: 'chrome', headless: true });

async function scenario(naam, blocks) {
  const page = await browser.newPage();
  await page.goto('http://localhost:8000/', { waitUntil: 'domcontentloaded' });
  await page.evaluate((b) => localStorage.setItem('videotest-sim-v1', JSON.stringify(b)), blocks);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(400);
  for (const btn of ['#btnCanvas', '#btnMse', '#btnRtcLocal', '#btnWc']) {
    try { await page.click(btn, { timeout: 2000 }); } catch (e) { /* knop onvindbaar = eigen uitslag */ }
  }
  await page.waitForTimeout(12000);
  const row = await page.evaluate(() => ({
    canvas: document.getElementById('status-canvas').textContent,
    mse: document.getElementById('status-mse').textContent,
    rtc: document.getElementById('status-rtc').textContent,
    wc: document.getElementById('status-wc').textContent,
    sim: document.getElementById('status-sim').textContent,
    mseVideoDisplay: getComputedStyle(document.getElementById('mseVideo')).display
  }));
  await page.close();
  console.log('=== ' + naam + ' ===');
  console.log('sim:    ' + row.sim);
  console.log('canvas: ' + row.canvas);
  console.log('mse:    ' + row.mse + (row.mseVideoDisplay === 'none' ? '   [element verborgen]' : ''));
  console.log('rtc:    ' + row.rtc);
  console.log('wc:     ' + row.wc);
  console.log('');
}

await scenario('geen blokkade', {});
await scenario('alle blokkades tegelijk', { play: true, mediasource: true, webcodecs: true, webrtc: true, netwerk: true, verbergen: true });
await scenario('alleen play() laten falen', { play: true });
await scenario('alleen video-verbergen (CSS)', { verbergen: true });

await browser.close();
server.kill();
console.log('KLAAR');
