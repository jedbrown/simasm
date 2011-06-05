from ppcasm.ppc import PPC, FPVal, IntVal
from collections import OrderedDict as odict

load_latency = 4
store_latency = 0                # not actually meaningful
fp_latency = 5

class Instruction:
    def __init__(self, pragmatic=False):
        self.read = set()
        self.write = set()
        self.iread = set()
        self.iwrite = set()
        self.saved = odict()
        self.uses(None,0)
        self.pragmatic = pragmatic
    def run(self,c):
        raise Exception('Not implemented')
    def writes(self,*args):
        self.write = set(args)
    def reads(self,*args):
        self.read = set(args)
    def iwrites(self,*args):
        self.iwrite = set(args)
    def ireads(self,*args):
        self.iread = set(args)
    def uses(self,unit,latency,ithroughput=1,writethrough=0):
        self.unit = unit
        self.latency = latency
        self.ithroughput = ithroughput
        self.writethrough = writethrough
    def save(self,loc,symbols):
        if isinstance(symbols,str):
            symbols = symbols.split()
        for sym in symbols:
            self.saved[sym] = loc[sym]
            setattr(self,sym,loc[sym])
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join([('%s=%r' % (k,v)) for (k,v) in self.saved.items()]))

def fpeaddr(ra,x):
    from ppcasm.ppc import IntRegister
    def chk(addr):
        if addr % 8 != 0:
            raise Exception('Computed effective address that is not a multiple of sizeof(double)')
        return addr // 8
    if isinstance(x,IntVal):    # Value was provided by a register
        return chk(ra.val + x.val)
    else:
        return chk(ra.val + x)

def fpeaddr_aligned(ra,x):
    def chk(double_addr):
        if double_addr % 2 != 0:
            raise Exception('Computed effective address not aligned to 2*sizeof(double)')
        return double_addr
    return chk(fpeaddr(ra,x))

class inspect(Instruction):
    '''Not a real instruction, handy for debugging'''
    def __init__(self):
        Instruction.__init__(self,pragmatic=True)
    def run(self,c):
        print(c)

class fpset2(Instruction):
    '''Not a real instruction, but handy for debugging/prologue'''
    def __init__(self,frt,p,s):
        Instruction.__init__(self,pragmatic=True)
        p, s = float(p), float(s)
        self.save(locals(),'frt p s')
        self.writes(frt)
        self.uses(PPC.FP,1)
    def run(self,c):
        c.fp[c.get_fpregister(self.frt)] = FPVal(self.p,self.s)

class intset(Instruction):
    '''Not a real instruction, but handy for debugging/prologue'''
    def __init__(self,ra,val):
        Instruction.__init__(self,pragmatic=True)
        val = int(val)
        self.save(locals(),'ra val')
        self.iwrites(ra)
        self.uses(PPC.INT,1)
    def run(self,c):
        c.int[self.ra] = IntVal(self.val)

class fmr(Instruction):
    def __init__(self,frt,frb):
        Instruction.__init__(self)
        self.save(locals(),'frt frb')
        self.reads(frb)
        self.writes(frt)
        self.uses(PPC.FP,1)
    def run(self,c):
        frt, frb = c.access_fpregisters(self.frt, self.frb)
        c.fp[c.get_fpregister(self.frt)] = FPVal(frb.p, frt.s)
        
class fxcxma(Instruction):
    def __init__(self,rt,ra,rc,rb):
        Instruction.__init__(self)
        self.save(locals(),'rt ra rc rb')
        self.reads(ra,rc,rb)
        self.writes(rt)
        self.uses(PPC.FP,fp_latency)
    def run(self,c):
        ra,rc,rb = c.access_fpregisters(self.ra,self.rc,self.rb)
        c.fp[c.get_fpregister(self.rt)] = FPVal(ra.s*rc.s + rb.p,
                                                ra.s*rc.p + rb.s)

class fxmul(Instruction):
    '''Floating Cross Multiply     fxmul  AS*CP -> TP, AP*CS -> TS'''
    def __init__(self,rt,ra,rc):
        Instruction.__init__(self)
        self.save(locals(),'rt ra rc')
        self.reads(ra,rc)
        self.writes(rt)
        self.uses(PPC.FP,fp_latency)
    def run(self,c):
        ra,rc = c.access_fpregisters(self.ra,self.rc)
        c.fp[c.get_fpregister(self.rt)] = FPVal(ra.s * rc.p,
                                                ra.p * rc.s)
    
