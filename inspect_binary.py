"""Locate MSVC command RTTI and vtables without executing game functions."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
import pefile

from game_version import DEFAULT_EXE

def inspect(path: Path):
    data = path.read_bytes()
    pe = pefile.PE(data=data)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    executable = [(s.VirtualAddress, s.VirtualAddress + s.Misc_VirtualSize)
                  for s in pe.sections if s.Characteristics & 0x20000000]
    found = []
    for m in re.finditer(rb"\.\?AU[^\x00]{1,200}@cmd@model@nimby@@\x00", image):
        td = m.start() - 16
        name = m.group()[:-1].decode()
        tables = []
        for ref in re.finditer(re.escape(struct.pack("<I", td)), image):
            col = ref.start() - 12
            if col < 0 or col + 24 > len(image):
                continue
            sig, off, ctor, typ, hierarchy, self_rva = struct.unpack_from("<6I", image, col)
            if sig != 1 or typ != td or self_rva != col:
                continue
            for vp in re.finditer(re.escape(struct.pack("<Q", base + col)), image):
                vt = vp.start() + 8
                funcs = []
                for i in range(32):
                    if vt + i * 8 + 8 > len(image):
                        break
                    addr = struct.unpack_from("<Q", image, vt + i * 8)[0] - base
                    if not any(a <= addr < b for a, b in executable):
                        break
                    funcs.append(addr)
                if funcs:
                    tables.append({"rva": vt, "offset": off, "functions": funcs})
        found.append({"name": name, "type_descriptor_rva": td, "vtables": tables})
    return {"exe": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(),
            "image_size": len(image), "commands": found}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = json.dumps(inspect(args.exe), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result)
