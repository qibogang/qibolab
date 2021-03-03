import numpy as np
from abc import ABC, abstractmethod
from io import BytesIO
from qibo.hardware import connections
from qibo.hardware.instruments import AcquisitionController
from qibo.config import raise_error


class Experiment(ABC):

    def __init__(self):
        self._connection = None
        self.static = None

    @property
    def connection(self):
        if self._connection is None:
            raise_error(RuntimeError, "Cannot establish connection.")
        return self.connection

    @abstractmethod
    def connect(self):
        raise_error(NotImplementedError)

    @abstractmethod
    def start(self):
        raise_error(NotImplementedError)

    @abstractmethod
    def stop(self):
        raise_error(NotImplementedError)

    @abstractmethod
    def upload(self):
        raise_error(NotImplementedError)

    @abstractmethod
    def download(self):
        raise_error(NotImplementedError)


class IcarusQ(Experiment):

    class StaticParameters():
        """Hardware static parameters."""
        num_qubits = 2
        sampling_rate = 2.3e9
        nchannels = 4
        sample_size = 32000
        readout_pulse_type = "IQ"
        readout_pulse_duration = 5e-6
        readout_pulse_amplitude = 0.75
        lo_frequency = 4.51e9
        readout_nyquist_zone = 4
        ADC_sampling_rate = 2e9
        default_averaging = 10000
        qubit_static_parameters = [
            {
                "id": 0,
                "channel": [2, None, [0, 1]], # XY control, Z line, readout
                "frequency_range": [2.6e9, 2.61e9],
                "resonator_frequency": 4.5241e9,
                "neighbours": [2],
                "amplitude": 0.75 / 2
            }, {
                "id": 1,
                "channel": [3, None, [0, 1]],
                "frequency_range": [3.14e9, 3.15e9],
                "resonator_frequency": 4.5241e9,
                "neighbours": [1],
                "amplitude": 0.75 / 2
            }
        ]
        dac_mode_for_nyquist = ["NRZ", "MIX", "MIX", "NRZ"] # fifth onwards not calibrated yet
        pulse_file = 'C:/fpga_python/fpga/tmp/wave_ch1.csv'

        # Temporary calibration result placeholder when actual calibration is not available
        from qibo.hardware import pulses
        calibration_placeholder = [{
            "id": 0,
            "qubit_frequency": 3.0473825e9,
            "qubit_amplitude": 0.75 / 2,
            "T1": 5.89e-6,
            "T2": 1.27e-6,
            "T2_Spinecho": 3.5e-6,
            "pi-pulse": 24.78e-9,
            "drive_channel": 3,
            "readout_channel": (0, 1),
            "iq_state": {
                "0": [0.016901687416102748, -0.006633150376482062],
                "1": [0.009458352995780546, -0.008570922209494462]
            },
            "gates": {
                "rx": [pulses.BasicPulse(3, 0, 24.78e-9, 0.375, 3.0473825e9 - sampling_rate, 0, pulses.Rectangular())],
                "ry": [pulses.BasicPulse(3, 0, 24.78e-9, 0.375, 3.0473825e9 - sampling_rate, 90, pulses.Rectangular())],
            }
        }]

    def __init__(self):
        super().__init__()
        self.static = self.StaticParameters()

    def connect(self, address, username, password):
        self._connection = connections.ParamikoSSH(address, username, password)

    def clock(self):
        self.connection.exec_command('clk-control')

    def start(self, adc_delay=0.0, verbose=False):
        stdin, stdout, stderr = self.connection.exec_command(
            'cd /tmp; ./cqtaws 1 {:.06f}'.format(adc_delay * 1e6))  # delay in us
        if verbose:
            for line in stdout:
                print(line.strip('\n'))

    def stop(self):
        self.connection.exec_command('cd /tmp; ./cqtaws 0 0')

    def upload(self, waveform):
        dump = BytesIO()
        with self.connection as sftp:
            for i in range(self.static.nchannels):
                dump.seek(0)
                np.savetxt(dump, waveform[i], fmt='%d', newline=',')
                dump.seek(0)
                sftp.putfo(dump)
        dump.close()

    def download(self):
        waveform = np.zeros((self.static.nchannels, self.static.sample_size))
        dump = BytesIO()
        with self.connection as sftp:
            for i in range(self.static.nchannels):
                dump.seek(0)
                #sftp.get('/tmp/ADC_CH{}.txt'.format(i + 1), local + 'ADC_CH{}.txt'.format(i + 1))
                dump = sftp.getfo(dump)
                dump.seek(0)
                #waveform.append(np.genfromtxt(local + 'ADC_CH{}.txt', delimiter=',')[:-1])
                waveform[i] = np.genfromtxt(dump, delimiter=',')[:-1]

        sftp.close()
        dump.close()

        return waveform

