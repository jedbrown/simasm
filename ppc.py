from collections import namedtuple

# Register contents
FPVal = namedtuple('FPVal','p s')
IntVal = namedtuple('IntVal','val')

class Register:
    'Contains resolved register name, not values'
    def __str__(self):
        return self.name
    def __eq__(self,x):
        return self.name == x.name and self.num == x.num
    def __hash__(self):
        return hash((self.name,self.num))
class FPRegister(Register):
    def __init__(self,num):
        self.num = num
        self.name = 'FPR_%02d' % (num,)
    def __repr__(self):
        return 'FPRegister(%d)' % (self.num,)
    def empty(self):
        return FPVal(0.0,0.0)
class IntRegister(Register):
    def __init__(self,num,c_var='',val=0):
        self.num = num
        self.name = 'Int_%02d' % (num,)
        self.c_var = c_var
    def __repr__(self):
        return 'IntRegister(%d)' % (self.num,)
    def empty(self):
        return IntVal(0)

class TrueRegister:
    def __init__(self,name,val):
        self.name = name
        self.val = val
    def __str__(self):
        return '%s=%s' % (self.name,self.val)
    def __repr__(self):
        return 'TrueRegister(%r=%r)' % (self.name,self.val)

class RegisterFile:
    def __init__(self,*args):
        if len(args) == 1:
            self.bank = args[0]
        else:
            cons, numregisters = args
            def mk(i):
                rname = cons(i)
                return TrueRegister(rname,rname.empty())
            self.bank = [mk(i) for i in range(numregisters)]
    def __str__(self):
        return 'RegisterFile(%s)' % ', '.join(str(treg) for treg in self.bank)
    def __repr__(self):
        return 'RegisterFile(%r)' % (self.bank,)
    def __getitem__(self,reg):
        treg = self.bank[reg.num]
        assert(treg.name == reg)
        return treg.val
    def __setitem__(self,reg,rval):
        treg = self.bank[reg.num]
        assert(treg.name == reg)
        assert(isinstance(rval,treg.val.__class__))
        treg.val = rval
    def keys(self):
        return (x.name for x in self.bank)
    def get(self,*regs):
        return map(self.__getitem__,regs)

class PPC:
    FP = 'floating point'
    INT = 'integer'
    LS = 'load/store'
    WORD_SIZE = 4
