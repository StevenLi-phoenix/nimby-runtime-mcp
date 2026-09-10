"""Validate native command ownership at the core's drained command batch."""
import hashlib
import json
import time
from pathlib import Path
import frida
from inspect_binary import DEFAULT_EXE
from test_runtime_call import SUPPORTED_SHA256

SOURCE = r'''
const main=Process.mainModule;
const factory=new NativeFunction(main.base.add(0x3092a0),'pointer',['pointer']);
const append=new NativeFunction(main.base.add(0x34af80),'void',['pointer','pointer']);
const holder=Memory.alloc(8);
let phase=0, result={events:[]}, expectedOwner=null, original=null;
function enqueue(output,value) {
  const vector=output.add(0x170);
  const begin=vector.readPointer(),end=vector.add(8).readPointer(),cap=vector.add(16).readPointer();
  if(end.compare(begin)<0 || cap.compare(end)<0 || end.sub(begin).toUInt32()>80000)
    throw Error('Invalid command batch');
  holder.writePointer(ptr(0));factory(holder);
  const command=holder.readPointer();
  if(!command.readPointer().equals(main.base.add(0xa6dc28))) throw Error('Wrong factory type');
  command.add(0x24).writeS32(value);
  append(vector,holder);
  if(!holder.readPointer().isNull()) throw Error('Ownership was not transferred');
  result.events.push({action:'enqueue',value,command:command.toString()});
}
const hook=Interceptor.attach(main.base.add(0x347520),{
  onEnter(args){this.owner=args[0];this.output=args[1];},
  onLeave(){
    if(phase>=3)return;
    try {
      const owner=this.owner,sim=owner.add(0x140).readPointer();
      if(sim.isNull())return;
      if(expectedOwner!==null&&!owner.equals(expectedOwner))throw Error('World changed');
      const speed=sim.add(0x2118).readS32();
      if(phase===0){
        if(speed<0||speed>10000)throw Error('Invalid speed');
        expectedOwner=owner;original=speed;
        result.thread=Process.getCurrentThreadId();result.before=speed;
        enqueue(this.output,speed===0?1:0);phase=1;
      } else if(phase===1){
        result.changed=speed;
        enqueue(this.output,original);phase=2;
      } else {
        result.restored=speed;
        result.success=result.changed===(original===0?1:0)&&speed===original;
        phase=3;send(result);
      }
    }catch(e){result.error=String(e);phase=3;send(result);}
  }
});
rpc.exports={status(){return {...result,phase};}};
'''

def run():
    if hashlib.sha256(DEFAULT_EXE.read_bytes()).hexdigest()!=SUPPORTED_SHA256:
        raise RuntimeError('Unsupported game executable')
    ps=[p for p in frida.get_local_device().enumerate_processes() if p.name.lower()=='nimbyrails.exe']
    if len(ps)!=1: raise RuntimeError('Expected one game process')
    session=frida.attach(ps[0].pid)
    script=session.create_script(SOURCE)
    script.on('message',lambda m,d:print(json.dumps(m),flush=True))
    try:
        script.load()
        for _ in range(50):
            time.sleep(.1)
            result=script.exports_sync.status()
            if result['phase']==3: break
        Path('work/queue-test.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2),flush=True)
        if not result.get('success'): raise RuntimeError('Queue test did not pass')
    finally:
        script.unload()
        session.detach()

if __name__=='__main__': run()
