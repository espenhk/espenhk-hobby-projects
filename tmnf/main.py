import time

from tminterface.client import Client
from tminterface.interface import TMInterface

from utils import StateData, steer_percent


class BackflipClient(Client):
    def __init__(self, speed: float = 1.0):
        super().__init__()
        self.speed = speed

    def on_registered(self, iface: TMInterface):
        print("Connected to TMInterface!")
        iface.execute_command(f"set speed {self.speed}")

    def on_run_step(self, iface: TMInterface, _time: int):
        state = iface.get_simulation_state()
        data = StateData(state)

        print(data)
        print()

        iface.set_input_state(
            accelerate=False,
            brake=True,
            steer=steer_percent(-30),  # slight left to induce tumble
        )


def main():
    client = BackflipClient(speed=0.1)
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