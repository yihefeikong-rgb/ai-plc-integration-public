"""Provider 初始化"""
from .base import ProviderResult, TiaProvider
from .tiaworker import TiaWorkerProvider

__all__ = ["ProviderResult", "TiaProvider", "TiaWorkerProvider"]