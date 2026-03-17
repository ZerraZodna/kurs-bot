import cProfile
import sys
import threading
import time
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main() -> None:
    profile = cProfile.Profile()

    config = uvicorn.Config(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)

    profile.enable()
    thread.start()

    time.sleep(30)

    server.should_exit = True
    thread.join()
    profile.disable()

    profile.dump_stats("cprofile.out")


if __name__ == "__main__":
    main()
