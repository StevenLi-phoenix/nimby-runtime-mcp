"""Test a disassembled, allocation-free leaf setter on the observed core thread."""
import hashlib
import json
from pathlib import Path
import frida
from game_version import DEFAULT_EXE, SUPPORTED_SHA256


def run():
    if hashlib.sha256(DEFAULT_EXE.read_bytes()).hexdigest() != SUPPORTED_SHA256:
        raise RuntimeError("Unsupported executable; revalidate function addresses")
    ps=[p for p in frida.get_local_device().enumerate_processes() if p.name.lower()=="nimbyrails.exe"]
    if len(ps)!=1:
        raise RuntimeError("Expected one game process")
    trace=json.loads(Path("work/edit-trace-2.json").read_text(encoding="utf-8"))
    if trace["pid"] != ps[0].pid or trace["exe_sha256"] != SUPPORTED_SHA256:
        raise RuntimeError("Capture a new trace for this process before testing")
    core=next(o for o in trace["observations"] if o.get("caller")=="0x30e12e")
    session=frida.attach(ps[0].pid)
    source=r'''
let result=null;
const main=Process.mainModule;
if(main.base.toString() !== '__BASE__') throw Error('Process restarted; capture a fresh trace');
if(main.path.toLowerCase().replace(/\\/g,'/') !== 'd:/steamlibrary/steamapps/common/nimby rails/nimbyrails.exe')
  throw Error('Unexpected process image');
const setSpeed=new NativeFunction(main.base.add(0x4794c0),'void',['pointer','int']);
function test() {
    if(result!==null) return;
    result={started:true,thread:Process.getCurrentThreadId()};
    const sim=ptr('__SIM__');
    const before=sim.add(0x2118).readS32();
    const originalFlag=sim.add(0x211c).readU8();
    if(before<0 || before>10000) {result.error='Unexpected simulation speed';return;}
    const requested=before===0?1:0;
    try {
      setSpeed(sim,requested);
      result.changed=sim.add(0x2118).readS32();
    } finally {
      setSpeed(sim,before);
      sim.add(0x211c).writeU8(originalFlag);
    }
    result.before=before;
    result.requested=requested;
    result.restored=sim.add(0x2118).readS32();
    result.success=result.changed===requested && result.restored===before;
    result.simulation=sim.toString();
    return result;
}
rpc.exports={async run(){
  if(!Process.enumerateThreads().some(t=>t.id===__THREAD__)) throw Error('Core thread is gone');
  await Process.runOnThread(__THREAD__,test);
  return result;
}};
'''
    source=source.replace('__SIM__',core['args'][3]).replace('__THREAD__',str(core['thread'])).replace('__BASE__',trace['base'])
    script=session.create_script(source)
    try:
        script.load()
        result=script.exports_sync.run()
        if not result or not result.get("success"):
            raise RuntimeError(f"Native test failed or core boundary not observed: {result}")
        Path("work").mkdir(exist_ok=True)
        Path("work/native-call.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        print(json.dumps(result,indent=2))
    finally:
        try:
            script.unload()
        finally:
            session.detach()

if __name__=="__main__":
    run()
