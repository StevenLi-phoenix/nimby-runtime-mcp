// Version-specific adapter. Every operation runs at a fresh core queue boundary.
const main = Process.mainModule;
if (main.path.toLowerCase().replace(/\\/g, '/') !==
    'd:/steamlibrary/steamapps/common/nimby rails/nimbyrails.exe') throw Error('Unexpected image');
const native = (rva, result, args) => new NativeFunction(main.base.add(rva), result, args);
const speedFactory = native(0x3092a0, 'pointer', ['pointer']);
const trackFactory = native(0x31bd20, 'pointer', ['pointer']);
const platformFactory = native(0x31bde0, 'pointer', ['pointer']);
const buildFactory = native(0x31cab0, 'pointer', ['pointer']);
const stationFactory = native(0x2ff5e0, 'pointer', ['pointer']);
const lineFactory = native(0x301630, 'pointer', ['pointer']);
const stopFactory = native(0x31cf30, 'pointer', ['pointer']);
const purchaseFactory = native(0x31d0e0, 'pointer', ['pointer']);
const metaFactory = native(0x31d040, 'pointer', ['pointer']);
const serviceFactory = native(0x3032e0, 'pointer', ['pointer']);
const editFactory = native(0x2f6e90, 'pointer', ['pointer']);
const trainEditFactory = native(0x303fb0, 'pointer', ['pointer']);
const rebpFactory = native(0x319a10, 'pointer', ['pointer']);
const walkLinkFactory = native(0x2ffac0, 'pointer', ['pointer']);
const deleteFactory = native(0x3198e0, 'pointer', ['pointer']);
const findTape = native(0x33f630, 'pointer', ['pointer','uint64']);
const findBuilding = native(0x33f860, 'pointer', ['pointer','uint64']);
const copyBuilding = native(0x2fbb10, 'pointer', ['pointer','pointer']);
const constructIdSet = native(0x3c67c0, 'pointer', ['pointer','pointer','pointer']);
const findTrain = native(0x33f780, 'pointer', ['pointer','uint64']);
const allocate = native(0x983da8, 'pointer', ['uint64']);
const findLine = native(0x33f7f0, 'pointer', ['pointer','uint64']);
const findStation = native(0x32c3b0, 'pointer', ['pointer','uint64']);
const assignString = native(0x30630, 'pointer', ['pointer','pointer','uint64']);
const append = native(0x34af80, 'void', ['pointer', 'pointer']);
const findNode = native(0x32c420, 'pointer', ['pointer', 'uint64']);
const holder = Memory.alloc(8);
let pending = [], active = null, executing = null, owner = null, worldDb = null, worldSim = null, stopping = false;
function readString(p) {
  const size=p.add(16).readU64().toNumber();
  if(size>4096)throw Error('Invalid string size');
  return (p.add(24).readU64().toNumber()>15?p.readPointer():p).readUtf8String(size);
}
function writeString(p,text) {assignString(p,Memory.allocUtf8String(text),uint64(unescape(encodeURIComponent(text)).length));}
function train(db,id) {
  const p=findTrain(db.add(0x200),uint64(id));if(p.isNull())return null;
  return {id:p.readU64().toString(),name:readString(p.add(0x10)),serial:readString(p.add(0x30)),
    model_id:p.add(0x50).readU64().toString(),cars:p.add(0xc8).readPointer().sub(p.add(0xc0).readPointer()).toUInt32()/32,
    max_speed_kmh:p.add(0xdc).readFloat()*3.6,length_metres:p.add(0xf8).readFloat(),capacity:p.add(0x100).readU32()};
}
function trains(db) {
  const table=db.add(0x200),begin=table.add(0x18).readPointer(),end=table.add(0x20).readPointer();
  const pages=end.sub(begin).toUInt32()/8,slots=table.add(8).readU32();
  if(!Number.isInteger(pages)||pages*slots>100000)throw Error('Invalid train table');
  const result=[];
  for(let i=0;i<pages;i++) {
    const page=begin.add(i*8).readPointer();if(page.isNull())continue;
    for(let j=0;j<slots;j++) {
      const p=page.add(j*0x178),id=p.readU64();
      if(id.shr(48).toNumber()!==5||!findTrain(table,id).equals(p))continue;
      result.push(train(db,id.toString()));
    }
  }
  return result;
}
function line(db,id) {
  const p=findLine(db.add(0x180),uint64(id));if(p.isNull())return null;
  const begin=p.add(0x118).readPointer(),end=p.add(0x120).readPointer();
  const count=end.sub(begin).toUInt32()/0x158;
  if(!Number.isInteger(count)||count>1000)throw Error('Invalid stop vector');
  const stops=[];
  for(let i=0;i<count;i++) {const s=begin.add(i*0x158);stops.push({index:i,node_id:s.add(0x78).readU64().toString(),position:s.add(0x80).readDouble(),stop_id:s.add(0x108).readU64().toString()});}
  return {id:p.readU64().toString(),name:readString(p.add(0x58)),code:readString(p.add(0x78)),color:p.add(0xb8).readU32(),base_fare:p.add(0x1d0).readDouble(),fare_per_km:p.add(0x1d8).readDouble(),service:p.add(0xfc).readS32(),reference_train:p.add(0x1f8).readU64().toString(),stop_count:count,stops};
}
function station(db,id) {
  const p=findStation(db.add(0x80),uint64(id));
  if(p.isNull())return null;
  const s=p.add(0x20),length=s.add(16).readU64().toNumber();
  if(length>4096)throw Error('Invalid station name');
  return {id:p.readU64().toString(),name:(s.add(24).readU64().toNumber()>15?s.readPointer():s).readUtf8String(length),
    x:p.add(0x10).readDouble(),y:p.add(0x18).readDouble(),walk_links:readIdSet(p.add(0x288)),display_settings:Object.fromEntries([0x44,0x398,0x39c,0x3a0,0x3a8].map(o=>[o.toString(16),p.add(o).readU32()])),display_flag:p.add(0x3a4).readU8()};
}
function readIdSet(p) {
  const begin=p.readPointer(),end=p.add(8).readPointer();
  const count=end.sub(begin).toUInt32()/8;
  if(!Number.isInteger(count)||count>1000)throw Error('Invalid station walk-link vector');
  return Array.from({length:count},(_,i)=>begin.add(i*8).readU64().toString());
}

