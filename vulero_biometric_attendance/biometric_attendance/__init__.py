from importlib import import_module

_delegate = import_module('vulero_biometric_attendance.vulero_biometric_attendance')

globals().update({k: v for k, v in vars(_delegate).items() if not k.startswith('_')})
__all__ = getattr(_delegate, '__all__', [])
__path__ = list(getattr(_delegate, '__path__', []))