class fxcpmadd(Instruction):
    def __init__(self,rt,ra,rc,rb):
        Instruction.__init__(self)
        self.save(locals(),'rt ra rc rb')
        self.reads(ra,rc,rb)
        self.writes(rt)
        self.uses(PPC.FP,fp_latency)
    def run(self,c):
        ra,rc,rb = c.access_fpregisters(self.ra,self.rc,self.rb)
        c.fp[c.get_fpregister(self.rt)] = FPVal(ra.p * rc.p + rb.p,
                                                ra.p * rc.s + rb.s)


class fxcsmadd(Instruction):
    def __init__(self,rt,ra,rc,rb):
        Instruction.__init__(self)
        self.save(locals(),'rt ra rc rb')
        self.reads(ra,rc,rb)
        self.writes(rt)
        self.uses(PPC.FP,fp_latency)
    def run(self,c):
        ra,rc,rb = c.access_fpregisters(self.ra,self.rc,self.rb)
        c.fp[c.get_fpregister(self.rt)] = FPVal(ra.s * rc.p + rb.p,
                                                ra.s * rc.s + rb.s)

class fxpmul(Instruction):
    def __init__(self,rt,ra,rc):
        Instruction.__init__(self)
        self.save(locals(),'rt ra rc')
        self.reads(ra,rc)
        self.writes(rt)
        self.uses(PPC.FP,fp_latency)
    def run(self,c):
        ra,rc = c.access_fpregisters(self.ra,self.rc)
        c.fp[c.get_fpregister(self.rt)] = FPVal(ra.p * rc.p,
                                                ra.p * rc.s)

class fxsmul(Instruction):
    def __init__(self,rt,ra,rc):
        Instruction.__init__(self)
        self.save(locals(),'rt ra rc')
        self.reads(ra,rc)
        self.writes(rt)
        self.uses(PPC.FP,fp_latency)
    def run(self,c):
        ra,rc = c.access_fpregisters(self.ra,self.rc)
        c.fp[c.get_fpregister(self.rt)] = FPVal(ra.s * rc.p,
                                                ra.s * rc.s)

class fpadd(Instruction):
    def __init__(self,rt,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'rt ra rb')
        self.reads(ra,rb)
        self.writes(rt)
        self.uses(PPC.FP,fp_latency)
    def run(self,c):
        ra,rb = c.access_fpregisters(self.ra,self.rb)
        c.fp[c.get_fpregister(self.rt)] = FPVal(ra.p + rb.p,
                                                ra.s + rb.s)

class lfpdux(Instruction):
    def __init__(self,frt,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'frt ra rb')
        self.ireads(ra,rb)
        self.writes(frt)
        self.iwrites(ra)
        self.uses(PPC.LS,load_latency,2)
    def run(self,c):
        ea = fpeaddr_aligned(c.int[self.ra],c.int[self.rb])
        c.fp[c.get_fpregister(self.frt)] = FPVal(c.mem[ea], c.mem[ea+1])
        c.int[self.ra] = IntVal(ea*PPC.WORD_SIZE)

class lfxdux(Instruction):
    def __init__(self,frt,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'frt ra rb')
        self.ireads(ra,rb)
        self.writes(frt)
        self.iwrites(ra)
        self.uses(PPC.LS,load_latency,2)
    def run(self,c):
        ea = fpeaddr_aligned(c.int[self.ra],c.int[self.rb])
        c.fp[c.get_fpregister(self.frt)] = FPVal(c.mem[ea+1], c.mem[ea])
        c.int[self.ra] = IntVal(ea*PPC.WORD_SIZE)

class lfpdu(Instruction):
    def __init__(self,frt,ra,d):
        Instruction.__init__(self)
        self.save(locals(),'frt ra d')
        self.ireads(ra)
        self.writes(frt)
        self.iwrites(ra)
        self.uses(PPC.LS,load_latency,2)
    def run(self,c):
        ea = fpeaddr_aligned(c.int[self.ra],self.d)
        c.fp[c.get_fpregister(self.frt)] = FPVal(c.mem[ea], c.mem[ea+1])
        c.int[self.ra] = IntVal(ea*8)

class lfpd(Instruction):
    def __init__(self,frt,ra,d):
        Instruction.__init__(self)
        self.save(locals(),'frt ra d')
        self.ireads(ra)
        self.writes(frt)
        self.uses(PPC.LS,load_latency,2)
    def run(self,c):
        ea = fpeaddr_aligned(c.int[self.ra],self.d)
        c.fp[c.get_fpregister(self.frt)] = FPVal(c.mem[ea], c.mem[ea+1])

