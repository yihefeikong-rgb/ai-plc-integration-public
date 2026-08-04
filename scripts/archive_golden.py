"""Update golden backup — called by run_p3_complete.bat."""
import sys, os

# Add tia-mcp to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-servers', 'tia-mcp'))

from config_loader import cfg, TargetConfigurationError, validate_control_target
from plcsim_api import archive_instance


def main():
    # 唯一控制目标校验：目标漂移（非 demo_V21/factoryio/隔离 IP）时 fail-closed
    try:
        target = validate_control_target()
    except TargetConfigurationError as exc:
        print(f'[ERR] 控制目标配置无效，拒绝归档: {exc}')
        return 1

    # golden 路径只从 config.yaml 读取（与 p3_flow 恢复路径同源，消灭硬编码漂移）
    golden_zip = cfg.simulation.golden_backup.zip_path
    storage = cfg.simulation.golden_backup.storage_path

    # golden 路径必须与唯一控制目标工程同目录，拒绝漂移到其他位置
    project_dir = os.path.normcase(os.path.normpath(
        os.path.dirname(str(target.project_path))))
    for label, path in (('zip', golden_zip), ('storage', storage)):
        parent = os.path.normcase(os.path.normpath(os.path.dirname(path)))
        if parent != project_dir:
            print(f'[ERR] golden_backup.{label} 路径不在唯一控制目标工程目录: {path}')
            return 1

    try:
        archive_instance(target.plcsim_instance, golden_zip, storage)
        print('[OK] Golden backup updated')
        return 0
    except Exception as e:
        print(f'[WARN] Golden backup failed: {e}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
