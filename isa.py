from ppc import PPC, FPVal, IntVal

class Instruction:
    def __init__(self):
        self.read = set()
        self.write = set()
        self.saved = dict()
        self.uses(None,0)
    def run(self,c):
        raise Exception('Not implemented')
    def writes(self,*args):
        self.write = set(args)
    def reads(self,*args):
        self.read = set(args)
    def uses(self,unit,latency):
        self.unit = unit
        self.latency = latency
    def save(self,**args):
        self.saved = args
        self.__dict__.update(args)
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join([('%s=%r' % (k,v)) for (k,v) in self.saved.items()]))

def fpeaddr(ra,x):
    from ppc import IntRegister
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
        Instruction.__init__(self)
    def run(self,c):
        print(c)

class fpset2(Instruction):
    '''Not a real instruction, but handy for debugging/prologue'''
    def __init__(self,fpr,p,s):
        Instruction.__init__(self)
        self.save(fpr=fpr,p=float(p),s=float(s))
        self.writes(fpr)
        self.uses(PPC.FP,6)
    def run(self,c):
        c.fp[self.fpr] = FPVal(self.p,self.s)

class fxcxma(Instruction):
    def __init__(self,r0,r1,r2,r3):
        self.save(r0=r0,r1=r1,r2=r2,r3=r3)
        self.reads(r1,r2,r3)
        self.writes(r0)
        self.uses(PPC.FP,5)
    def run(self,c):
        r1,r2,r3 = map(c.fp.__getitem__,(self.r1,self.r2,self.r3))
        c.fp[self.r0] = FPVal(r1.s*r2.s + r3.p,
                              r1.s*r2.p + r3.s)

class fxcpmadd(Instruction):
    def __init__(self,r0,r1,r2,r3):
        self.save(r0=r0,r1=r1,r2=r2,r3=r3)
        self.reads(r1,r2,3)
        self.writes(r0)
        self.uses(PPC.FP,5)
    def run(self,c):
        r1,r2,r3 = map(c.fp.__getitem__,(self.r1,self.r2,self.r3))
        c.fp[self.r0] = FPVal(r1.p * r2.p + r3.p,
                              r1.p * r2.s + r3.s)

class lfpdux(Instruction):
    def __init__(self,frt,ra,rb):
        self.save(frt=frt,ra=ra,rb=rb)
        self.reads(ra,rb)
        self.writes(frt,ra)
        self.uses(PPC.LS,6)
    def run(self,c):
        ea = fpeaddr_aligned(c.int[self.ra],c.int[self.rb])
        c.fp[self.frt] = FPVal(c.mem[ea], c.mem[ea+1])
        c.int[self.ra] = IntVal(ea*PPC.WORD_SIZE)

class lfpdu(Instruction):
    def __init__(self,frt,ra,d):
        self.save(frt=frt,ra=ra,d=d)
        self.reads(ra)
        self.writes(frt,ra)
        self.uses(PPC.LS,6)
    def run(self,c):
        ea = fpeaddr_aligned(c.int[self.ra],self.d)
        c.fp[self.frt] = FPVal(c.mem[ea], c.mem[ea+1])
        c.int[self.ra] = IntVal(ea*8)

class lfpd(Instruction):
    def __init__(self,frt,ra,d):
        self.save(frt=frt,ra=ra,d=d)
        self.reads(ra)
        self.writes(frt)
        self.uses(PPC.LS,6)
    def run(self,c):
        ea = fpeaddr_aligned(c.int[self.ra],self.d)
        c.fp[self.frt] = FPVal(c.mem[ea], c.mem[ea+1])

class lfd(Instruction):
    def __init__(self,frt,ra,d):
        self.save(frt=frt,ra=ra,d=d)
        self.reads(ra)
        self.writes(frt)
        self.uses(PPC.LS,6)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],self.d)
        c.fp[self.frt] = FPVal(c.mem[ea], c.fp[self.frt].s)

class lfdu(Instruction):
    def __init__(self,frt,ra,d):
        self.save(frt=frt,ra=ra,d=d)
        self.reads(ra)
        self.writes(frt,ra)
        self.uses(PPC.LS,6)
    def run(self,c):
        ea = fpeaddr(c.int[self.ra],self.d)
        c.fp[self.frt] = FPVal(c.mem[ea], c.fp[self.frt].s)
        c.int[self.ra] = IntVal(ea*8)
