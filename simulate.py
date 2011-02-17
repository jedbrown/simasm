#!/usr/bin/env python3

import isa
from ppc import Register, FPRegister, IntRegister, RegisterFile
import itertools
from collections import OrderedDict, deque, defaultdict

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
    fpregisters = 10
    intregisters = 6
    def __init__(self,cycle=0,fp=None,int=None,mem=None):
        self.cycle = cycle
        self.counter = defaultdict(lambda:0)
        self.fp = fp   if fp  is not None else RegisterFile(FPRegister,Core.fpregisters)
        self.int = int if int is not None else RegisterFile(IntRegister,Core.intregisters)
        self.mem = mem if mem is not None else [0.0]*Core.memsize
        self.hazards = Pipeline('Register')
        self.units = Pipeline('Logic Unit')
        self.regnames = dict()
        self.fppool = set(self.fp.keys())
        self.fpeternal = set()
        self.trace = self.trace_print
    def __str__(self):
        return ('Core(cycle=%r,\n\tfp=%s,\n\tint=%s,\n\tmem=%r,\n\tregnames=%s,\n\tcounter=%s)'
                % (self.cycle,self.fp,self.int,self.mem,self.regnames,dict(self.counter)))
    def __repr__(self):
        return ('Core(cycle=%r,\n\tfp=%r,\n\tint=%r,\n\tmem=%r,\n\tregnames=%r)'
                % (self.cycle,self.fp,self.int,self.mem,self.regnames))
    def flush_pipeline(self):
        self.hazards.flush()
        self.units.flush()
    def name_registers(self,**args):
        self.regnames.update(args)
        self.fppool.difference_update(args.values())
    def gc(self):
        raise Exception('Garbage collector not implemented')
    def get_fpregister(self,reg,allocate=True):
        if isinstance(reg,Register): # The register has been named explicitly
            self.fppool.discard(reg)
            return reg
        elif isinstance(reg,str): # It is a string, find a concrete register
            phys = self.regnames.get(reg)
            if phys is None:
                if not allocate: raise Exception('Register "%s" has not been allocated' % (reg,))
                if len(self.fppool) < 1:
                    self.gc()
                try:
                    phys = self.fppool.pop()
                except KeyError:
                    raise Exception('Cannot find a free register')
                self.regnames[reg] = phys
            return phys
        else:
            raise Exception('Invalid register: %r' % reg)
    def access_fpregisters(self,*args):
        return (self.fp[self.get_fpregister(reg)] for reg in args)
    def acquire_fpregisters(self,numbers):
        regs = list(map(FPRegister,numbers)) # Have to make this a list because otherwise set.update(regs) modifies regs
        self.fpeternal.update(regs)
        self.fppool.difference_update(regs)
        return regs
    def next_cycle(self):
        self.cycle += 1
        self.hazards.retire()
        self.units.retire()
    def trace_none(self,msg):
        pass
    def trace_print(self,msg):
        if isinstance(msg,isa.Instruction):
            print('[%2d] %s' % (self.cycle,msg))
        else:
            print('[%2d] -- %s' % (self.cycle,msg))
    def execute_one(self,instr):
        while self.units.stall((instr.unit,)) > 0:
            self.trace('Instruction unit in use: %s' % (instr.unit,))
            self.next_cycle()
        while self.hazards.stall(map(self.get_fpregister,instr.read)) > 0:
            def format_hazards(odict):
                return ', '.join('(%s:%s,%d)' % (reg,self.get_fpregister(reg,allocate=False),cost) for (reg,cost) in odict.items())
            self.trace('Register hazards: %s' % format_hazards(self.hazards.conflicts(instr.read)))
            self.next_cycle()
        self.trace(instr)
        instr.run(self)
        self.counter[instr.unit] += 1
        self.units[instr.unit] = instr.ithroughput
        for reg in instr.write:
            self.hazards[reg] = instr.latency
    def execute(self,code):
        for instr in code:
            self.execute_one(instr)
    def cost(self,instr):
        cost = max(self.units.stall((instr.unit,)),
                   self.hazards.stall((self.get_fpregister(reg,allocate=False) for reg in instr.read)))
        return cost
    def schedule_one(self,istream):
        def get_candidates(stream):
            'generator for safe instructions'
            modified = set()
            for i,instr in enumerate(stream):
                if modified.isdisjoint(instr.read.union(instr.iread)):
                    yield i,instr
                modified.update(instr.write)
                modified.update(instr.iwrite)
        candidates = list(get_candidates(istream))
        if len(candidates) < 1:
            raise Exception('Cannot find a safe instruction')
        (i,instr) = min(candidates, key=lambda c:self.cost(c[1]))
        self.execute_one(instr)
        del istream[i]
    def schedule(self,istream):
        while len(istream) > 0:
            self.schedule_one(istream)

