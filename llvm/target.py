import llvm
from llvmpy import api, extra
from io import BytesIO
import contextlib
from llvm.passes import TargetData

#===----------------------------------------------------------------------===
# Enumerations
#===----------------------------------------------------------------------===

BO_BIG_ENDIAN       = 0
BO_LITTLE_ENDIAN    = 1

# CodeModel
CM_DEFAULT      = api.llvm.CodeModel.Model.Default
CM_JITDEFAULT   = api.llvm.CodeModel.Model.JITDefault
CM_SMALL        = api.llvm.CodeModel.Model.Small
CM_KERNEL       = api.llvm.CodeModel.Model.Kernel
CM_MEDIUM       = api.llvm.CodeModel.Model.Medium
CM_LARGE        = api.llvm.CodeModel.Model.Large

# Reloc
RELOC_DEFAULT        = api.llvm.Reloc.Model.Default
RELOC_STATIC         = api.llvm.Reloc.Model.Static
RELOC_PIC            = api.llvm.Reloc.Model.PIC_
RELOC_DYNAMIC_NO_PIC = api.llvm.Reloc.Model.DynamicNoPIC

def initialize_all():
    api.llvm.InitializeAllTargets()
    api.llvm.InitializeAllTargetInfos()
    api.llvm.InitializeAllTargetMCs()
    api.llvm.InitializeAllAsmPrinters()
    api.llvm.InitializeAllDisassemblers()
    api.llvm.InitializeAllAsmParsers()

def initialize_target(target, noraise=False):
    """Initialize target by name.
    It is safe to initialize the same target multiple times.
    """
    prefix = 'LLVMInitialize'
    postfixes = ['Target', 'TargetInfo', 'TargetMC', 'AsmPrinter', 'AsmParser']
    try:
        for postfix in postfixes:
            getattr(api, '%s%s%s' % (prefix, target, postfix))()
    except AttributeError:
        if noraise:
            return False
        else:
            raise
    else:
        return True


def print_registered_targets():
    '''
    Note: print directly to stdout
    '''
    api.llvm.TargetRegistry.printRegisteredTargetsForVersion()

def get_host_cpu_name():
    '''return the string name of the host CPU
    '''
    return api.llvm.sys.getHostCPUName()

def get_default_triple():
    '''return the target triple of the host in str-rep
    '''
    return api.llvm.sys.getDefaultTargetTriple()

class TargetMachine(llvm.Wrapper):

    @staticmethod
    def new(triple='', cpu='', features='', opt=2, cm=CM_DEFAULT,
            reloc=RELOC_DEFAULT):
        if not triple:
            triple = get_default_triple()
        if not cpu:
            cpu = get_host_cpu_name()
        with contextlib.closing(BytesIO()) as error:
            target = api.llvm.TargetRegistry.lookupTarget(triple, error)
            if not target:
                raise llvm.LLVMException(error.getvalue())
            if not target.hasTargetMachine():
                raise llvm.LLVMException(target, "No target machine.")
            target_options = api.llvm.TargetOptions.new()
            tm = target.createTargetMachine(triple, cpu, features,
                                            target_options,
                                            reloc, cm, opt)
            if not tm:
                raise llvm.LLVMException("Cannot create target machine")
            return TargetMachine(tm)

    @staticmethod
    def lookup(arch, cpu='', features='', opt=2, cm=CM_DEFAULT,
               reloc=RELOC_DEFAULT):
        '''create a targetmachine given an architecture name

            For a list of architectures,
            use: `llc -help`

            For a list of available CPUs,
            use: `llvm-as < /dev/null | llc -march=xyz -mcpu=help`

            For a list of available attributes (features),
            use: `llvm-as < /dev/null | llc -march=xyz -mattr=help`
            '''
        triple = api.llvm.Triple.new()
        with contextlib.closing(BytesIO()) as error:
            target = api.llvm.TargetRegistry.lookupTarget(arch, triple, error)
            if not target:
                raise llvm.LLVMException(error.getvalue())
            if not target.hasTargetMachine():
                raise llvm.LLVMException(target, "No target machine.")
            target_options = api.llvm.TargetOptions.new()
            tm = target.createTargetMachine(str(triple), cpu, features,
                                            target_options,
                                            reloc, cm, opt)
            if not tm:
                raise llvm.LLVMException("Cannot create target machine")
            return TargetMachine(tm)

    @staticmethod
    def x86():
        return TargetMachine.lookup('x86')

    @staticmethod
    def x86_64():
        return TargetMachine.lookup('x86-64')

    @staticmethod
    def arm():
        return TargetMachine.lookup('arm')

    @staticmethod
    def thumb():
        return TargetMachine.lookup('thumb')

    def _emit_file(self, module, cgft):
        pm = api.llvm.PassManager.new()
        os = extra.make_raw_ostream_for_printing()
        pm.add(api.llvm.DataLayout.new(str(self.target_data)))
        failed = self._ptr.addPassesToEmitFile(pm, os, cgft)
        pm.run(module)


        CGFT = api.llvm.TargetMachine.CodeGenFileType
        if cgft == CGFT.CGFT_ObjectFile:
            return os.bytes()
        else:
            return os.str()

    def emit_assembly(self, module):
        '''returns byte string of the module as assembly code of the target machine
        '''
        CGFT = api.llvm.TargetMachine.CodeGenFileType
        return self._emit_file(module._ptr, CGFT.CGFT_AssemblyFile)

    def emit_object(self, module):
        '''returns byte string of the module as native code of the target machine
        '''
        CGFT = api.llvm.TargetMachine.CodeGenFileType
        return self._emit_file(module._ptr, CGFT.CGFT_ObjectFile)

    @property
    def target_data(self):
        '''get target data of this machine
        '''
        return TargetData(self._ptr.getDataLayout())

    @property
    def target_name(self):
        return self._ptr.getTarget().getName()

    @property
    def target_short_description(self):
        return self._ptr.getTarget().getShortDescription()

    @property
    def triple(self):
        return self._ptr.getTargetTriple()

    @property
    def cpu(self):
        return self._ptr.getTargetCPU()

    @property
    def feature_string(self):
        return self._ptr.getTargetFeatureString()
    
    @property
    def target(self):
        return self._ptr.getTarget()

    if llvm.version >= (3, 4):
        @property
        def reg_info(self):
            if not getattr(self, '_mri', False):
                self._mri = self.target.createMCRegInfo(self.triple)

            return self._mri

        @property
        def subtarget_info(self):
            return self._ptr.getSubtargetImpl()

        @property
        def asm_info(self):
            return self._ptr.getMCAsmInfo()

        @property
        def instr_info(self):
            return self._ptr.getInstrInfo()

        @property
        def instr_analysis(self):
            if not getattr(self, '_mia', False):
                self._mia = self.target.createMCInstrAnalysis(self.instr_info)

            return self._mia

        @property
        def disassembler(self):
            if not getattr(self, '_dasm', False):
                self._dasm = self.target.createMCDisassembler(self.subtarget_info)

            return self._dasm

        def is_little_endian(self):
            return self.asm_info.isLittleEndian()
