class NipachanError(Exception):
    pass

class StepNormalizationError(NipachanError):
    pass

class StepMatchError(NipachanError):
    pass

class FeatureWriteError(NipachanError):
    pass

class ExecutionError(NipachanError):
    pass

class UnresolvedLocatorError(NipachanError):
    pass
