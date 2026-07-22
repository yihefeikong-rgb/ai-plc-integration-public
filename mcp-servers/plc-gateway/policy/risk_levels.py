"""风险等级定义和判断"""
from __future__ import annotations

from enum import Enum


class RiskLevel(Enum):
    """风险等级 L0-L4"""
    L0_READ_ONLY = "L0"
    L1_FILE_GEN = "L1"
    L2_TIA_EDIT = "L2"
    L3_SIM_CONTROL = "L3"
    L4_REAL_DEVICE = "L4"


# 各等级的描述
RISK_DESCRIPTIONS = {
    RiskLevel.L0_READ_ONLY: "纯读取，无需人工确认",
    RiskLevel.L1_FILE_GEN: "本地文件生成，不修改 TIA 项目",
    RiskLevel.L2_TIA_EDIT: "TIA 工程修改，必须 Preview/Apply 和自动备份",
    RiskLevel.L3_SIM_CONTROL: "仿真控制，必须人工确认、隔离目标验证和事后只读核验",
    RiskLevel.L4_REAL_DEVICE: "真实设备操作，默认禁用",
}

# 各等级所需的安全措施
RISK_REQUIREMENTS = {
    RiskLevel.L0_READ_ONLY: {"preview": False, "confirmation": False, "backup": False},
    RiskLevel.L1_FILE_GEN: {"preview": False, "confirmation": False, "backup": False},
    RiskLevel.L2_TIA_EDIT: {"preview": True, "confirmation": True, "backup": True},
    RiskLevel.L3_SIM_CONTROL: {"preview": True, "confirmation": True, "backup": True},
    RiskLevel.L4_REAL_DEVICE: {"preview": True, "confirmation": True, "backup": True,
                                "default_disabled": True},
}


def is_default_disabled(level: RiskLevel) -> bool:
    """是否默认禁用"""
    return RISK_REQUIREMENTS[level].get("default_disabled", False)


def requires_preview(level: RiskLevel) -> bool:
    return RISK_REQUIREMENTS[level].get("preview", False)


def requires_confirmation(level: RiskLevel) -> bool:
    return RISK_REQUIREMENTS[level].get("confirmation", False)


def requires_backup(level: RiskLevel) -> bool:
    return RISK_REQUIREMENTS[level].get("backup", False)