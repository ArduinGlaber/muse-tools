#!/usr/bin/env node
// Solver PoW DeepSeekHashV1 via WASM en Node.js
// Uso: node deepseek-pow.mjs <challenge> <salt> <difficulty> <expire_at>
import { readFileSync } from 'fs';

const wasmBuffer = readFileSync('/home/hatch/workspace/openrouter-free/sha3_wasm_bg.7b9ca65ddd.wasm');
const module = await WebAssembly.compile(wasmBuffer);

// WASI minimalista
const wasiImports = {
  wasi_snapshot_preview1: {
    fd_write: () => 0,
    fd_close: () => 0,
    fd_seek: () => 0,
    environ_get: () => 0,
    environ_sizes_get: () => 0,
    proc_exit: () => {},
    clock_time_get: () => 0,
    random_get: () => 0,
  }
};

const instance = await WebAssembly.instantiate(module, wasiImports);
const ex = instance.exports;
const mem = ex.memory;

function writeStr(s) {
  const b = Buffer.from(s, 'utf8');
  const ptr = ex.__wbindgen_export_0(b.length, 1);
  Buffer.from(mem.buffer, ptr, b.length).set(b);
  return [ptr, b.length];
}

const [challenge, salt, difficulty, expire_at] = process.argv.slice(2);
const prefix = `${salt}_${expire_at}_`;

const retptr = ex.__wbindgen_add_to_stack_pointer(-16);
const [chPtr, chLen] = writeStr(challenge);
const [pfPtr, pfLen] = writeStr(prefix);

ex.wasm_solve(retptr, chPtr, chLen, pfPtr, pfLen, parseFloat(difficulty));

const view = new DataView(mem.buffer, retptr, 16);
const status = view.getUint32(0, true);
if (status === 0) {
  console.error("sin solucion");
  process.exit(1);
}
const bits = view.getBigUint64(8, true);
const buf = Buffer.alloc(8);
buf.writeBigUInt64LE(bits);
const answer = Math.trunc(buf.readDoubleLE(0));
console.log(answer);
ex.__wbindgen_add_to_stack_pointer(16);
