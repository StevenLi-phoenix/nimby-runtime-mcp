// Operations adapter for the SHA256-locked 1.19.10 build.
// No writes to live objects: edits are native commands, checked at the next boundary.
function readCompanyLoans(sim) {
  const loans=boundedVector(sim.add(8),0x38,10000).map((p,index)=>{
    const principal=p.add(0x20).readDouble(),rate=p.add(0x10).readDouble();
    const months=p.add(0x18).readS32(),paid=p.add(0x30).readS32();
    const interest=principal>0&&paid<months?principal*rate:0;
    if(!Number.isFinite(principal)||!Number.isFinite(rate)||principal<0||rate<0)throw Error('Invalid loan data');
    return {index,original_principal:p.add(8).readDouble(),remaining_principal:principal,
      interest_rate:rate,total_months:months,paid_months:paid,repayment_interest:interest,
      repayment_total:principal+interest};
  });
  return {cash:sim.readDouble(),loans,total_outstanding:loans.reduce((s,l)=>s+l.remaining_principal,0)};
}
function boundedVector(p, stride, limit=10000) {
  const b=p.readPointer(),e=p.add(8).readPointer();
  if(e.compare(b)<0)throw Error('Reversed vector');
  const bytes=parseInt(e.sub(b).toString(),16),n=bytes/stride;
  if(!Number.isInteger(n)||n<0||n>limit)throw Error('Invalid vector size');
  return Array.from({length:n},(_,i)=>b.add(i*stride));
}
function pagedObjects(t,stride,tag) {
  const slots=t.add(8).readU32(),pages=boundedVector(t.add(24),8,10000);
  if(slots*pages.length>1000000)throw Error('Oversized object table');
  const out=[];
  for(const pp of pages) {const p=pp.readPointer();if(p.isNull())continue;
    for(let i=0;i<slots;i++){const q=p.add(i*stride);if(q.readU64().shr(48).toNumber()===tag)out.push(q);}}
  return out;
}
function hashObjects(p,nextOffset,limit=10000) {
  const buckets=p.add(8).readPointer(),n=p.add(16).readU32(),expected=p.add(24).readU64().toNumber();
  if(n>100000||expected>limit)throw Error('Oversized hash table');
  const result=[],seen=new Set();
  for(let i=0;i<n;i++){let q=buckets.add(i*8).readPointer();while(!q.isNull()) {
    if(seen.has(q.toString())||result.length>=limit)throw Error('Invalid hash chain');
    seen.add(q.toString());result.push(q);q=q.add(nextOffset).readPointer();}}
  if(result.length!==expected)throw Error('Hash count mismatch');
  // Native rehash changes bucket iteration order, not schedule contents.
  return result.sort((a,b)=>{const x=a.readU64().toString(),y=b.readU64().toString();return x.length-y.length||(x<y?-1:x>y?1:0);});
}
function schedulePointer(db,id){return pagedObjects(db.add(0x280),0x290,6).find(p=>p.readU64().toString()===id)||null;}
function scheduleOrder(p,depth=0) {
  if(depth>32)throw Error('Schedule order nesting limit exceeded');
  return {id:p.add(0x28).readU64().toString(),line_id:p.add(0x30).readU64().toString(),
    start_time:p.add(0x18).readS32(),days_mask:p.add(0x1c).readS32(),timing_event:p.add(0x20).readS32(),
    enabled:p.readU8()!==0,flags:[0,1,2,3].map(o=>p.add(o).readU8()),repeat_count:p.add(0x38).readS32(),continue_into_next:p.add(0x3c).readU8()!==0,
    entry_stop_id:p.add(0x40).readU64().toString(),exit_stop_id:p.add(0x48).readU64().toString(),
    timing_stop_id:p.add(0x50).readU64().toString(),timing_bias:p.add(0x58).readS32(),group:p.add(0x5c).readS32(),
    children:boundedVector(p.add(0x60),0x78,1000).map(q=>scheduleOrder(q,depth+1))};
}
function scheduleDetails(p) {
  return {id:p.readU64().toString(),name:readString(p.add(0x10)),code:readString(p.add(0x30)),
    service:p.add(0x70).readS32(),auto_line_id:p.add(0x78).readU64().toString(),
    train_ids:boundedVector(p.add(0x1f8),8).map(q=>q.readU64().toString()),
    order_lists:hashObjects(p.add(0x90),0x48).map(q=>({id:q.readU64().toString(),name:readString(q.add(0x10)),orders:boundedVector(q.add(0x30),0x78,1000).map(o=>scheduleOrder(o))})),
    shifts:hashObjects(p.add(0x1b0),0x1d8).map(q=>{const s=q.add(8);return {id:s.readU64().toString(),name:readString(s.add(0x10)),enabled:s.add(0x30).readU8()!==0,
      instances:hashObjects(s.add(0xc0),0x20).map(i=>({id:i.add(8).readU64().toString(),order_list_id:i.add(16).readU64().toString(),offset_seconds:i.add(24).readS32()}))};}),
    train_shift_pairs:boundedVector(p.add(0x228),16).map(q=>({train_id:q.readU64().toString(),shift_id:q.add(8).readU64().toString()}))};
}
function readSchedules(db){return {schedules:pagedObjects(db.add(0x280),0x290,6).map(scheduleDetails)};}
function queueWaitMetrics(list,now) {
  const stack=[list.add(0x10).readPointer()],seen=new Set();
  let passengers=0,known=0,sum=0,max=0,over300=0;
  while(stack.length) {
    const q=stack.pop();if(q.isNull())continue;
    if(seen.has(q.toString())||seen.size>=100000)throw Error('Invalid passenger tree');
    seen.add(q.toString());stack.push(q.readPointer(),q.add(8).readPointer());
    for(const p of boundedVector(q.add(0x28),0x28,100000)) {
      const packed=p.add(0x20).readU32(),count=(packed>>>24)&127;
      passengers+=count;
      const started=p.add(0x10).readU64().toNumber();if(!started)continue;
      // Same elapsed-current-leg formula as the native passenger timeout check.
      const seconds=Math.max(0,((now>>>0)-(packed&0xffffff)-(started>>>0))|0);
      known+=count;sum+=seconds*count;if(count)max=Math.max(max,seconds);
      if(seconds>300)over300+=count;
    }
  }
  const waiting=list.add(0x30).readU64().toNumber();
  if(seen.size!==list.add(0x20).readU64().toNumber()||passengers!==waiting)throw Error('Passenger queue count mismatch');
  return {count_verified:true,wait_sample_count:known,average_wait_seconds:known?sum/known:null,
    max_wait_seconds:known?max:null,waiting_over_300_seconds:over300};
}
function readStationQueues(db,sim,ids) {
  const now=sim.add(0x2108).readU64().toNumber();
  const rows=pagedObjects(sim.add(0x40),0x178,2).filter(p=>!ids||ids.includes(p.readU64().toString()));
  return {simulation_time:now,scope:'station',stations:rows.map(p=>{
    const id=p.readU64().toString(),s=station(db,id),list=p.add(0x68);
    return {station_id:id,name:s?s.name:null,waiting:list.add(0x30).readU64().toNumber(),hall_waiting:p.add(0x60).readU32(),...queueWaitMetrics(list,now)};
  })};
}
function readTrainOperations(db,sim,ids) {
  const pax=new Map(pagedObjects(sim.add(0xd0),0x40,5).map(p=>[p.readU64().toString(),p.add(0x38).readU64().toNumber()]));
  return {simulation_time:sim.add(0x2108).readU64().toNumber(),trains:pagedObjects(db.add(0x200),0x178,5).filter(p=>!ids||ids.includes(p.readU64().toString())).map(p=>({
    ...train(db,p.readU64().toString()),orders_mode:p.add(0xb8).readS32(),onboard:pax.get(p.readU64().toString())??null}))};
}
function operationsRead(j,db,sim) {
  if(j.kind==='company_loans'){finish(j,readCompanyLoans(sim));return true;}
  if(j.kind==='list_schedules'){finish(j,readSchedules(db));return true;}
  if(j.kind==='get_schedule'){const p=schedulePointer(db,j.args.id);finish(j,p?scheduleDetails(p):null);return true;}
  if(j.kind==='station_queues'){finish(j,readStationQueues(db,sim,j.args.ids));return true;}
  if(j.kind==='train_operations'){finish(j,readTrainOperations(db,sim,j.args.ids));return true;}
  return false;
}
const operationFactories={schedule_create:0x304fd0,schedule_delete:0x3054c0,schedule_name:0x3056d0,
  shift_create:0x307e90,order_append:0x306c50,
  shift_instance:0x308fc0,train_schedule:0x303ce0,train_autorun:0x303b80,order_edit:0x307210,order_delete:0x307470};
