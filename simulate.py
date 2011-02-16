#!/usr/bin/env python3

import isa
from ppc import Register, FPRegister, IntRegister, RegisterFile
import itertools
from collections import OrderedDict, deque

class Pipeline:
    def __init__(self,name,**args):
        self.name = name
        self.dict = OrderedDict(args)
    def __getitem__(self,key): return self.dict.__getitem__(key)
    def __setitem__(self,key,val): return self.dict.__setitem__(key,val)
    def has_key(self,key): return self.dict.__contains__(key)
    def __repr__(self):
        return 'Pipeline(%s,%r)' % (self.name,', '.join('%s=%s' % (key,val) for (key,val) in self.dict.items()))
    def flush(self):
        self.dict.clear()
    def stall(self, needed):
        stall = 0
        for x in needed:
            stall = max(stall, self.dict.get(x,0))
        return stall
    def conflicts(self, needed):
        conflict = OrderedDict()
        for x in needed:
            if x in self.dict:
                conflict[x] = self.dict[x]
        return conflict
    def retire(self, cycles=1):
        for k,v in list(self.dict.items()):
            if v <= cycles:
                del self.dict[k]
            else:
                self.dict[k] -= cycles

class Core:
    memsize = 32                # Number of doubles
    fpregisters = 8
    intregisters = 4
    def __init__(self,cycle=0,fp=RegisterFile(FPRegister,fpregisters),int=RegisterFile(IntRegister,intregisters),mem=[0.0]*memsize):
        self.cycle = cycle
        self.fp = fp
        self.int = int
        self.mem = mem
        self.hazards = Pipeline('Register')
        self.units = Pipeline('Logic Unit')
        self.regnames = dict()
        self.fppool = set(self.fp.keys())
    def __str__(self):
        return ('Core(cycle=%r,\n\tfp=%s,\n\tint=%s,\n\tmem=%r)'
                % (self.cycle,self.fp,self.int,self.mem))
    def __repr__(self):
        return ('Core(cycle=%r,\n\tfp=%r,\n\tint=%r,\n\tmem=%r)'
                % (self.cycle,self.fp,self.int,self.mem))
    def flush_pipeline(self):
        self.hazards.flush()
        self.units.flush()
    def get_fpregister(self,reg,auto=True):
        if isinstance(reg,Register): # The register has been named explicitly
            self.fppool.discard(reg)
            return reg
        else:                   # It is a string, find a concrete register
            phys = self.regnames.get(reg)
            if phys is None:
                if not auto: raise Exception('Register "%s" has not been assigned a physical register yet' % (reg,))
                phys = self.fppool.pop()
                self.regnames[reg] = phys
            return phys
    def next_cycle(self):
        self.cycle += 1
        self.hazards.retire()
        self.units.retire()
    def trace(self,msg):
        if isinstance(msg,isa.Instruction):
            print('[%2d] %s' % (self.cycle,msg))
        else:
            print('[%2d] -- %s' % (self.cycle,msg))
    def execute_one(self,instr):
        while self.units.stall((instr.unit,)) > 0:
            self.trace('Instruction unit in use: %s' % (instr.unit,))
            self.next_cycle()
        while self.hazards.stall(instr.read) > 0:
            self.trace('Register hazards: %s' % (self.hazards.conflicts(instr.read)))
            self.next_cycle()
        self.trace(instr)
        instr.run(self)
        self.units[instr.unit] = instr.ithroughput
        for reg in instr.write:
            self.hazards[reg] = instr.latency
    def execute(self,code):
        for instr in code:
            self.execute_one(instr)
    def cost(self,instr):
        return max(self.units.stall((instr.unit,)),
                   self.hazards.stall((self.get_fpregister(reg,auto=False) for reg in instr.read)))
    def ready(self,instr):
        return all(self.get_fpregister(reg) for reg in instr.read)
    def schedule_one(self,istreams):
        candidates = [(i,istream[0],self.cost(istream[0])) for (i,istream) in enumerate(istreams) if self.ready(istream[0])]
        candidates.sort(key=lambda c:c[2])
        for (i,instr,cost) in candidates:
            if self.ready(instr):
                self.execute_one(instr)
                # advance stream and move it to the back so that we consider it last when using a stable sort
                stream = istreams.pop(i)
                del stream[0]
                if len(stream) > 0:
                    istreams.append(stream)
                return
            else:
                self.trace('Not ready: %s',instr)
        raise Exception('Cannot find a safe instruction with search depth 1')
    def schedule(self,istreams):
        while any(len(s) > 0 for s in istreams):
            self.schedule_one(istreams)

def test():
    c = Core()
    (a21,r21,a23,b21,s21,b23,w01,w2x) = map(FPRegister,range(8))
    (i0,i1) = map(IntRegister,(0,1))
    c.mem[:32] = map(float,range(32))
    istream = [isa.fpset2(w01,1/9,2/9),
               isa.fpset2(w2x,1/9,-1),
               # main loop
               isa.fxcpmadd(r21,w01,a21,r21),
               isa.lfpd(a23,i0,16),
               isa.fxcpmadd(s21,w01,b21,s21),
               isa.lfpd(b23,i1,16),
               isa.fxcxma(r21,w01,a23,r21),
               isa.lfdu(a23,i0,16),
               isa.fxcxma(s21,w01,b23,s21),
               isa.lfdu(b23,i1,16),
               # need a store
               isa.inspect()]
    c.execute(istream)
    print()
    c.flush_pipeline()
    c.schedule([
            [isa.lfpd(a23,i0,16),
             isa.lfpd(b23,i1,16),
             isa.lfdu(a23,i0,16),
             isa.lfdu(b23,i1,16),
             ],
            [isa.fxcpmadd(r21,w01,a21,r21),
             isa.fxcpmadd(s21,w01,b21,s21),
             isa.fxcxma(r21,w01,a23,r21),
             isa.fxcxma(s21,w01,b23,s21),
             ],
            ])

def stencil():
    def label(c,i,j,kp,ks):
        return '%s_%d_%d_%d%d' % (c,i,j,kp,ks)
    def stream(i,j):
        def a(kp,ks): return label('a',i,j,kp,ks)
        p = 'p_%d_%d' % (i,j)
        yield isa.lfpd(a(0,1),p,0)
        for k in (2,4,6):
            yield isa.lfdu(a(k,k-1),p,16)
            yield isa.lfpd(a(k,k+1),p,0)
    def jam(i,j):
        def r(kp,ks): return label('r',i,j,kp,ks)
        for k in (2,4,6):
            rr = r(k,k-1)
            for ii in (-1,0,1):
                for jj in (-1,0,1):
                    def a(kp,ks): return label('a',i+ii,j+jj,kp,ks)
                    yield isa.fxcpmadd(rr,'w01',a(k,k-1),rr)
                    yield isa.fxcxma(rr,'w01',a(k,k+1),rr)
                    yield isa.fxcpmadd(rr,'w2x',a(k+2,k+1),rr)
    instrs = []
    for i in (0,1,2):
        for j in (0,1,2):
            instrs.append(stream(i,j))
    instrs.append(jam(1,1))
    yield isa.fpset2('w01',1/9,2/9)
    yield isa.fpset2('w2x',1/9,9)
    while True:
        for ins in instrs:
            yield next(ins)

def main():
    test()
    for instr in itertools.islice(stencil(),100):
        print(instr)

if __name__ == '__main__':
    main()
