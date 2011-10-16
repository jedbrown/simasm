class CViewer:
    def __init__(self,c):
        self.c = c

    def view(self, i):
        return 'asm volatile("' + i.__class__.__name__  + ' ' + ', '.join(repr(r.num) for r in i.saved.values()) + '"); '
    def named_view(self, i):
        if i.__class__.__name__[0] == 'f':
            return '    asm volatile("%s %s");' % (i.__class__.__name__,
                               ', '.join([('%d' % self.c.get_fpregister(k).num) for (temp, k) in i.saved.items()]))
        else:
            if 'u' in i.__class__.__name__:
                return '    asm volatile("%s %s, %%0, %%1":"+b" (%s):"b" (%s));' % (i.__class__.__name__,
                               self.c.get_fpregister(list(i.saved.items())[0][1]).num,i.saved['ra'].c_var,i.saved['rb'].c_var)
            else:
                return '    asm volatile("%s %s, %%0, %%1"::"b" (%s),"b" (%s));' % (i.__class__.__name__,
                               self.c.get_fpregister(list(i.saved.items())[0][1]).num,i.saved['ra'].c_var,i.saved['rb'].c_var)
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join([('%s=%r' % (k,v)) for (k,v) in self.saved.items()]))

def test():
    from simulate import get_core
    import isa
    from ppc import Register, FPRegister, IntRegister, RegisterFile
    c = get_core()
    (i0,i1,i2,i3) = map(IntRegister,range(4))
    (r0,r1,r2,r3) = c.acquire_fpregisters(range(4))

    cv = CViewer()

    i = isa.lfpdx(r0,i0,i1)
    print(i)
    print(cv.view(i))

    i = isa.stfxdux(r0,i0,i1)
    print(i)
    print(cv.view(i))

    i = isa.fxmul(r0,r1,r2)
    print(i)
    print(cv.view(i))

    i = isa.fxcpmadd(r0,r1,r2,r3)
    print(i)
    print(cv.view(i))


if __name__ == '__main__':
    test()
    