class AWGSystem(Experiment):
    class StaticParameters:
        """Hardware static parameters."""
        num_qubits = 2
        sampling_rate = 2.3e9
        nchannels = 7
        sample_size = 23000
        readout_pulse_type = "IQ"
        readout_pulse_duration = 5e-6
        readout_pulse_amplitude = 0.75 / 2
        readout_IF_frequency = 100e6
        readout_attenuation = 13
        qubit_attenuation = 18
        default_averaging = 10000
        lo_frequency = 4.5171749e9 - 100e6
        ADC_sampling_rate = 1e9
        ADC_length = 4992
        readout_start_time = 0

        ADC_delay = 266e-9 + 16e-9
        RO_SW_delay = 266e-9 - 22e-9
        QB_SW_delay = 266e-9 + 26e-9
        readout_phase = [-6.2, 0.2]

        awg_params = {
            "offset": [-0.001, 0, 0, 0],
            "phase": [-6.2, 0.2, 0, 0],
            "amplitude": [0.75, 0.75, 0.75, 0.75]
        }


        qubit_static_parameters = [
            {
                "id": 0,
                "name": "Left/Bottom Qubit",
                "channel": [3, None, [0, 1]], # XY control, Z line, readout
                "frequency_range": [3e9, 3.1e9],
                "resonator_frequency": 4.5171749e9,
                "amplitude": 0.75 / 2,
                "neighbours": [2]
            }, {
                "id": 1,
                "name": "Right/Top Qubit",
                "channel": [3, None, [0, 1]],
                "frequency_range": [2.14e9, 3.15e9],
                "resonator_frequency": 4.5241e9,
                "amplitude": 0.75 / 2,
                "neighbours": [1]
            }, 
        ]
        dac_mode_for_nyquist = ["NRZ", "MIX", "MIX", "NRZ"] # fifth onwards not calibrated yet
        pulse_file = 'C:/fpga_python/fpga/tmp/wave_ch1.csv'

        # Temporary calibration result placeholder when actual calibration is not available
        from qibo.hardware import pulses
        calibration_placeholder = [{
            "id": 0,
            "qubit_frequency": 3.0473825e9,
            "qubit_amplitude": 0.75 / 2,
            "T1": 5.89e-6,
            "T2": 1.27e-6,
            "T2_Spinecho": 3.5e-6,
            "pi-pulse": 24.78e-9,
            "drive_channel": 3,
            "readout_channel": (0, 1),
            "iq_state": {
                "0": [0.016901687416102748, -0.006633150376482062],
                "1": [0.009458352995780546, -0.008570922209494462]
            },
            "gates": {
                "rx": [pulses.BasicPulse(3, 0, 24.78e-9, 0.375, 3.0473825e9 - sampling_rate, 0, pulses.Rectangular())],
                "ry": [pulses.BasicPulse(3, 0, 24.78e-9, 0.375, 3.0473825e9 - sampling_rate, 90, pulses.Rectangular())],
            }
        }]

    def __init__(self):
        super().__init__()
        self.static = self.StaticParameters()
        self.ac = AcquisitionController()
        self.ic = self.ac.ic
        self.results = None

    def connect(self):
        pass

    def clock(self):
        pass

    def start(self):
        buffer, buffers_per_acquisition, records_per_buffer, samples_per_record, time_array = self.ac.do_acquisition()
        records_per_acquisition = (1. * buffers_per_acquisition * records_per_buffer)
        # Skip first 50 anomalous points
        recordA = np.zeros(samples_per_record - 50)
        recordB = np.zeros(samples_per_record - 50)

        for i in range(records_per_buffer):
            record_start = i * samples_per_record * 2
            record_stop = record_start + samples_per_record * 2
            record_slice = buffer[record_start:record_stop]
            recordA += record_slice[100::2] / records_per_acquisition
            recordB += record_slice[101::2] / records_per_acquisition

        recordA = self._signal_to_volt(recordA, 0.02)
        recordB = self._signal_to_volt(recordB, 0.02)

        self.results = [recordA, recordB]

    @staticmethod
    def _signal_to_volt(signal, voltdiv):
        u12 = signal / 16
        #bitsPerSample = 12
        codeZero = 2047.5
        codeRange = codeZero
        return voltdiv * (u12 - codeZero) / codeRange

    def stop(self):
        self.ac.stop()

    def upload(self, waveform, averaging):
        self.ic.setup(self.static.awg_params, self.static.lo_frequency, self.static.qubit_attenuation, self.static.readout_attenuation, 0)
        self.ic.awg.set_nyquist_mode()
        i_readout = waveform[0]
        q_readout = waveform[1]
        ch3_drive = waveform[2]
        ch4_drive = waveform[3]
        adc_ttl = waveform[4]
        ro_ttl = waveform[5]
        qb_ttl = waveform[6]
        output = self.ic.generate_pulse_sequence(i_readout, q_readout, ch3_drive, ch4_drive, adc_ttl, ro_ttl, qb_ttl, 60, averaging, self.static.sampling_rate)
        self.ic.awg.upload_sequence(output, 1)
        self.ic.ready_instruments_for_scanning(self.static.qubit_attenuation, self.static.readout_attenuation, 0)
        self.ac.update_acquisitionkwargs(mode='NPT',
                                         samples_per_record=self.static.ADC_length,
                                         records_per_buffer=10,
                                         buffers_per_acquisition=int(averaging / 10),
                                         #channel_selection='AB',
                                         #transfer_offset=0,
                                         #external_startcapture='ENABLED',
                                         #enable_record_headers='DISABLED',
                                         #alloc_buffers='DISABLED',
                                         #fifo_only_streaming='DISABLED',
                                         interleave_samples='DISABLED',
                                         #get_processed_data='DISABLED',
                                         allocated_buffers=100,
                                         buffer_timeout=100000)

    def upload_batch(self, waveform_batch, averaging):
        self.ic.setup(self.static.awg_params, self.static.lo_frequency, self.static.qubit_attenuation, self.static.readout_attenuation, 0)
        self.ic.awg.set_nyquist_mode()
        i_readout = waveform_batch[0, 0]
        q_readout = waveform_batch[1, 0]
        ch3_drive = waveform_batch[2]
        ch4_drive = waveform_batch[3]
        adc_ttl = waveform_batch[4, 0]
        ro_ttl = waveform_batch[5, 0]
        qb_ttl = waveform_batch[6, 0]
        steps = len(ch3_drive)
        output = self.ic.generate_broadbean_sequence(i_readout, q_readout, ch3_drive, ch4_drive, steps, adc_ttl, ro_ttl, qb_ttl, 60, averaging, self.static.sampling_rate)
        self.ic.awg.upload_sequence(output, steps)
        self.ic.ready_instruments_for_scanning(self.static.qubit_attenuation, self.static.readout_attenuation, 0)
        self.ac.update_acquisitionkwargs(mode='NPT',
                                         samples_per_record=self.static.ADC_length,
                                         records_per_buffer=10,
                                         buffers_per_acquisition=int(averaging / 10),
                                         #channel_selection='AB',
                                         #transfer_offset=0,
                                         #external_startcapture='ENABLED',
                                         #enable_record_headers='DISABLED',
                                         #alloc_buffers='DISABLED',
                                         #fifo_only_streaming='DISABLED',
                                         interleave_samples='DISABLED',
                                         #get_processed_data='DISABLED',
                                         allocated_buffers=100,
                                         buffer_timeout=100000)

    def start_batch(self, steps):
        self.results = np.zeros((steps, 2, self.static.ADC_length - 50))
        for k in range(steps):

            buffer, buffers_per_acquisition, records_per_buffer, samples_per_record, time_array = self.ac.do_acquisition()
            records_per_acquisition = (1. * buffers_per_acquisition * records_per_buffer)
            # Skip first 50 anomalous points
            recordA = np.zeros(samples_per_record - 50)
            recordB = np.zeros(samples_per_record - 50)

            for i in range(records_per_buffer):
                record_start = i * samples_per_record * 2
                record_stop = record_start + samples_per_record * 2
                record_slice = buffer[record_start:record_stop]
                recordA += record_slice[100::2] / records_per_acquisition
                recordB += record_slice[101::2] / records_per_acquisition

            self.results[k, 0] = self._signal_to_volt(recordA, 0.02)
            self.results[k, 1] = self._signal_to_volt(recordB, 0.02)

    def download(self):
        return self.results