class lfpdx(Instruction):
    def __init__(self,frt,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'frt ra rb')
        self.ireads(ra,rb)
        self.writes(frt)
        self.uses(PPC.LS,load_latency,2)
    def run(self,c):
        ea = fpeaddr_aligned(c.int[self.ra],c.int[self.rb])
        c.fp[c.get_fpregister(self.frt)] = FPVal(c.mem[ea], c.mem[ea+1])

class lfd(Instruction):
    def __init__(self,frt,ra,d):
        Instruction.__init__(self)
        self.save(locals(),'frt ra d')
        self.ireads(ra)
        self.writes(frt)
        self.uses(PPC.LS,load_latency,2)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],self.d)
        frt = c.get_fpregister(self.frt)
        c.fp[frt] = FPVal(c.mem[ea], c.fp[frt].s)

class lfdu(Instruction):
    def __init__(self,frt,ra,d):
        Instruction.__init__(self)
        self.save(locals(),'frt ra d')
        self.ireads(ra)
        self.writes(frt)
        self.iwrites(ra)
        self.uses(PPC.LS,load_latency,2)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],self.d)
        frt = c.get_fpregister(self.frt)
        c.fp[frt] = FPVal(c.mem[ea], c.fp[frt].s)
        c.int[self.ra] = IntVal(ea*8)

class lfdux(Instruction):
    def __init__(self,frt,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'frt ra rb')
        self.ireads(ra,rb)
        self.writes(frt)
        self.iwrites(ra)
        self.uses(PPC.LS,load_latency,2)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],c.int[self.rb])
        frt = c.get_fpregister(self.frt)
        c.fp[frt] = FPVal(c.mem[ea], c.fp[frt].s)
        c.int[self.ra] = IntVal(ea*8)

class lfsdux(Instruction):
    def __init__(self,frt,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'frt ra rb')
        self.ireads(ra,rb)
        self.writes(frt)
        self.iwrites(ra)
        self.uses(PPC.LS,load_latency,2)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],c.int[self.rb])
        frt = c.get_fpregister(self.frt)
        c.fp[frt] = FPVal(c.fp[frt].p, c.mem[ea])
        c.int[self.ra] = IntVal(ea*8)

class lfdx(Instruction):
    def __init__(self,frt,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'frt ra rb')
        self.ireads(ra,rb)
        self.writes(frt)
        self.uses(PPC.LS,load_latency,2)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],c.int[self.rb])
        frt = c.get_fpregister(self.frt)
        c.fp[frt] = FPVal(c.mem[ea], c.fp[frt].s)        

class lfsdx(Instruction):
    def __init__(self,frt,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'frt ra rb')
        self.ireads(ra,rb)
        self.writes(frt)
        self.uses(PPC.LS,load_latency,2)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],c.int[self.rb])
        frt = c.get_fpregister(self.frt)
        c.fp[frt] = FPVal(c.fp[frt].p, c.mem[ea])        

class stfxdux(Instruction):
    def __init__(self,frs,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'frs ra rb')
        self.reads(frs)
        self.ireads(ra,rb)
        self.iwrites(ra)
        self.uses(PPC.LS,store_latency,2,writethrough=16)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],c.int[self.rb])
        (frs,) = c.access_fpregisters(self.frs)
        c.mem[ea] = frs.s
        c.mem[ea+1] = frs.p
        c.int[self.ra] = IntVal(ea*8)
        
class stfpdux(Instruction):
    def __init__(self,frs,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'frs ra rb')
        self.reads(frs)
        self.ireads(ra,rb)
        self.iwrites(ra)
        self.uses(PPC.LS,store_latency,2,writethrough=16)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],c.int[self.rb])
        (frs,) = c.access_fpregisters(self.frs)
        c.mem[ea] = frs.p
        c.mem[ea+1] = frs.s
        c.int[self.ra] = IntVal(ea*8)

class stfsdx(Instruction):
    def __init__(self,frs,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'frs ra rb')
        self.reads(frs)
        self.ireads(ra,rb)
        self.iwrites(ra)
        self.uses(PPC.LS,store_latency,2,writethrough=16)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],c.int[self.rb])
        (frs,) = c.access_fpregisters(self.frs)
        c.mem[ea] = frs.s

class stfdx(Instruction):
    def __init__(self,frs,ra,rb):
        Instruction.__init__(self)
        self.save(locals(),'frs ra rb')
        self.reads(frs)
        self.ireads(ra,rb)
        self.iwrites(ra)
        self.uses(PPC.LS,store_latency,2,writethrough=16)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],c.int[self.rb])
        (frs,) = c.access_fpregisters(self.frs)
        c.mem[ea] = frs.p
        