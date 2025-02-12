from qibolab import Platform
from qibolab.paths import qibolab_folder
from qibolab.pulses import Pulse, PulseSequence, ReadoutPulse

# Define PulseSequence
sequence = PulseSequence()
# Add some pulses to the pulse sequence
sequence.add(
    Pulse(
        start=0,
        amplitude=0.3,
        duration=4000,
        frequency=200_000_000,
        relative_phase=0,
        shape="Gaussian(5)",  # Gaussian shape with std = duration / 5
        channel=1,
        qubit=0,
    )
)

sequence.add(
    ReadoutPulse(
        start=4004,
        amplitude=0.9,
        duration=2000,
        frequency=20_000_000,
        relative_phase=0,
        shape="Rectangular",
        channel=2,
        qubit=0,
    )
)

# Define platform and load specific runcard
runcard = qibolab_folder / "runcards" / "tii1q.yml"
platform = Platform("tii1q", runcard)

# Connects to lab instruments using the details specified in the calibration settings.
platform.connect()
# Configures instruments using the loaded calibration settings.
platform.setup()
# Turns on the local oscillators
platform.start()
# Executes a pulse sequence.
results = platform.execute_pulse_sequence(sequence, nshots=3000)
print(f"results (amplitude, phase, i, q): {results}")
# Turn off lab instruments
platform.stop()
# Disconnect from the instruments
platform.disconnect()
