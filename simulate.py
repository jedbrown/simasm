#!/usr/bin/env python3

import isa
from ppc import FPRegister, IntRegister, RegisterFile

class Core:
    memsize = 32                # Number of doubles
    fpregisters = 8
    intregisters = 4
    def __init__(self,cycle=0,fp=RegisterFile(FPRegister,fpregisters),int=RegisterFile(IntRegister,intregisters),mem=[0.0]*memsize):
        self.cycle = cycle
        self.fp = fp
        self.int = int
        self.mem = mem # size of L1 cache
        self.hazards = dict()
        self.units = set()
    def __str__(self):
        return ('Core(cycle=%r,\n\tfp=%s,\n\tint=%s,\n\tmem=%r)'
                % (self.cycle,self.fp,self.int,self.mem))
    def __repr__(self):
        return ('Core(cycle=%r,\n\tfp=%r,\n\tint=%r,\n\tmem=%r)'
                % (self.cycle,self.fp,self.int,self.mem))
    def next_cycle(self):
        self.cycle += 1
        for reg in list(self.hazards.keys()):
            if self.hazards[reg] <= 1:
                del self.hazards[reg]
            else:
                self.hazards[reg] -= 1
        self.units.clear()
    def trace(self,msg):
        print('[%2d] %s' % (self.cycle,str(msg)))
    def execute(self,code):
        for instr in code:
            if instr.unit in self.units:
                self.trace('Instruction unit in use: %s' % (instr.unit,))
                self.next_cycle()
            while not instr.read.isdisjoint(self.hazards):
                self.trace('Register hazards: %s' % (self.hazards,))
                self.next_cycle()
            self.trace(instr)
            self.units.add(instr.unit)
            instr.run(self)
            for reg in instr.write:
                self.hazards[reg] = instr.latency

def test():
    c = Core()
    (a21,r21,a23,b21,s21,b23,w01,w2x) = map(FPRegister,range(8))
    (i0,i1) = map(IntRegister,(0,1))
    c.mem[:32] = map(float,range(32))
    c.execute([isa.fpset2(w01,1/9,2/9),
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
               isa.inspect()])

def main():
    test()

if __name__ == '__main__':
    main()
