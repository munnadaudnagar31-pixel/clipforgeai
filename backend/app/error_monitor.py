import sys
import os
import json
import traceback

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Find root folder (two levels up from backend/app)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(current_dir))
    log_file = os.path.join(root_dir, 'render_crash_report.json')

    error_details = {
        "error_type": exc_type.__name__,
        "message": str(exc_value),
        "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    }

    try:
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(error_details, f, indent=4)
    except Exception as e:
        print(f"Failed to write crash report: {e}")

    # Call the default handler so the crash still appears in server logs
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Override the global exception handler
sys.excepthook = handle_exception
