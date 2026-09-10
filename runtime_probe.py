"""Attach temporarily, inspect modules and observe command calls; never replay them."""
import argparse
import json
import time
from pathlib import Path
import frida
from inspect_binary import DEFAULT_EXE, inspect

def probe(seconds=10, output=None):
    profile = inspect(DEFAULT_EXE)
    if profile['sha256'] != 'fff49ac21720abfc824c2b4f68b862727630eb0db71cfe1f9ea8f685d0db10ae':
        raise RuntimeError('Unsupported executable; validate virtual method layout first')
    processes = [p for p in frida.get_local_device().enumerate_processes()
                 if p.name.lower() == "nimbyrails.exe"]
    if len(processes) != 1:
        raise RuntimeError(f"Expected one NIMBY Rails process, found {len(processes)}")
    commands = [{"name": c["name"], "rva": v["functions"][1], "vtable": v["rva"]}
                for c in profile["commands"] for v in c["vtables"]
                if v["offset"] == 0 and len(v["functions"]) == 6]
    source = "const candidates = " + json.dumps(commands) + ";\n" + r'''
const main = Process.mainModule;
if(main.path.toLowerCase().replace(/\\/g,'/') !== 'd:/steamlibrary/steamapps/common/nimby rails/nimbyrails.exe')
  throw Error('Unexpected process image');
const observations = [];
const counts = {};
const hooks = [];
const seen = new Set();
for (const cmd of candidates) {
  if (seen.has(cmd.rva)) continue;
  seen.add(cmd.rva);
  hooks.push(Interceptor.attach(main.base.add(cmd.rva), {
    onEnter(args) {
      try {
        if (!args[0].readPointer().equals(main.base.add(cmd.vtable))) return;
        counts[cmd.name] = (counts[cmd.name] || 0) + 1;
        if (counts[cmd.name] > 2 || observations.length >= 200) return;
        const vectors=[];
        if(cmd.name.includes('EditStop@')) for(let off=0x20;off<=0xf8;off+=0x18) {
          const begin=args[0].add(off).readPointer(),end=args[0].add(off+8).readPointer();
          const length=end.sub(begin).toUInt32();
          if(!begin.isNull()&&length>0&&length<=4096)vectors.push({offset:off,length,hex:hexdump(begin,{length,header:false,ansi:false})});
        }
        if(cmd.name.includes('TrainsPurchase@')) for(const off of [0x78,0x80,0x88,0x98,0xc0,0xe0,0x128,0x160,0x198]) {
          const begin=args[0].add(off).readPointer(),end=args[0].add(off+8).readPointer();
          const length=end.sub(begin).toUInt32();
          if(!begin.isNull()&&length>0&&length<=4096&&Process.findRangeByAddress(begin))vectors.push({offset:off,length,hex:hexdump(begin,{length,header:false,ansi:false})});
        }
        observations.push({name:cmd.name, thread:Process.getCurrentThreadId(),
          vectors,
          objectHex:hexdump(args[0],{length:cmd.name.includes('TrainsPurchase@')?464:cmd.name.includes('CreateTrack@')?200:cmd.name.includes('Build@tn@')?144:cmd.name.includes('CreatePlatform@')?120:32,header:false,ansi:false}),
          args:[0,1,2,3].map(i=>args[i].toString()),
          caller:this.returnAddress.sub(main.base).toString(),
          stack:Thread.backtrace(this.context,Backtracer.ACCURATE).slice(0,10)
            .map(p=>({address:p.toString(),module:Process.findModuleByAddress(p)?.name,
                      rva:Process.findModuleByAddress(p) ? p.sub(Process.findModuleByAddress(p).base).toString():null}))});
      } catch (e) { observations.push({error:String(e),name:cmd.name}); }
    }
  }));
}
rpc.exports = {
  status() {
    const sdl=Process.getModuleByName('SDL3.dll');
    const getVersion=new NativeFunction(sdl.getExportByName('SDL_GetVersion'),'int',[]);
    return {pid:Process.id,arch:Process.arch,path:main.path,base:main.base.toString(),
      sdlVersion:getVersion(),hookCount:hooks.length,counts,observations};
  },
  stop() { for(const hook of hooks) hook.detach(); }
};
'''
    session = frida.attach(processes[0].pid)
    script = None
    try:
        script = session.create_script(source)
        script.load()
        initial = script.exports_sync.status()
        if Path(initial["path"]).resolve() != DEFAULT_EXE.resolve():
            raise RuntimeError("Unexpected process image")
        print(json.dumps({"attached": initial["pid"], "hooks": initial["hookCount"],
                          "sdl_version": initial["sdlVersion"]}), flush=True)
        time.sleep(seconds)
        result = script.exports_sync.status()
        result["exe_sha256"] = profile["sha256"]
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return result
    finally:
        try:
            if script:
                script.exports_sync.stop()
                script.unload()
        finally:
            session.detach()

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--seconds",type=float,default=10)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if not 0 <= args.seconds <= 300:
        parser.error("seconds must be between 0 and 300")
    probe(args.seconds,args.output)
