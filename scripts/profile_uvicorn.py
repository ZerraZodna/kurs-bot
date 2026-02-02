import cProfile
import threading
import time
import uvicorn
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


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

    profile.dump_stats("d:/dev/kurs-bot/cprofile.out")


if __name__ == "__main__":
    main()
