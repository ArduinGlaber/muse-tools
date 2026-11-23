#!/usr/bin/env python3
"""Solver PoW DeepSeekHashV1 via WASM (sha3_wasm_bg.7b9ca65ddd.wasm).

Uso: deepseek-pow.py <challenge> <salt> <difficulty> <expire_at>
Imprime el answer (entero).
"""
import struct
import sys

from wasmtime import Config, Engine, Linker, Module, Store

WASM_PATH = "/home/hatch/workspace/openrouter-free/sha3_wasm_bg.7b9ca65ddd.wasm"


def solve(challenge: str, salt: str, difficulty: int, expire_at: int) -> int:
    prefix = f"{salt}_{expire_at}_"
    engine = Engine(Config())
    store = Store(engine)
    linker = Linker(engine)
    linker.define_wasi()
    module = Module.from_file(engine, WASM_PATH)
    instance = linker.instantiate(store, module)
    mem = instance.exports(store)["memory"]
    alloc = instance.exports(store)["__wbindgen_export_0"]
    stack_ptr = instance.exports(store)["__wbindgen_add_to_stack_pointer"]
    solve_fn = instance.exports(store)["wasm_solve"]

    def write(text: str):
        b = text.encode()
        ptr = alloc(store, len(b), 1)
        m = mem.data_ptr(store)
        # wasmtime Memory: usar write()
        mem.write(store, b, ptr)
        return ptr, len(b)

    retptr = stack_ptr(store, -16)
    ch_ptr, ch_len = write(challenge)
    pf_ptr, pf_len = write(prefix)
    solve_fn(store, retptr, ch_ptr, ch_len, pf_ptr, pf_len, float(difficulty))

    raw = mem.read(store, 16, retptr)
    status = struct.unpack("<I", raw[0:4])[0]
    if status == 0:
        raise RuntimeError("sin solucion")
    value_bits = struct.unpack("<Q", raw[8:16])[0]
    answer = int(struct.unpack("<d", struct.pack("<Q", value_bits))[0])
    stack_ptr(store, 16)
    return answer


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Uso: deepseek-pow.py <challenge> <salt> <difficulty> <expire_at>")
        sys.exit(1)
    print(solve(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])))
