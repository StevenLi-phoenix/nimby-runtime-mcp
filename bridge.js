// Version-specific adapter. Every operation runs at a fresh core queue boundary.
const main = Process.mainModule;
if (main.path.toLowerCase().replace(/\\/g, '/') !==
    'd:/steamlibrary/steamapps/common/nimby rails/nimbyrails.exe') throw Error('Unexpected image');
const native = (rva, result, args) => new NativeFunction(main.base.add(rva), result, args);
const speedFactory = native(0x3092a0, 'pointer', ['pointer']);
const trackFactory = native(0x31bd20, 'pointer', ['pointer']);
const footprintFactory = native(0x2fd000, 'pointer', ['pointer']);
const platformFactory = native(0x31bde0, 'pointer', ['pointer']);
const buildFactory = native(0x31cab0, 'pointer', ['pointer']);
const stationDeleteFactory = native(0x2ff800, 'pointer', ['pointer']);
const stationFactory = native(0x2ff5e0, 'pointer', ['pointer']);
const lineFactory = native(0x301630, 'pointer', ['pointer']);
const stopFactory = native(0x31cf30, 'pointer', ['pointer']);
const copyStopProperties = native(0x3011f0, 'pointer', ['pointer','pointer']);
const purchaseFactory = native(0x31d0e0, 'pointer', ['pointer']);
const metaFactory = native(0x31d040, 'pointer', ['pointer']);
const serviceFactory = native(0x3032e0, 'pointer', ['pointer']);
const editFactory = native(0x2f6e90, 'pointer', ['pointer']);
const trainEditFactory = native(0x303fb0, 'pointer', ['pointer']);
const rebpFactory = native(0x319a10, 'pointer', ['pointer']);
const walkLinkFactory = native(0x2ffac0, 'pointer', ['pointer']);
const deleteFactory = native(0x3198e0, 'pointer', ['pointer']);
const splitFactory = native(0x2fb020, 'pointer', ['pointer']);
const pointOnTrack = native(0x3898d0, 'pointer', ['pointer','pointer','double','double']);
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
      return {id,node_id:b.add(0xa8).readU64().toString(),type:b.add(8).readS32(),depth:b.add(0x1c).readS32(),blueprint:b.add(0x24).readU8()!==0,x:b.add(0x28).readDouble(),y:b.add(0x30).readDouble(),rotation:Math.atan2(-b.add(0x38).readFloat(),b.add(0x3c).readFloat()),direction_x:b.add(0x3c).readFloat(),direction_y:-b.add(0x38).readFloat(),width:b.add(0x40).readFloat(),height:b.add(0x44).readFloat()};
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
function stationInventory(db) {
  const refs=new Map();
  for(const [table,stride,kind,lookup,visit] of [
    [db.add(0x428).readPointer(),0x4e8,1,findNode,p=>{const id=p.add(0xd0).readU64().toString();if(id!=='0')refs.set(id,(refs.get(id)||0)+1);}]
  ]) {
    const begin=table.add(0x18).readPointer(),end=table.add(0x20).readPointer(),pages=end.sub(begin).toUInt32()/8,slots=table.add(8).readU32();
    if(!Number.isInteger(pages)||pages*slots>1000000)throw Error('Invalid track table');
    for(let i=0;i<pages;i++){const page=begin.add(i*8).readPointer();if(page.isNull())continue;for(let k=0;k<slots;k++){const p=page.add(k*stride),id=p.readU64();if(id.shr(48).toNumber()===kind&&lookup(table,id).equals(p))visit(p);}}
  }
  const table=db.add(0x80),begin=table.add(0x18).readPointer(),end=table.add(0x20).readPointer(),pages=end.sub(begin).toUInt32()/8,slots=table.add(8).readU32(),stations=[];
  if(!Number.isInteger(pages)||pages*slots>100000)throw Error('Invalid station table');
  for(let i=0;i<pages;i++){const page=begin.add(i*8).readPointer();if(page.isNull())continue;for(let k=0;k<slots;k++){const p=page.add(k*0x3e8),id=p.readU64();if(id.shr(48).toNumber()===2&&findStation(table,id).equals(p))stations.push({...station(db,id.toString()),track_count:refs.get(id.toString())||0});}}
  return {stations};
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
  onEnter(){this.job=executing&&['build','build_selected'].includes(executing.kind)?executing:null;},
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
Interceptor.attach(main.base.add(0x2fd070), {
  onEnter(args){this.ours=active&&args[0].equals(active.command);if(this.ours)executing=active;},
  onLeave(){if(this.ours)executing=null;}
});
Interceptor.attach(main.base.add(0x3a85c0), {
  onEnter(){this.job=executing&&executing.kind==='create_footprint'?executing:null;},
  onLeave(retval){if(this.job)this.job.buildingId=retval.toString();}
});
function buildingDetails(db,id) {
  const b=findBuilding(db.add(0x428).readPointer().add(0x100),uint64(id));
  if(b.isNull())return null;
  return {id:b.readU64().toString(),type:b.add(8).readS32(),depth:b.add(0x1c).readS32(),blueprint:b.add(0x24).readU8()!==0,x:b.add(0x28).readDouble(),y:b.add(0x30).readDouble(),direction_x:b.add(0x3c).readFloat(),direction_y:-b.add(0x38).readFloat(),width:b.add(0x40).readFloat(),height:b.add(0x44).readFloat(),node_id:b.add(0xa8).readU64().toString()};
}
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
        else if(j.kind==='delete_empty_stations') {
          const after=stationInventory(db);finish(j,{deleted_ids:j.args.ids,stations:after.stations,verified:j.args.ids.every(id=>!station(db,id))&&j.beforeStations.filter(s=>!j.args.ids.includes(s.id)).every(s=>after.stations.some(a=>a.id===s.id&&a.track_count===s.track_count))});
        }
        else if(j.kind==='assign_station') {
          const nodes=j.args.ids.map(id=>node(db,id));
          const preserved=nodes.every((n,i)=>n&&['x','y','depth','track_type','previous','next','blueprint'].every(k=>n[k]===j.beforeNodes[i][k]));
          finish(j,{nodes,station:station(db,j.args.station_id),verified:preserved&&nodes.every(n=>n.station_id===j.args.station_id)});
        }
        else if(j.kind==='attach_footprint') {
          const building=buildingDetails(db,j.args.building_id),platform=node(db,j.args.platform_id);
          finish(j,{building,platform,verified:!!building&&building.node_id===j.args.platform_id&&!!platform&&platform.buildings.some(b=>b.id===j.args.building_id)&&(j.args.geometry||building.x===j.beforeBuilding.x&&building.y===j.beforeBuilding.y)});
        } else if(j.kind==='create_footprint') {
          const building=j.buildingId?buildingDetails(db,j.buildingId):null;
          const nodes=j.args.platform_ids.map(id=>node(db,id));
          const preserved=nodes.every((n,i)=>n&&n.x===j.beforeNodes[i].x&&n.y===j.beforeNodes[i].y&&n.depth===j.beforeNodes[i].depth);
          finish(j,{building,nodes,verified:!!building&&building.type===1&&building.depth===j.args.depth&&building.blueprint&&preserved});
        } else if(j.kind==='split_edge') {
          const after=network(db,[j.args.id]),oldIds=new Set(j.beforeNetwork.nodes.map(n=>n.id));
          const added=after.nodes.filter(n=>!oldIds.has(n.id));
          const edge=node(db,j.args.id),previous=node(db,j.before.previous),next=node(db,j.before.next);
          const beforeInsert=edge&&node(db,edge.previous),afterInsert=edge&&node(db,edge.next);
          // Native paired-curve recalculation can move the companion control point by centimetres.
          const recalculated=[];
          const intact=j.beforeNetwork.nodes.every(n=>after.nodes.some(a=>{const displacement=Math.hypot(a.x-n.x,a.y-n.y);if(a.id!==n.id)return false;if(displacement>0.01)recalculated.push({id:n.id,displacement});return a.track_type===n.track_type&&a.depth===n.depth&&a.station_id===n.station_id&&displacement<(n.station_id!=='0'?0.01:n.branch_parent!=='0'?2:0.5);}));
          const beforeOK=beforeInsert&&beforeInsert.id!==j.before.previous&&beforeInsert.previous===j.before.previous&&beforeInsert.next===j.before.id&&previous&&previous.next===beforeInsert.id;
          const afterOK=afterInsert&&afterInsert.id!==j.before.next&&afterInsert.previous===j.before.id&&afterInsert.next===j.before.next&&next&&next.previous===afterInsert.id;
          finish(j,{edge,previous,next,new_nodes:added,recalculated,verified:intact&&added.length>0&&!!(beforeOK||afterOK)});
        }
        else if(j.kind==='edit_geometry') {
          const after=network(db,j.args.points.map(p=>p.id)),byId=new Map(after.nodes.map(n=>[n.id,n]));
          const preserved=j.beforeNetwork.nodes.every(n=>{const a=byId.get(n.id);return a&&a.previous===n.previous&&a.next===n.next&&a.station_id===n.station_id&&a.depth===n.depth&&a.blueprint===n.blueprint&&a.track_type===n.track_type&&(n.station_id==='0'||Math.hypot(a.x-n.x,a.y-n.y)<0.1);});
          const nodes=j.args.points.map(p=>byId.get(p.id));
          finish(j,{nodes,verified:preserved&&after.count===j.beforeNetwork.count&&nodes.every((n,i)=>n&&Math.hypot(n.x-j.args.points[i].x,n.y-j.args.points[i].y)<0.1)});
        }
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
        else if(j.kind==='remove_stop') {
          const l=line(db,j.args.line_id), b=j.before;
          const expected=b.stops.filter(s=>s.stop_id!==j.args.stop_id);
          const verified=l!==null&&l.stop_count===expected.length&&
            ['id','name','code','color','service','reference_train','base_fare','fare_per_km'].every(k=>l[k]===b[k])&&
            l.stops.every((s,i)=>s.stop_id===expected[i].stop_id&&s.node_id===expected[i].node_id);
          finish(j,{line:l,removed_stop_id:j.args.stop_id,verified});
        }
        else if(j.kind==='edit_stop') {
          const l=line(db,j.args.line_id), b=j.before;
          const verified=l!==null&&l.stop_count===b.stop_count&&
            ['id','name','code','color','service','reference_train','base_fare','fare_per_km'].every(k=>l[k]===b[k])&&
            l.stops.every((s,i)=>s.stop_id===b.stops[i].stop_id&&s.node_id===(i===j.args.stop_index?j.args.node_id:b.stops[i].node_id));
          finish(j,{line:l,verified});
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
        } else if(j.kind==='build'||j.kind==='build_selected') {
          const nodes=j.args.ids.map(id=>node(db,id));
          const protectedNodes=(j.protectedBefore||[]).map(n=>node(db,n.id));
          const preserved=protectedNodes.every((n,i)=>n&&n.blueprint===j.protectedBefore[i].blueprint);
          const buildings=(j.args.building_ids||[]).map(id=>buildingDetails(db,id));
          finish(j,{code:j.code,nodes,buildings,protected_count:protectedNodes.length,verified:buildings.every(b=>b&&!b.blueprint)&&j.code===0&&nodes.every(n=>n!==null&&!n.blueprint&&n.buildings.every(b=>!b.blueprint))&&preserved});
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
      if(j.kind==='station_inventory') {finish(j,stationInventory(db));return;}
      if(j.kind==='status') {finish(j,state);return;}
      if(j.kind==='get_node') {finish(j,node(db,j.args.id));return;}
      if(j.kind==='build_checks') {
        const blocked=[];
        for(const id of j.args.ids){const p=findNode(db.add(0x428).readPointer(),uint64(id));if(p.isNull())throw Error('Track node not found');const buffers=[];
          for(const offset of [0x110,0x128]){const begin=p.add(offset).readPointer(),end=p.add(offset+8).readPointer(),size=end.sub(begin).toUInt32();if(size>65536||size%8!==0)throw Error('Invalid native check vector');if(size){const values=[];for(let k=0;k<Math.min(size,256);k+=8)values.push({u64:begin.add(k).readU64().toString(),f64:begin.add(k).readDouble()});buffers.push({offset,byte_length:size,values});}}
          if(buffers.length)blocked.push({node:node(db,id),buffers});
        }finish(j,{blocked});return;
      }
      if(j.kind==='sample_curve') {
        const p=findNode(db.add(0x428).readPointer(),uint64(j.args.id));
        if(p.isNull())throw Error('Track node not found');
        const out=Memory.alloc(16);
        const points=j.args.positions.map(position=>{pointOnTrack(p,out,position,0);return {position,x:out.readDouble(),y:out.add(8).readDouble()};});
        finish(j,{id:j.args.id,points});return;
      }
      if(j.kind==='get_network') {finish(j,network(db,j.args.ids));return;}
      if(j.kind==='nearby_nodes') {finish(j,nearbyNodes(db,j.args));return;}
      if(j.kind==='get_station') {finish(j,station(db,j.args.id));return;}
      if(j.kind==='get_line') {finish(j,line(db,j.args.id));return;}
      if(j.kind==='get_train') {finish(j,train(db,j.args.id));return;}
      if(j.kind==='building_catalog') {
        const catalog=db.add(0x428).readPointer().add(0x408).readPointer();
        const begin=catalog.add(0x108).readPointer(),end=catalog.add(0x110).readPointer();
        const count=end.sub(begin).toUInt32()/0x128;
        if(!Number.isInteger(count)||count<1||count>10000)throw Error('Invalid building catalog');
        const templates=[];
        for(let i=0;i<count;i++) {
          const p=begin.add(i*0x128);
          templates.push({index:i,id:readString(p),name:readString(p.add(0x28)),price_m2:p.add(0x84).readFloat(),default_width:p.add(0x98).readFloat(),default_height:p.add(0x9c).readFloat()});
        }
        finish(j,{templates});return;
      }
      if(j.kind==='get_trains') {finish(j,{trains:trains(db)});return;}
      holder.writePointer(ptr(0));
      if(j.kind==='set_speed') {
        speedFactory(holder);j.command=holder.readPointer();
        j.command.add(0x24).writeS32(j.args.speed);
      } else if(j.kind==='delete_empty_stations') {
        if(state.speed!==0)throw Error('Pause before deleting stations');
        j.beforeStations=stationInventory(db).stations;
        if(j.args.ids.some(id=>!j.beforeStations.some(s=>s.id===id&&s.track_count===0)))throw Error('Only existing stations without track references may be deleted');
        stationDeleteFactory(holder);j.command=holder.readPointer();
        const ids=Memory.alloc(j.args.ids.length*8);j.args.ids.forEach((id,i)=>ids.add(i*8).writeU64(uint64(id)));
        constructIdSet(j.command.add(0x20),ids,ids.add(j.args.ids.length*8));
      } else if(j.kind==='assign_station') {
        if(state.speed!==0)throw Error('Pause before assigning platforms');
        const target=station(db,j.args.station_id);
        j.beforeNodes=j.args.ids.map(id=>node(db,id));
        if(!target||j.beforeNodes.some(n=>!n||n.station_id==='0'||Math.hypot(n.x-target.x,n.y-target.y)>1000))throw Error('Expected existing nearby station and platform nodes');
        editFactory(holder);j.command=holder.readPointer();
        // TN Edit +0xc8 vector: {node ID, station ID}; native handler 0x3a4080
        // removes old membership, inserts target membership and recomputes stations.
        const size=j.args.ids.length*16,entries=allocate(uint64(size));
        j.args.ids.forEach((id,i)=>{entries.add(i*16).writeU64(uint64(id));entries.add(i*16+8).writeU64(uint64(j.args.station_id));});
        j.command.add(0xc8).writePointer(entries);j.command.add(0xd0).writePointer(entries.add(size));j.command.add(0xd8).writePointer(entries.add(size));
      } else if(j.kind==='attach_footprint') {
        if(state.speed!==0)throw Error('Pause before attaching footprint');
        const b=buildingDetails(db,j.args.building_id),n=node(db,j.args.platform_id);
        if(!b||b.type!==1||(!j.args.geometry&&b.node_id!=='0')||!n||n.station_id==='0')throw Error('Expected unbound footprint and platform');
        if(Math.hypot(b.x-n.x,b.y-n.y)>1000)throw Error('Footprint too far from platform');
        j.beforeBuilding=b;editFactory(holder);j.command=holder.readPointer();
        const entry=allocate(uint64(0xe8));entry.writeByteArray(new Uint8Array(0xe8));
        copyBuilding(entry,findBuilding(db.add(0x428).readPointer().add(0x100),uint64(b.id)));
        entry.add(0xa8).writeU64(uint64(n.id));
        if(j.args.geometry){[0xb0,0xb4,0xb8,0xbc].forEach((o,i)=>entry.add(o).writeFloat(j.args.geometry[i]));}
        j.command.add(0x98).writePointer(entry);j.command.add(0xa0).writePointer(entry.add(0xe8));j.command.add(0xa8).writePointer(entry.add(0xe8));
      } else if(j.kind==='create_footprint') {
        if(state.speed!==0)throw Error('Pause before footprint construction');
        j.beforeNodes=j.args.platform_ids.map(id=>node(db,id));
        if(j.beforeNodes.some(n=>!n||n.station_id==='0'))throw Error('Expected platform nodes');
        const catalog=db.add(0x428).readPointer().add(0x408).readPointer();
        const template=catalog.add(0x108).readPointer().add(0x128);
        if(readString(template)!=='waw_internal_footprint_building')throw Error('Footprint template changed');
        footprintFactory(holder);j.command=holder.readPointer();const c=j.command;
        c.add(0x20).writeDouble(j.args.start_x);c.add(0x28).writeDouble(j.args.start_y);
        c.add(0x30).writeDouble(j.args.end_x);c.add(0x38).writeDouble(j.args.end_y);
        c.add(0x40).writeS32(1);c.add(0x44).writeS32(j.args.depth);c.add(0x48).writeU64(uint64(0));
      } else if(j.kind==='split_edge') {
        const n=node(db,j.args.id),p=n&&node(db,n.previous);
        if(!n||!p||!n.blueprint||!p.blueprint||n.station_id!=='0')throw Error('Split requires a blueprint corridor control outside platforms');
        const raw=findNode(db.add(0x428).readPointer(),uint64(n.id));
        if(raw.add(0x3f0).readU64().toString()!=='0')throw Error('Cannot split a branch edge');
        const sample=Memory.alloc(16);pointOnTrack(raw,sample,j.args.position,0);
        const sx=sample.readDouble()-n.x,sy=sample.add(8).readDouble()-n.y;
        for(const neighbor of [p,node(db,n.next)])if(neighbor&&neighbor.station_id!=='0'&&sx*(neighbor.x-n.x)+sy*(neighbor.y-n.y)>0)throw Error('Split point falls on the platform side of a lead');
        j.before=n;j.beforeNetwork=network(db,[n.id]);
        if(j.beforeNetwork.count>=4900)throw Error('Network too large for complete split verification');
        splitFactory(holder);j.command=holder.readPointer();
        if(!j.command.readPointer().equals(main.base.add(0xa6cc00)))throw Error('Invalid Split factory');
        j.command.add(0x20).writeU64(uint64(n.id));j.command.add(0x28).writeDouble(j.args.position);
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
      } else if(j.kind==='edit_geometry') {
        if(j.args.tangent_only&&state.speed!==0)throw Error('Pause before setting tangents');
        j.beforeNetwork=network(db,j.args.points.map(p=>p.id));
        if(j.beforeNetwork.count>=4900)throw Error('Network too large for complete geometry verification');
        for(const p of j.args.points){const n=node(db,p.id);if(!n||!n.blueprint||n.station_id!=='0'||Math.hypot(n.x-p.x,n.y-p.y)>(j.args.tangent_only?0.000001:500))throw Error('Geometry edit requires unchanged selected controls or displacement <=500 world metres');}
        editFactory(holder);j.command=holder.readPointer();
        const size=j.args.points.length*24,positions=allocate(uint64(size)),directions=allocate(uint64(size));
        j.args.points.forEach((p,i)=>{const a=positions.add(i*24),b=directions.add(i*24);a.writeU64(uint64(p.id));a.add(8).writeDouble(p.x);a.add(16).writeDouble(p.y);b.writeU64(uint64(p.id));b.add(8).writeDouble(p.dx);b.add(16).writeDouble(p.dy);});
        for(const [offset,entries] of (j.args.tangent_only?[[0x38,directions]]:[[0x20,positions],[0x38,directions]])){j.command.add(offset).writePointer(entries);j.command.add(offset+8).writePointer(entries.add(size));j.command.add(offset+16).writePointer(entries.add(size));}
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
      } else if(j.kind==='build'||j.kind==='build_selected') {
        if(j.args.ids.some(id=>node(db,id)===null))throw Error('Verification node not found; construction not submitted');
        buildFactory(holder);j.command=holder.readPointer();
        if(j.kind==='build_selected') {
          j.protectedBefore=j.args.protected_ids.map(id=>node(db,id));
          if(j.protectedBefore.some(n=>!n))throw Error('Protected node missing');
          if(j.args.protected_ids.some(id=>j.args.ids.includes(id)))throw Error('Selection overlaps protected nodes');
          // Native Build's selection-only flag skips global blueprint enumeration.
          j.command.add(0x28).writeU8(1);
          const buildings=[...new Set([...j.args.ids.flatMap(id=>node(db,id).buildings.map(b=>b.id)),...(j.args.building_ids||[])])];
          if(buildings.some(id=>!buildingDetails(db,id)))throw Error("Selected building missing");
          for(const [offset,values] of [[0x30,j.args.ids],[0x60,buildings]]) {
            if(!values.length)continue;
            const entries=Memory.alloc(values.length*8);
            values.forEach((id,i)=>entries.add(i*8).writeU64(uint64(id)));
            constructIdSet(j.command.add(offset),entries,entries.add(values.length*8));
          }
        }
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
      } else if(j.kind==='remove_stop') {
        if(state.speed!==0)throw Error('Pause before removing a stop');
        const l=line(db,j.args.line_id);
        if(!l||l.stop_count<=1)throw Error('Expected line with multiple stops');
        const index=l.stops.findIndex(s=>s.stop_id===j.args.stop_id);
        if(index<0)throw Error('Stop ID not found; do not retry a previous removal');
        j.before=l;stopFactory(holder);j.command=holder.readPointer();
        const e=allocate(uint64(16));e.writeByteArray(new Uint8Array(16));
        e.writeS32(index);e.add(8).writeU64(uint64(j.args.line_id));
        j.command.add(0xe0).writePointer(e);j.command.add(0xe8).writePointer(e.add(16));j.command.add(0xf0).writePointer(e.add(16));
      } else if(j.kind==='edit_stop') {
        if(state.speed!==0)throw Error('Pause before editing stops');
        const l=line(db,j.args.line_id), n=node(db,j.args.node_id), i=j.args.stop_index;
        if(!l||!n||n.station_id==='0'||!Number.isInteger(i)||i<0||i>=l.stop_count)throw Error('Expected existing stop and platform');
        const old=node(db,l.stops[i].node_id);
        if(!old||old.station_id!==n.station_id)throw Error('Replacement must belong to the same station');
        j.before=l;
        const p=findLine(db.add(0x180),uint64(j.args.line_id));
        const source=p.add(0x118).readPointer().add(i*0x158);
        stopFactory(holder);j.command=holder.readPointer();
        const e=allocate(uint64(0xb8));e.writeByteArray(new Uint8Array(0xb8));
        e.writeS32(i);copyStopProperties(e.add(8),source.add(8));
        e.add(0x78).writeU64(uint64(j.args.node_id));e.add(0x80).writeDouble(0.5);
        e.add(0xb0).writeU64(uint64(j.args.line_id));
        j.command.add(0x38).writePointer(e);j.command.add(0x40).writePointer(e.add(0xb8));j.command.add(0x48).writePointer(e.add(0xb8));
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
