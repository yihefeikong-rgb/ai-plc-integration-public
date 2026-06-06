"""Update golden backup — called by run_p3_complete.bat."""
import sys, os

# Add tia-mcp to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-servers', 'tia-mcp'))

from plcsim_api import archive_instance

golden_zip = r'D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip'
storage = r'D:\PLC cheng xu\TIA PLC CHENG XU\demo\plcsim_storage'

try:
    archive_instance('factoryio', golden_zip, storage)
    print('[OK] Golden backup updated')
except Exception as e:
    print(f'[WARN] Golden backup failed: {e}')
    sys.exit(1)
