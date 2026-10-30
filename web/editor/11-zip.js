  // 11-zip.js: Making and reading zip files.
  /* ---------- Zip (single file out; read .py from any zip) ---------- */
  const CRC_TABLE = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  function crc32(bytes){ let c = 0xFFFFFFFF; for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
  function makeZip(files){
    const enc = new TextEncoder(), parts = [], central = [];
    let offset = 0;
    const now = new Date();
    const dosTime = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
    const dosDate = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
    files.forEach(f => {
      const name = enc.encode(f.name), data = enc.encode(f.text), crc = crc32(data);
      const lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); lh.setUint16(8, 0, true);
      lh.setUint16(10, dosTime, true); lh.setUint16(12, dosDate, true); lh.setUint32(14, crc, true);
      lh.setUint32(18, data.length, true); lh.setUint32(22, data.length, true); lh.setUint16(26, name.length, true); lh.setUint16(28, 0, true);
      parts.push(new Uint8Array(lh.buffer), name, data);
      const ch = new DataView(new ArrayBuffer(46));
      ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 0x0314, true); ch.setUint16(6, 20, true); ch.setUint16(8, 0x0800, true); ch.setUint16(10, 0, true);
      ch.setUint16(12, dosTime, true); ch.setUint16(14, dosDate, true); ch.setUint32(16, crc, true);
      ch.setUint32(20, data.length, true); ch.setUint32(24, data.length, true); ch.setUint16(28, name.length, true);
      ch.setUint32(38, ((/\.sh$/.test(f.name) ? 0o100755 : 0o100644) << 16) >>> 0, true);  // Linux and Mac: scripts can run
      ch.setUint32(42, offset, true);
      central.push(new Uint8Array(ch.buffer), name);
      offset += 30 + name.length + data.length;
    });
    const cdSize = central.reduce((s, p) => s + p.length, 0);
    const end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true); end.setUint16(8, files.length, true); end.setUint16(10, files.length, true);
    end.setUint32(12, cdSize, true); end.setUint32(16, offset, true);
    return new Blob([...parts, ...central, new Uint8Array(end.buffer)], { type:"application/zip" });
  }
  async function readZipEntry(buf, test){
    const dv = new DataView(buf), u8 = new Uint8Array(buf);
    let eocd = -1;
    for (let i = u8.length - 22; i >= Math.max(0, u8.length - 65557); i--) if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    if (eocd < 0) throw new Error("not a zip file");
    let p = dv.getUint32(eocd + 16, true);
    const count = dv.getUint16(eocd + 10, true), dec = new TextDecoder();
    for (let i = 0; i < count; i++) {
      if (dv.getUint32(p, true) !== 0x02014b50) break;
      const method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true);
      const nlen = dv.getUint16(p + 28, true), xlen = dv.getUint16(p + 30, true), clen = dv.getUint16(p + 32, true), off = dv.getUint32(p + 42, true);
      const name = dec.decode(u8.subarray(p + 46, p + 46 + nlen));
      if (test(name)) {
        const start = off + 30 + dv.getUint16(off + 26, true) + dv.getUint16(off + 28, true);
        const raw = u8.subarray(start, start + csize);
        if (method === 0) return dec.decode(raw);
        if (method === 8 && typeof DecompressionStream !== "undefined") return new Response(new Blob([raw]).stream().pipeThrough(new DecompressionStream("deflate-raw"))).text();
        throw new Error("this file uses a compression this browser can't open");
      }
      p += 46 + nlen + xlen + clen;
    }
    return null;
  }
  async function readZipCode(buf){
    const dv = new DataView(buf), u8 = new Uint8Array(buf);
    let eocd = -1;
    for (let i = u8.length - 22; i >= Math.max(0, u8.length - 65557); i--) if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    if (eocd < 0) throw new Error("not a zip file");
    let p = dv.getUint32(eocd + 16, true);
    const count = dv.getUint16(eocd + 10, true), dec = new TextDecoder();
    const entries = [];
    for (let i = 0; i < count; i++) {
      if (dv.getUint32(p, true) !== 0x02014b50) break;
      const method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true);
      const nlen = dv.getUint16(p + 28, true), xlen = dv.getUint16(p + 30, true), clen = dv.getUint16(p + 32, true), off = dv.getUint32(p + 42, true);
      entries.push({ name:dec.decode(u8.subarray(p + 46, p + 46 + nlen)), method, csize, off });
      p += 46 + nlen + xlen + clen;
    }
    const pick = entries.find(e => /\.py$/i.test(e.name)) || entries.find(e => /\.(json|txt)$/i.test(e.name));
    if (!pick) throw new Error("no .py, .json or .txt file inside");
    const lp = pick.off, start = lp + 30 + dv.getUint16(lp + 26, true) + dv.getUint16(lp + 28, true);
    const raw = u8.subarray(start, start + pick.csize);
    if (pick.method === 0) return { name:pick.name, text:dec.decode(raw) };
    if (pick.method === 8 && typeof DecompressionStream !== "undefined") {
      const stream = new Blob([raw]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
      return { name:pick.name, text:await new Response(stream).text() };
    }
    throw new Error("this zip uses a compression this browser can't open");
  }