def tests():
    def get_core():
        c = Core()
        c.mem[:32] = map(float,range(32))
        return c
    def merge(*streams):
        istreams = [iter(s) for s in streams]
        result = []
        while len(istreams) > 0:
            try:
                s = istreams.pop(0)
                result.append(next(s))
                istreams.append(s)
            except StopIteration:
                pass
        return result
    def s_weights(w01,w2x):
        return [isa.fpset2(w01,1/9,2/9), isa.fpset2(w2x,1/9,-1)]
    def s_preamble(a,i0):
        yield isa.lfpd(a,i0,0)  # A[0],A[1]
        yield isa.lfdu(a,i0,16) # A[2],A[1]
    def test1():
        c = get_core()
        (r21,s21,w01,w2x,a21,b21,a23,b23) = c.acquire_fpregisters(range(8))
        (i0,i1,ir0,is0,sixteen) = map(IntRegister,range(5))
        istream = (s_weights(w01,w2x)
                   + merge(s_preamble(a21,i0),s_preamble(b21,i1))
                   + [
                isa.fxcpmadd(r21,w01,a21,r21),
                isa.fxcpmadd(s21,w01,b21,s21),
                isa.lfpd(a23,i0,16),
                isa.lfpd(b23,i1,16),
                isa.fxcxma(r21,w01,a23,r21),
                isa.fxcxma(s21,w01,b23,s21),
                isa.lfdu(a23,i0,16), # Rename to a43
                isa.lfdu(b23,i1,16), # Rename to a43

                isa.intset(ir0,8*8),
                isa.intset(is0,18*8),
                isa.intset(sixteen,16),
                isa.stfxdux(r21,ir0,sixteen),
                isa.stfxdux(s21,is0,sixteen),
                ])
        #for instr in istream: print(instr); #c.trace = c.trace_none
        c.schedule(istream)
        c.execute([isa.inspect()])
    def test_alloc():
        c = get_core()
        (r21,s21,w01,w2x) = c.acquire_fpregisters(range(4))
        (i0,i1,ir0,is0,sixteen) = map(IntRegister,range(5))
        c.name_registers(a21=FPRegister(4),b21=FPRegister(5))
        istream = [
            # weights
            isa.fpset2(w01,1/9,2/9),
            isa.fpset2(w2x,1/9,-1),
            # preamble
            isa.lfpd('a21',i0,0),  # A[0],A[1]
            isa.lfdu('a21',i0,16), # A[2],A[1]
            isa.lfpd('b21',i1,0),  # A[0],A[1]
            isa.lfdu('b21',i1,16), # A[2],A[1]
            # start loads
            isa.fxcpmadd(r21,w01,'a21',r21),
            isa.fxcpmadd(s21,w01,'b21',s21),
            isa.lfpd('a23',i0,16),
            isa.lfpd('b23',i1,16),
            isa.fxcxma(r21,w01,'a23',r21),
            isa.fxcxma(s21,w01,'b23',s21),
            isa.lfdu('a23',i0,16), # a43
            isa.lfdu('b23',i1,16), # b43

            isa.intset(ir0,8*8),
            isa.intset(is0,18*8),
            isa.intset(sixteen,16),
            isa.stfxdux(r21,ir0,sixteen),
            isa.stfxdux(s21,is0,sixteen),
            ]
        #for instr in istream: print(instr); #c.trace = c.trace_none
        c.schedule(istream)
        c.execute([isa.inspect()])
    test1()
    test_alloc()

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
    tests()
    # for instr in itertools.islice(stencil(),10):
    #     print(instr)

if __name__ == '__main__':
    main()
