// Generates simple branded placeholder PNG assets with no external deps.
// Run with: node scripts/gen-assets.js
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

function crc32(buf) {
  let c = ~0;
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i];
    for (let k = 0; k < 8; k++) c = c & 1 ? (c >>> 1) ^ 0xedb88320 : c >>> 1;
  }
  return ~c >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const typeBuf = Buffer.from(type, 'ascii');
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])), 0);
  return Buffer.concat([len, typeBuf, data, crc]);
}

const COLORS = {
  bg: [11, 14, 26],
  primary: [108, 140, 255],
  accent: [255, 158, 196],
};

function lerp(a, b, t) {
  return Math.round(a + (b - a) * t);
}

// Draws a dark background with a centered glowing circle + a 4-point star.
function makePng(width, height, transparentBg) {
  const cx = width / 2;
  const cy = height / 2;
  const R = Math.min(width, height) * 0.32;
  const raw = Buffer.alloc((width * 3 + 1) * height);
  let p = 0;
  for (let y = 0; y < height; y++) {
    raw[p++] = 0; // filter byte
    for (let x = 0; x < width; x++) {
      const dx = x - cx;
      const dy = y - cy;
      const dist = Math.sqrt(dx * dx + dy * dy);
      let r = COLORS.bg[0];
      let g = COLORS.bg[1];
      let b = COLORS.bg[2];

      // soft radial glow
      const glow = Math.max(0, 1 - dist / (R * 1.8));
      r = lerp(r, COLORS.primary[0], glow * 0.5);
      g = lerp(g, COLORS.primary[1], glow * 0.5);
      b = lerp(b, COLORS.primary[2], glow * 0.5);

      // ring
      if (Math.abs(dist - R) < Math.max(2, R * 0.04)) {
        r = COLORS.primary[0];
        g = COLORS.primary[1];
        b = COLORS.primary[2];
      }

      // 4-point star (sparkle) at center
      const ax = Math.abs(dx);
      const ay = Math.abs(dy);
      const arm = R * 0.55;
      const thin = R * 0.06;
      const onStar =
        (ax < thin && ay < arm) || (ay < thin && ax < arm);
      const taper = onStar && ax + ay < arm * 1.1;
      if (taper) {
        r = COLORS.accent[0];
        g = COLORS.accent[1];
        b = COLORS.accent[2];
      }

      raw[p++] = r;
      raw[p++] = g;
      raw[p++] = b;
    }
  }

  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // color type RGB
  const idat = zlib.deflateSync(raw, { level: 9 });
  return Buffer.concat([
    sig,
    chunk('IHDR', ihdr),
    chunk('IDAT', idat),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

const outDir = path.join(__dirname, '..', 'assets');
fs.mkdirSync(outDir, { recursive: true });

const targets = [
  ['icon.png', 1024, 1024],
  ['adaptive-icon.png', 1024, 1024],
  ['splash.png', 1242, 1242],
  ['favicon.png', 48, 48],
];

for (const [name, w, h] of targets) {
  fs.writeFileSync(path.join(outDir, name), makePng(w, h));
  console.log('wrote', name, `${w}x${h}`);
}
