"""项目统一异常类型。

本模块集中定义 L0/L1 与管道层会抛出的可恢复或不可恢复异常。
调用方可按异常类型决定中止、降级为诊断模式，或提示用户修复输入数据。
"""


class AssemblyDatasetError(Exception):
    """项目基础异常。

    Args:
        message: 面向日志和调用方的错误说明。
    """


class StepImportError(AssemblyDatasetError):
    """STEP 文件导入失败或无法提取有效几何时抛出。"""


class UIDError(AssemblyDatasetError):
    """UID 生成、重复校验或格式校验失败时抛出。"""


class SerializationError(AssemblyDatasetError):
    """管道状态序列化或反序列化失败时抛出。"""


class FingerprintMismatchError(AssemblyDatasetError):
    """跨进程恢复 face 映射时几何指纹不匹配。"""