function operationsPrepare(j,db,sim) {
  if(j.kind==='repay_loan') {
    if(sim.add(0x2118).readS32()!==0)throw Error('Pause before repaying loans');
    j.beforeFinance=readCompanyLoans(sim);
    const loan=j.beforeFinance.loans[j.args.index];
    if(!loan||loan.remaining_principal<=0)throw Error('Outstanding loan not found');
    if(j.beforeFinance.cash<loan.repayment_total)throw Error('Insufficient cash');
    j.repayment=loan.repayment_total;
    const holder=Memory.alloc(8);native(0x309d10,'pointer',['pointer'])(holder);
    j.command=holder.readPointer();
    if(!j.command.readPointer().equals(main.base.add(0xa6ce30)))throw Error('Invalid loan command factory');
    j.command.add(0x3c).writeU8(1);j.command.add(0x40).writeU64(j.args.index);
    return true;
  }
  const rva=operationFactories[j.kind];if(rva===undefined)return false;
  if(sim.add(0x2118).readS32()!==0)throw Error('Pause before editing schedules');
  j.beforeSchedules=readSchedules(db).schedules;
  let before=null;
  if(j.kind.startsWith('train_')) {
    if(!train(db,j.args.train_id))throw Error('Train not found');
    j.beforeTrain=train(db,j.args.train_id);
    if(j.kind==='train_autorun') {
      const l=line(db,j.args.line_id);if(!l||l.stop_count<2)throw Error('Operating line needs at least two stops');
      const assigned=j.beforeSchedules.filter(s=>s.train_ids.includes(j.args.train_id));
      const originLines=new Set(assigned.flatMap(s=>s.auto_line_id!=='0'?[s.auto_line_id]:s.order_lists.flatMap(o=>o.orders.map(r=>r.line_id))));
      if(originLines.size&&!originLines.has(j.args.line_id))throw Error('Cross-line reassignment requires verified physical routing; this tool only restores autorun on an existing assigned line');
    }
  }
  if(j.kind!=='schedule_create'&&j.kind!=='train_autorun') {
    before=j.beforeSchedules.find(s=>s.id===j.args.id);if(!before)throw Error('Schedule not found');
    if(before.auto_line_id!=='0')throw Error('Automatic line schedules are protected');
    if(j.kind==='schedule_delete'&&before.train_ids.length)throw Error('Unassign trains before deleting schedule');
    if((j.kind.startsWith('shift_')&&j.kind!=='shift_create'||j.kind==='train_schedule')&&!before.shifts.some(s=>s.id===j.args.shift_id))throw Error('Shift not found');
    if(j.kind==='shift_instance') {
      if(!before.shifts.find(s=>s.id===j.args.shift_id).instances.some(i=>i.id===j.args.instance_id))throw Error('Instance not found');
      if(!before.order_lists.some(l=>l.id===j.args.order_list_id))throw Error('Order list not found');
    }
    if(j.kind==='order_append'||j.kind==='order_edit') {
      if(!before.order_lists.some(l=>l.id===j.args.order_list_id))throw Error('Order list not found');
      const l=line(db,j.args.line_id);if(!l||l.stop_count<2)throw Error('Operating line needs at least two stops');
      if(j.kind==='order_edit'&&!before.order_lists.find(l=>l.id===j.args.order_list_id).orders.some(o=>o.id===j.args.order_id))throw Error('Top-level order not found');
    }
    if(j.kind==='order_delete'&&!before.order_lists.find(l=>l.id===j.args.order_list_id)?.orders.some(o=>o.id===j.args.order_id))throw Error('Top-level order not found');
  }
  native(rva,'pointer',['pointer'])(holder);j.command=holder.readPointer();const c=j.command;
  if(j.args.id)c.add(0x20).writeU64(uint64(j.args.id));
  if(j.kind==='schedule_name'){writeString(c.add(0x28),j.args.name);c.add(0x48).writeU8(1);}
  if(j.kind==='shift_instance') {
    c.add(0x28).writeU64(uint64(j.args.shift_id));c.add(0x30).writeU64(uint64(j.args.instance_id));
    c.add(0x38).writeU64(uint64(j.args.order_list_id));c.add(0x40).writeS32(j.args.offset_seconds);
  }
  if(j.kind==='train_schedule') {
    c.add(0x20).writeU64(uint64(j.args.train_id));c.add(0x28).writeU64(uint64(j.args.id));
    c.add(0x30).writeU64(uint64(j.args.shift_id));c.add(0x38).writeU8(j.args.assigned?1:0);
  }
  if(j.kind==='train_autorun') {
    c.add(0x20).writeU64(uint64(j.args.train_id));c.add(0x28).writeU64(uint64(j.args.line_id));
    j.autorunCommand=c;
    native(0x303ae0,'pointer',['pointer'])(holder);j.command=holder.readPointer();
    j.command.add(0x20).writeU64(uint64(j.args.train_id));j.command.add(0x28).writeS32(0);
    j.autorunStage='mode';
  }
  if(j.kind==='order_append'||j.kind==='order_edit') {
    const o=allocate(uint64(0x78));o.writeByteArray(new Uint8Array(0x78));
    if(j.kind==='order_edit') {
      const list=hashObjects(schedulePointer(db,j.args.id).add(0x90),0x48).find(q=>q.readU64().toString()===j.args.order_list_id);
      const original=boundedVector(list.add(0x30),0x78,1000).find(q=>q.add(0x28).readU64().toString()===j.args.order_id);
      native(0x334ee0,'pointer',['pointer','pointer'])(o,original);
    }
    o.add(0x18).writeS32(j.args.start_time);o.add(0x1c).writeS32(j.args.days_mask);
    if(j.kind==='order_append')o.writeU8(1);
    o.add(0x20).writeS32(1);o.add(0x30).writeU64(uint64(j.args.line_id));
    o.add(0x38).writeS32(j.args.repeat_count);o.add(0x3c).writeU8(j.args.continue_into_next?1:0);
    if(j.kind==='order_append')for(const off of [0x40,0x48,0x50])o.add(off).writeU64(uint64('18446744073709551615'));
    c.add(0x28).writeU64(uint64(j.args.order_list_id));
    const v=j.kind==='order_edit'?0x30:0x38;
    c.add(v).writePointer(o);c.add(v+8).writePointer(o.add(0x78));c.add(v+16).writePointer(o.add(0x78));
  }
  if(j.kind==='order_delete') {
    const ids=Memory.alloc(8);ids.writeU64(uint64(j.args.order_id));
    c.add(0x28).writeU64(uint64(j.args.order_list_id));constructIdSet(c.add(0x30),ids,ids.add(8));
  }
  return true;
}
function operationsComplete(j,db,sim,output) {
  if(j.kind==='repay_loan') {
    const after=readCompanyLoans(sim),before=j.beforeFinance;
    const verified=after.loans[j.args.index]?.remaining_principal===0&&
      Math.abs(before.cash-after.cash-j.repayment)<0.01&&
      before.loans.every((l,i)=>i===j.args.index||JSON.stringify(l)===JSON.stringify(after.loans[i]));
    finish(j,{before,after,repaid:j.repayment,verified});return true;
  }
  if(operationFactories[j.kind]===undefined)return false;
  if(j.autorunStage==='mode') {
    const p=pagedObjects(db.add(0x200),0x178,5).find(p=>p.readU64().toString()===j.args.train_id);
    if(!p||p.add(0xb8).readS32()!==0)throw Error('Autorun mode did not apply; line was not submitted');
    j.command=j.autorunCommand;j.autorunStage='line';active=j;enqueue(output,j.command);return true;
  }
  const after=readSchedules(db).schedules;
  if(j.kind.startsWith('train_')) {
    const t=train(db,j.args.train_id),p=pagedObjects(db.add(0x200),0x178,5).find(p=>p.readU64().toString()===j.args.train_id);
    const affected=after.filter(s=>s.train_ids.includes(j.args.train_id));
    const unrelated=j.beforeSchedules.filter(s=>s.id!==j.args.id&&!s.train_ids.includes(j.args.train_id)&&s.auto_line_id!==j.args.line_id);
    const preserved=unrelated.every(s=>JSON.stringify(s)===JSON.stringify(after.find(a=>a.id===s.id)));
    const verified=preserved&&t&&p&&(j.kind==='train_autorun'
      ?p.add(0xb8).readS32()===0&&affected.some(s=>s.auto_line_id===j.args.line_id)
      :p.add(0xb8).readS32()===1&&after.find(s=>s.id===j.args.id)?.train_shift_pairs.some(a=>a.train_id===j.args.train_id&&a.shift_id===j.args.shift_id)===j.args.assigned);
    finish(j,{train:t,orders_mode:p?p.add(0xb8).readS32():null,schedules:affected,before_train:j.beforeTrain,verified:!!verified});return true;
  }
  const unchanged=j.beforeSchedules.filter(s=>s.id!==j.args.id).every(s=>JSON.stringify(s)===JSON.stringify(after.find(a=>a.id===s.id)));
  let target=after.find(s=>s.id===j.args.id),verified=unchanged;
  if(j.kind==='schedule_create') {const added=after.filter(s=>!j.beforeSchedules.some(b=>b.id===s.id));target=added[0];verified=unchanged&&added.length===1&&target.auto_line_id==='0';}
  else if(j.kind==='schedule_delete')verified=unchanged&&!target;
  else if(j.kind==='schedule_name')verified=unchanged&&target?.name===j.args.name;
  else if(j.kind==='shift_create')verified=unchanged&&target?.shifts.length===j.beforeSchedules.find(s=>s.id===j.args.id).shifts.length+1;
  else if(j.kind==='shift_instance')verified=unchanged&&target?.shifts.find(s=>s.id===j.args.shift_id)?.instances.some(i=>i.id===j.args.instance_id&&i.order_list_id===j.args.order_list_id&&i.offset_seconds===j.args.offset_seconds);
  else if(j.kind==='order_append') {
    const old=j.beforeSchedules.find(s=>s.id===j.args.id).order_lists.find(l=>l.id===j.args.order_list_id).orders;
    const orders=target?.order_lists.find(l=>l.id===j.args.order_list_id)?.orders;
    const added=orders?.filter(o=>!old.some(b=>b.id===o.id));
    verified=unchanged&&added?.length===1&&added[0].enabled&&added[0].timing_event===1&&['line_id','start_time','days_mask','repeat_count','continue_into_next'].every(k=>added[0][k]===j.args[k]);
  }
  else if(j.kind==='order_edit') {
    const o=target?.order_lists.find(l=>l.id===j.args.order_list_id)?.orders.find(o=>o.id===j.args.order_id);
    verified=unchanged&&o&&o.timing_event===1&&['line_id','start_time','days_mask','repeat_count','continue_into_next'].every(k=>o[k]===j.args[k]);
  }
  else if(j.kind==='order_delete')verified=unchanged&&target&&!target.order_lists.find(l=>l.id===j.args.order_list_id)?.orders.some(o=>o.id===j.args.order_id);
  // Verify retained target settings as well as other schedules, not just requested fields.
  if(target&&j.kind!=='schedule_create') {
    const expected=JSON.parse(JSON.stringify(j.beforeSchedules.find(s=>s.id===j.args.id)));
    if(j.kind==='schedule_name')expected.name=j.args.name;
    if(j.kind==='shift_instance') {
      const i=expected.shifts.find(s=>s.id===j.args.shift_id).instances.find(i=>i.id===j.args.instance_id);
      i.order_list_id=j.args.order_list_id;i.offset_seconds=j.args.offset_seconds;
    }
    if(j.kind.startsWith('order_')) {
      const l=expected.order_lists.find(l=>l.id===j.args.order_list_id);
      if(j.kind==='order_delete')l.orders=l.orders.filter(o=>o.id!==j.args.order_id);
      if(j.kind==='order_edit') {
        const o=l.orders.find(o=>o.id===j.args.order_id);
        for(const k of ['line_id','start_time','days_mask','repeat_count','continue_into_next'])o[k]=j.args[k];
        o.timing_event=1;
      }
    }
    const comparable=JSON.parse(JSON.stringify(target));
    if(j.kind==='shift_create')comparable.shifts=comparable.shifts.filter(s=>expected.shifts.some(b=>b.id===s.id));
    if(j.kind==='order_append') {
      const l=comparable.order_lists.find(l=>l.id===j.args.order_list_id),old=expected.order_lists.find(l=>l.id===j.args.order_list_id);
      l.orders=l.orders.filter(o=>old.orders.some(b=>b.id===o.id));
    }
    verified=verified&&JSON.stringify(expected)===JSON.stringify(comparable);
  }
  finish(j,{schedule:target??null,verified});return true;
}
