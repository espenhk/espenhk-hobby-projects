from tminterface.client import Client
from tminterface.interface import TMInterface
import time

class FullGasClient(Client):
    def on_registered(self, iface: TMInterface):
        print("Connected to TMInterface!")
        iface.execute_command("set speed 1")  # normal speed

    def on_run_step(self, iface: TMInterface, _time: int):
        # Called every simulation step while a run is active
        state = iface.get_simulation_state()

        # Print some telemetry
        pos = state.dyna.current_state.position      # type: ignore[attr-defined]  # numpy [x, y, z]
        speed = state.dyna.current_state.linear_speed  # type: ignore[attr-defined]  # numpy [x, y, z]
        print(f"Pos: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})  "
              f"Vel: ({speed[0]:.1f}, {speed[1]:.1f}, {speed[2]:.1f})")

        # Send controls: full gas, no brake, no steering
        iface.set_input_state(
            accelerate=True,
            brake=False,
            left=False,
            right=False,
            steer=0  # -65536 = full left, 65536 = full right, 0 = straight
        )


def main():
    client = FullGasClient()
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