function node(db, id) {
  const p = findNode(db.add(0x428).readPointer(), uint64(id));
  if (p.isNull()) return null;
  return {id: p.readU64().toString(), previous: p.add(8).readU64().toString(),
    next: p.add(16).readU64().toString(), track_type: p.add(0x24).readU32(),
    depth: p.add(0x28).readS32(), x: p.add(0x30).readDouble(), y: p.add(0x38).readDouble(),
    station_id:p.add(0xd0).readU64().toString(),blueprint:p.add(0x20).readU8()!==0,
    buildings:readIdSet(p.add(0x440)).map(id=>{
      const b=findBuilding(db.add(0x428).readPointer().add(0x100),uint64(id));
      if(b.isNull())throw Error('Missing attached building');
      return {id,node_id:b.add(0xa8).readU64().toString(),type:b.add(8).readS32(),depth:b.add(0x1c).readS32(),blueprint:b.add(0x24).readU8()!==0,x:b.add(0x28).readDouble(),y:b.add(0x30).readDouble(),rotation:b.add(0x38).readDouble(),width:b.add(0x48).readFloat(),height:b.add(0x4c).readFloat()};
    }),building_tapes:readIdSet(p.add(0x140)).map(id=>{
      const t=findTape(db.add(0x428).readPointer().add(0x380),uint64(id));
      if(t.isNull())throw Error('Missing attached building tape');
      return {id,node_id:t.add(0x40).readU64().toString()};
    })};
}
function network(db, ids) {
  const seen=new Set(),queue=[...ids],nodes=[];
  for(let index=0;index<queue.length;index++) {
    const id=queue[index];if(id==='0'||seen.has(id))continue;
    seen.add(id);if(seen.size>5000)throw Error('Connected network exceeds 5000 nodes');
    const n=node(db,id);if(!n)continue;
    const p=findNode(db.add(0x428).readPointer(),uint64(id));
    const begin=p.add(0x408).readPointer(),end=p.add(0x410).readPointer();
    const count=end.sub(begin).toUInt32()/8;
    if(!Number.isInteger(count)||count>1000)throw Error('Invalid branch vector');
    n.branch_parent=p.add(0x3f0).readU64().toString();n.branches=[];
    n.branch_position=p.add(0x3f8).readDouble();
    const curveBegin=p.add(0x1b0).readPointer(),curveEnd=p.add(0x1b8).readPointer();
    const curveCount=curveEnd.sub(curveBegin).toUInt32()/16;
    if(!Number.isInteger(curveCount)||curveCount>10000)throw Error('Invalid track curve');
    n.curve=[];
    for(let i=0;i<curveCount;i++)n.curve.push([curveBegin.add(i*16).readDouble(),curveBegin.add(i*16+8).readDouble()]);
    for(let i=0;i<count;i++)n.branches.push(begin.add(i*8).readU64().toString());
    nodes.push(n);queue.push(n.previous,n.next,n.branch_parent,...n.branches);
  }
  return {nodes,count:nodes.length};
}
function nearbyNodes(db,args) {
  const table=db.add(0x428).readPointer(),begin=table.add(0x18).readPointer(),end=table.add(0x20).readPointer();
  const pages=end.sub(begin).toUInt32()/8,slots=table.add(8).readU32(),nodes=[];
  if(!Number.isInteger(pages)||pages*slots>1000000)throw Error('Invalid track table');
  for(let i=0;i<pages;i++) {
    const page=begin.add(i*8).readPointer();if(page.isNull())continue;
    for(let k=0;k<slots;k++) {
      const p=page.add(k*0x4e8),id=p.readU64();
      if(id.shr(48).toNumber()!==1||!findNode(table,id).equals(p))continue;
      if(Math.hypot(p.add(0x30).readDouble()-args.x,p.add(0x38).readDouble()-args.y)>args.radius)continue;
      nodes.push({...node(db,id.toString()),group_id:p.add(0x18).readU64().toString(),structure_parent:p.add(0x478).readU64().toString(),structure_children:readIdSet(p.add(0x498))});
    }
  }
  return {nodes,count:nodes.length};
}
function queueBuildingDepths(db,j,depth) {
  j.expectedBuildings=[];
  for(const id of j.args.ids) {
    const n=node(db,id);if(!n)throw Error('Node not found');
    for(const b of n.buildings)j.expectedBuildings.push({...b,depth:depth??n.depth});
  }
  if(!j.expectedBuildings.length)return;
  const size=j.expectedBuildings.length*0xe8,entries=allocate(uint64(size));
  entries.writeByteArray(new Uint8Array(size));
  j.expectedBuildings.forEach((b,i)=>{
    const p=findBuilding(db.add(0x428).readPointer().add(0x100),uint64(b.id));
    copyBuilding(entries.add(i*0xe8),p);
    entries.add(i*0xe8+0x1c).writeS32(b.depth);
  });
  j.command.add(0x98).writePointer(entries);j.command.add(0xa0).writePointer(entries.add(size));j.command.add(0xa8).writePointer(entries.add(size));
}
function buildingsMatch(j,nodes) {
  const actual=nodes.flatMap(n=>n?n.buildings:[]);
  return j.expectedBuildings.every(b=>actual.some(a=>JSON.stringify(a)===JSON.stringify(b)));
}
function finish(job, value, error) {
  if(job.settled)return;
  job.settled=true;
  clearTimeout(job.timer);
  if (error) job.reject(Error(error)); else job.resolve(value);
}
function enqueue(output, command) {
  const v = output.add(0x170), b = v.readPointer(), e = v.add(8).readPointer(), c = v.add(16).readPointer();
  if (e.compare(b)<0 || c.compare(e)<0 || e.sub(b).toUInt32()>80000) throw Error('Invalid command vector');
  holder.writePointer(command); append(v, holder);
  if (!holder.readPointer().isNull()) throw Error('Native ownership transfer failed');
}
function endpoint(p, point) {
  if(point.edge_id){p.writeU64(uint64(point.edge_id));p.add(8).writeDouble(point.position);p.add(0x10).writeU32(3);p.add(0x14).writeS32(point.depth??-1);p.add(0x30).writeU8(2);return;}
  if(point.id){p.writeU64(uint64(point.id));p.add(0x30).writeU8(1);return;}
  p.writeDouble(point.x); p.add(8).writeDouble(point.y);
  p.add(0x10).writeU32(3); p.add(0x14).writeS32(point.depth??-1);
  p.add(0x30).writeU8(0); // coordinate variant; inactive optional fields stay zero
}
Interceptor.attach(main.base.add(0x2facf0), {
  onEnter(args) {this.ours = active && args[0].equals(active.command); if(this.ours) executing=active;},
  onLeave() {if(this.ours) executing=null;}
});
Interceptor.attach(main.base.add(0x39d8c0), {
  onEnter(args) {this.job=executing;this.out=args[1];},
  onLeave() {if(this.job) for(let i=0;i<2;i++) this.job.ids.push(this.out.add(i*8).readU64().toString());}
});
Interceptor.attach(main.base.add(0x2fc790), {
  onEnter(args){this.ours=active&&args[0].equals(active.command);if(this.ours)executing=active;},
  onLeave(){if(this.ours)executing=null;}
});
for(const rva of [0x39d690,0x39d4e0]) Interceptor.attach(main.base.add(rva), {
  onEnter(){this.job=executing;},
  onLeave(ret){if(this.job)this.job.ids.push(ret.toString());}
});
for(const rva of [0x2ff410,0x301670,0x304b50]) Interceptor.attach(main.base.add(rva), {
  onEnter(args){this.ours=active&&args[0].equals(active.command);if(this.ours)executing=active;},
  onLeave(){if(this.ours)executing=null;}
});
Interceptor.attach(main.base.add(0x399d00), {
  onEnter(){this.job=executing&&executing.kind==='build'?executing:null;},
  onLeave(ret){if(this.job)this.job.code=ret.toInt32();}
});
Interceptor.attach(main.base.add(0x36d8d0), {
  onEnter(){this.job=executing&&executing.kind==='new_line'?executing:null;},
  onLeave(ret){if(this.job)this.job.lineId=uint64(ret.toString()).toString();}
});
Interceptor.attach(main.base.add(0x3f6c20), {
  onEnter(){this.job=executing&&executing.kind==='purchase'?executing:null;},
  onLeave(ret){if(this.job&&!ret.isNull())this.job.trainIds.push(ret.readU64().toString());}
});
Interceptor.attach(main.base.add(0x347520), {
  onEnter(args) {this.owner=args[0];this.output=args[1];},
  onLeave() {
    let currentJob=null;
    try {
      const current=this.owner, db=current.readPointer(), sim=current.add(0x140).readPointer();
      if(db.isNull()||sim.isNull())return;
      if(owner!==null&&(!owner.equals(current)||!worldDb.equals(db)||!worldSim.equals(sim))) {
        if(active){finish(active,null,'World changed; outcome unknown');active=null;}
        for(const j of pending)finish(j,null,'World changed');pending=[];
      }
      owner=current;worldDb=db;worldSim=sim;
      const state={pid:Process.id,thread:Process.getCurrentThreadId(),speed:sim.add(0x2118).readS32(),cash:sim.readDouble(),simulation_time:sim.add(0x2108).readU64().toNumber()};
      if(active) {
        const j=active;active=null;currentJob=j;
        if(j.kind==='set_speed') finish(j,{...state,requested:j.args.speed,verified:state.speed===j.args.speed});
        else if(j.kind==='edit_kind'||j.kind==='rebp') {
          const nodes=j.args.ids.map(id=>node(db,id));
          finish(j,{nodes,verified:nodes.every(n=>n&&(j.kind==='rebp'?n.blueprint:n.track_type===j.args.track_type))});
        }
        else if(j.kind==='delete_branches') {
          const remaining=j.args.ids.filter(id=>node(db,id)!==null);
          const parents=j.parents.map(n=>node(db,n.id));
          finish(j,{remaining,parents,verified:remaining.length===0&&parents.every((n,i)=>n&&JSON.stringify(n)===JSON.stringify(j.parents[i]))});
        }
        else if(j.kind==='edit_depth'||j.kind==='sync_building_depth') {
          const nodes=j.args.ids.map(id=>node(db,id));
          finish(j,{nodes,verified:nodes.every(n=>n&&(j.kind==='sync_building_depth'||n.depth===j.args.depth))&&buildingsMatch(j,nodes)});
        }
        else if(j.kind==='new_line') {
          const l=j.lineId?line(db,j.lineId):null;finish(j,{line:l,verified:l!==null});
        }
        else if(j.kind==='add_stop') {
          const l=line(db,j.args.line_id);finish(j,{line:l,verified:l!==null&&l.stop_count===j.before+1&&l.stops[j.before].node_id===j.args.node_id});
        }
        else if(j.kind==='purchase') {
          const trains=j.trainIds.map(id=>train(db,id));finish(j,{trains,verified:trains.length===j.args.count&&trains.every(t=>t&&t.cars===6)});
        }
        else if(j.kind==='line_meta'||j.kind==='line_service') {
          const l=line(db,j.args.id);
          const matches=l!==null&&(j.kind==='line_meta'
            ?l.name===j.args.name&&l.code===j.args.code&&(j.args.color==null||l.color===j.args.color)&&(j.args.base_fare==null||l.base_fare===j.args.base_fare)&&(j.args.fare_per_km==null||l.fare_per_km===j.args.fare_per_km)
            :l.service===j.args.service&&(!j.args.reference_train||l.reference_train===j.args.reference_train));
          finish(j,{line:l,verified:matches});
        }
        else if(j.kind==='rename_train') {
          const t=train(db,j.args.id);finish(j,{train:t,verified:t!==null&&t.name===j.args.name&&t.serial===j.args.serial});
        }
        else if(j.kind==='walk_link') {
          const a=station(db,j.args.a),b=station(db,j.args.b);
          finish(j,{stations:[a,b],verified:!!a&&!!b&&a.walk_links.includes(j.args.b)&&b.walk_links.includes(j.args.a)});
        }
        else if(j.kind==='station_label') {
          const s=station(db,j.args.id);
          const expected={...j.before.display_settings,'3a8':j.args.label};
          finish(j,{station:s,verified:s!==null&&s.name===j.before.name&&s.display_flag===j.before.display_flag&&JSON.stringify(s.display_settings)===JSON.stringify(expected)&&JSON.stringify(s.walk_links)===JSON.stringify(j.before.walk_links)});
        }
        else if(j.kind==='rename_station') {
          const s=station(db,j.args.id);finish(j,{station:s,verified:s!==null&&s.name===j.args.name});
        } else if(j.kind==='build') {
          const nodes=j.args.ids.map(id=>node(db,id));
          finish(j,{code:j.code,nodes,verified:j.code===0&&nodes.every(n=>n!==null&&!n.blueprint)});
        }
        else {
          const ids=[...new Set(j.ids.map(x=>uint64(x).toString()))].filter(x=>x!=='0');
          const nodes=ids.map(id=>node(db,id));
          finish(j,{...state,nodes,verified:nodes.length>=2&&nodes.every(n=>n!==null)});
        }
      }
      currentJob=null;
      if(!pending.length||stopping)return;
      const j=pending.shift();currentJob=j;
      if(j.kind==='status') {finish(j,state);return;}
      if(j.kind==='get_node') {finish(j,node(db,j.args.id));return;}
      if(j.kind==='get_network') {finish(j,network(db,j.args.ids));return;}
      if(j.kind==='nearby_nodes') {finish(j,nearbyNodes(db,j.args));return;}
      if(j.kind==='get_station') {finish(j,station(db,j.args.id));return;}
      if(j.kind==='get_line') {finish(j,line(db,j.args.id));return;}
      if(j.kind==='get_train') {finish(j,train(db,j.args.id));return;}
      if(j.kind==='get_trains') {finish(j,{trains:trains(db)});return;}
      holder.writePointer(ptr(0));
      if(j.kind==='set_speed') {
        speedFactory(holder);j.command=holder.readPointer();
        j.command.add(0x24).writeS32(j.args.speed);
      } else if(j.kind==='walk_link') {
        const a=station(db,j.args.a),b=station(db,j.args.b);
        if(!a||!b||a.id===b.id)throw Error('Expected two distinct stations');
        if(a.walk_links.includes(b.id)&&b.walk_links.includes(a.id)){finish(j,{stations:[a,b],verified:true});return;}
        walkLinkFactory(holder);j.command=holder.readPointer();
        j.command.add(0x20).writeU64(uint64(a.id));j.command.add(0x28).writeU64(uint64(b.id));
        j.command.add(0x30).writeS32(0); // native add; factory default 1 removes the link
      } else if(j.kind==='rebp') {
        if(j.args.ids.some(id=>node(db,id)===null))throw Error('Node not found');
        rebpFactory(holder);j.command=holder.readPointer();
        j.command.add(0x80).writeS64(-1); // preserve the existing node's group/layer field
        const ids=Memory.alloc(j.args.ids.length*8);
        j.args.ids.forEach((id,i)=>ids.add(i*8).writeU64(uint64(id)));
        constructIdSet(j.command.add(0x20),ids,ids.add(j.args.ids.length*8));
      } else if(j.kind==='edit_kind') {
        if(j.args.ids.some(id=>{const n=node(db,id);return !n||!n.blueprint;}))throw Error('Expected blueprint nodes; use native ReBP first');
        editFactory(holder);j.command=holder.readPointer();
        const size=j.args.ids.length*16,entries=allocate(uint64(size));
        entries.writeByteArray(new Uint8Array(size));
        j.args.ids.forEach((id,i)=>{entries.add(i*16).writeU64(uint64(id));entries.add(i*16+8).writeU32(j.args.track_type);});
        j.command.add(0x188).writePointer(entries);j.command.add(0x190).writePointer(entries.add(size));j.command.add(0x198).writePointer(entries.add(size));
      } else if(j.kind==='delete_branches') {
        const parents=new Set();
        for(const id of j.args.ids) {
          const n=node(db,id),p=findNode(db.add(0x428).readPointer(),uint64(id));
          if(!n||n.station_id!=='0'||p.add(0x3f0).readU64().toString()==='0')throw Error('Only branch endpoints may be removed');
          if([n.previous,n.next].filter(x=>x!=='0').some(x=>!j.args.ids.includes(x)))throw Error('Include the complete branch pair');
          parents.add(p.add(0x3f0).readU64().toString());
        }
        j.parents=[...parents].map(id=>node(db,id));
        deleteFactory(holder);j.command=holder.readPointer();
        const ids=Memory.alloc(j.args.ids.length*8);
        j.args.ids.forEach((id,i)=>ids.add(i*8).writeU64(uint64(id)));
        constructIdSet(j.command.add(0x20),ids,ids.add(j.args.ids.length*8));
      } else if(j.kind==='sync_building_depth') {
        editFactory(holder);j.command=holder.readPointer();queueBuildingDepths(db,j,null);
      } else if(j.kind==='edit_depth') {
        if(j.args.ids.some(id=>node(db,id)===null))throw Error('Node not found');
        editFactory(holder);j.command=holder.readPointer();
        const size=j.args.ids.length*16,entries=allocate(uint64(size));
        entries.writeByteArray(new Uint8Array(size));
        j.args.ids.forEach((id,i)=>{entries.add(i*16).writeU64(uint64(id));entries.add(i*16+8).writeS32(j.args.depth);});
        j.command.add(0x170).writePointer(entries);
        j.command.add(0x178).writePointer(entries.add(size));
        j.command.add(0x180).writePointer(entries.add(size));
        queueBuildingDepths(db,j,j.args.depth);
      } else if(j.kind==='create_track') {
        for(const point of [j.args.start,j.args.end]) {
          if(point.id||point.edge_id) {
            const n=node(db,point.id||point.edge_id);
            if(!n)throw Error('Track node no longer exists in this world');
            if(n.track_type!==3)throw Error('Metro endpoints must use Medium; convert existing nodes first');
            if(point.id&&n.previous!=='0'&&n.next!=='0')throw Error('Expected free endpoint');
            if(point.edge_id&&n.previous==='0')throw Error('Expected a node with an existing previous edge');
          }
        }
        if(j.args.start.id&&j.args.start.id===j.args.end.id)throw Error('Cannot connect a node to itself');
        if(j.args.start.id&&!j.args.end.id&&!j.args.end.edge_id) {
          const n=node(db,j.args.start.id),distance=Math.hypot(n.x-j.args.end.x,n.y-j.args.end.y);
          if(distance<1||distance>10000)throw Error('Extension distance out of range in current world');
        }
        trackFactory(holder);j.command=holder.readPointer();
        if(!j.command.readPointer().equals(main.base.add(0xa6d5d0)))throw Error('Invalid track factory');
        endpoint(j.command.add(0x20),j.args.start);endpoint(j.command.add(0x70),j.args.end);
        j.command.add(0xa8).writeU8(j.args.dual?1:0);
        j.command.add(0xba).writeU8(1);j.command.add(0xbc).writeFloat(5);
        j.ids=[j.args.start.id,j.args.end.id].filter(Boolean);
      } else if(j.kind==='create_platform') {
        platformFactory(holder);j.command=holder.readPointer();j.ids=[];
        j.command.add(0x20).writeDouble(j.args.start.x);j.command.add(0x28).writeDouble(j.args.start.y);
        j.command.add(0x30).writeDouble(j.args.end.x);j.command.add(0x38).writeDouble(j.args.end.y);
        j.command.add(0x50).writeU32(3);j.command.add(0x54).writeS32(j.args.depth??-1);
        j.command.add(0x5b).writeU8(1);j.command.add(0x5c).writeFloat(5);
      } else if(j.kind==='build') {
        if(j.args.ids.some(id=>node(db,id)===null))throw Error('Verification node not found; construction not submitted');
        buildFactory(holder);j.command=holder.readPointer();
      } else if(j.kind==='new_line') {
        lineFactory(holder);j.command=holder.readPointer();
      } else if(j.kind==='line_meta') {
        const p=findLine(db.add(0x180),uint64(j.args.id));
        if(p.isNull()){finish(j,null,'Line not found');return;}
        metaFactory(holder);j.command=holder.readPointer();const c=j.command;
        c.add(0x20).writeU64(uint64(j.args.id));writeString(c.add(0x28),j.args.name);writeString(c.add(0x48),j.args.code);writeString(c.add(0x68),readString(p.add(0x98)));
        c.add(0x88).writeDouble(j.args.base_fare??p.add(0x1d0).readDouble());c.add(0x90).writeDouble(j.args.fare_per_km??p.add(0x1d8).readDouble());
        c.add(0x98).writeU32(j.args.color??p.add(0xb8).readU32());c.add(0x9c).writeU32(p.add(0xc0).readU32());
      } else if(j.kind==='line_service') {
        const p=findLine(db.add(0x180),uint64(j.args.id));
        if(p.isNull()){finish(j,null,'Line not found');return;}
        if(j.args.reference_train&&!train(db,j.args.reference_train))throw Error('Reference train not found');
        serviceFactory(holder);j.command=holder.readPointer();const c=j.command;
        c.add(0x20).writeU64(uint64(j.args.id));
        for(const [to,from] of [[0x28,0xfc],[0x2c,0x100],[0x30,0x104],[0x34,0x108],[0x38,0x10c],[0x3c,0x110],[0x40,0x190],[0x48,0x1e4],[0x50,0x1ec],[0x58,0x1f4],[0x68,0x200],[0x6c,0x204],[0x70,0x208],[0x74,0x20c],[0x78,0x210],[0x7c,0x214]])c.add(to).writeU32(p.add(from).readU32());
        for(const [to,from] of [[0x44,0x1e3],[0x4c,0x1e8],[0x54,0x1f0],[0x80,0xbc],[0x81,0xc4],[0x82,0x1e0],[0x83,0x1e1]])c.add(to).writeU8(p.add(from).readU8());
        c.add(0x60).writeU64(j.args.reference_train?uint64(j.args.reference_train):p.add(0x1f8).readU64());
        c.add(0x28).writeS32(j.args.service);
      } else if(j.kind==='add_stop') {
        const l=line(db,j.args.line_id),n=node(db,j.args.node_id);
        if(!l||!n||n.station_id==='0'){finish(j,null,'Expected line and platform node');return;}
        j.before=l.stop_count;
        stopFactory(holder);j.command=holder.readPointer();
        const e=allocate(uint64(0xb8));e.writeByteArray(new Uint8Array(0xb8));
        e.writeS32(l.stop_count);
        for(const offset of [8,16,40])e.add(offset).writePointer(e.add(0x30));
        e.add(24).writePointer(e.add(0x70));
        e.add(0x78).writeU64(uint64(j.args.node_id));e.add(0x80).writeDouble(0.5);
        e.add(0x88).writeU8(255);e.add(0x89).writeU8(1);
        e.add(0xa0).writeU8(1);e.add(0xa1).writeU8(1);
        e.add(0xa8).writeFloat(100);e.add(0xac).writeU8(1);e.add(0xad).writeU8(1);
        e.add(0xb0).writeU64(uint64(j.args.line_id));
        j.command.add(0x20).writePointer(e);j.command.add(0x28).writePointer(e.add(0xb8));j.command.add(0x30).writePointer(e.add(0xb8));
      } else if(j.kind==='rename_train') {
        const p=findTrain(db.add(0x200),uint64(j.args.id));
        if(p.isNull())throw Error('Train not found');
        if(trains(db).some(t=>t.id!==j.args.id&&t.serial===j.args.serial))throw Error('Train serial already exists');
        trainEditFactory(holder);j.command=holder.readPointer();const c=j.command;
        c.add(0x20).writeU64(uint64(j.args.id));writeString(c.add(0x28),j.args.name);writeString(c.add(0x48),j.args.serial);
        c.add(0x68).writeU32(p.add(0x130).readU32());c.add(0x6c).writeU32(p.add(0x134).readU32());
        c.add(0x70).writeU8(p.add(0x78).readU8());c.add(0x71).writeU8(p.add(0x138).readU8());
      } else if(j.kind==='purchase') {
        const purchaseLine=line(db,j.args.line_id);
        if(!purchaseLine)throw Error('Line does not exist');
        if(!/^[a-z][a-z0-9]*-[a-z0-9]+$/.test(purchaseLine.code))throw Error('Set a city-prefixed line code before buying trains, e.g. bj-1');
        purchaseFactory(holder);j.command=holder.readPointer();const c=j.command;j.trainIds=[];
        writeString(c.add(0x30),purchaseLine.name+' ####');writeString(c.add(0x50),purchaseLine.code+'-pending-'+Date.now()+'-####');
        c.add(0x70).writeU64(uint64('0x47ede2a4baaa7908')); // built-in Kayou 231 six-car preset
        const counts=allocate(uint64(12));[1,4,1].forEach((n,i)=>counts.add(i*4).writeU32(n));
        c.add(0x80).writePointer(counts);c.add(0x88).writePointer(counts.add(12));c.add(0x90).writePointer(counts.add(12));
        const cars=allocate(uint64(192));cars.writeByteArray(new Uint8Array(192));
        for(let i=0;i<6;i++) {
          const car=cars.add(i*32);car.writeU64(uint64(i===0||i===5?'0x3bedd81c7932bd83':'0xbe414ab5fd839c86'));
          car.add(20).writeU32(0xffffffff);car.add(24).writeU32(0xff3028a1);
          car.add(28).writeU8(i===5?1:0);car.add(29).writeU8(1);car.add(30).writeU8(1);car.add(31).writeU8(255);
        }
        c.add(0xe0).writePointer(cars);c.add(0xe8).writePointer(cars.add(192));c.add(0xf0).writePointer(cars.add(192));
        for(const [off,value] of [[0xfc,33.333335876464844],[0x100,1],[0x104,1],[0x108,2.5],[0x10c,159000],[0x110,1140000],[0x114,159000],[0x118,120],[0x11c,2.95]])c.add(off).writeFloat(value);
        c.add(0x120).writeU32(900);c.add(0x128).writeU64(uint64(13200000));
        c.add(0x130).writeDouble(0.00005000000074505806);c.add(0x138).writeDouble(0.002968749761581421);c.add(0x140).writeDouble(318/86400);
        c.add(0x148).writeU64(uint64('0x91c40db1ad3f2b92'));
        const ids=allocate(uint64(j.args.count*8));ids.writeByteArray(new Uint8Array(j.args.count*8));
        c.add(0x198).writePointer(ids);c.add(0x1a0).writePointer(ids.add(j.args.count*8));c.add(0x1a8).writePointer(ids.add(j.args.count*8));
        c.add(0x1b0).writeU64(uint64(j.args.line_id));
      } else if(j.kind==='rename_station'||j.kind==='station_label') {
        const p=findStation(db.add(0x80),uint64(j.args.id));
        if(p.isNull()){finish(j,null,'Station not found');return;}
        if(!p.add(0x48).readPointer().isNull()){finish(j,null,'Station tag preservation not yet implemented');return;}
        stationFactory(holder);j.command=holder.readPointer();const c=j.command;
        c.add(0x20).writeU64(uint64(j.args.id));
        j.before=station(db,j.args.id);
        const text=j.kind==='station_label'?j.before.name:j.args.name;
        const name=Memory.allocUtf8String(text);
        const length=unescape(encodeURIComponent(text)).length;
        assignString(c.add(0x28),name,uint64(length));
        c.add(0x48).writeU8(j.kind==='station_label'?p.add(0x40).readU8():0);
        for(const [to,from] of [[0x4c,0x44],[0x50,0x398],[0x54,0x39c],[0x58,0x3a8],[0x5c,0x3a0]])
          c.add(to).writeU32(p.add(from).readU32());
        c.add(0x60).writeU8(p.add(0x3a4).readU8());
        if(j.kind==='station_label')c.add(0x58).writeU32(j.args.label);
      } else {finish(j,null,'Unknown operation');return;}
      active=j;enqueue(this.output,j.command);
    } catch(e) {
      if(active){finish(active,null,'Submitted operation failed: '+String(e));active=null;}
      else if(currentJob)finish(currentJob,null,String(e));
      send({error:String(e)});
    }
  }
});
rpc.exports={async shutdown() {
  stopping=true;
  for(const j of pending)finish(j,null,'Bridge is shutting down; command cancelled');pending=[];
  for(let i=0;active&&i<50;i++)await new Promise(r=>setTimeout(r,100));
  if(active)throw Error('Cannot detach with an operation in flight');
  Interceptor.detachAll();Interceptor.flush();
  await new Promise(r=>setTimeout(r,1000));
  return true;
},request(kind,args) {
  if(stopping)throw Error('Bridge is shutting down');
  return new Promise((resolve,reject)=>{
    const j={kind,args,resolve,reject};
    j.timer=setTimeout(()=>{
      const index=pending.indexOf(j);
      if(index>=0)pending.splice(index,1);
      finish(j,null,index>=0?'No active world boundary; command cancelled':'Command timed out; outcome unknown, do not retry blindly');
    },5000);
    pending.push(j);
  });
}};
