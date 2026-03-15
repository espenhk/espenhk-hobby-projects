import time

from tminterface.interface import TMInterface

from clients import AdaptiveClient


def main():
    SPEED = 5.0
    #client = InstructionClient("runs/example_run.txt", centerline_file="tracks/a03_centerline.npy", speed=SPEED)
    #client = InstructionClient("runs/example_run.txt", speed=SPEED)
    client = AdaptiveClient("tracks/a03_centerline.npy", speed=SPEED)
    iface = TMInterface()

    print("Waiting for TMInterface connection...")
    iface.register(client)

    try:
        while iface.running:
            time.sleep(0)
    except KeyboardInterrupt:
        pass

    iface.close()


if __name__ == "__main__":
    main()
