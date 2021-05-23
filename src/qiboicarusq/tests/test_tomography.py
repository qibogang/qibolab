import os
import json
import pytest
import numpy as np
from qiboicarusq.tomography import Cholesky, Tomography


def test_cholesky_init():
    m = np.random.random((5, 5))
    c = Cholesky.from_matrix(m)
    np.testing.assert_allclose(c.matrix, m)
    v = np.random.random((5,))
    c = Cholesky.from_vector(v)
    np.testing.assert_allclose(c.vector, v)
    with pytest.raises(ValueError):
        c = Cholesky(matrix=m, vector=v)
    with pytest.raises(TypeError):
        c = Cholesky(matrix="test")
    with pytest.raises(TypeError):
        c = Cholesky(vector="test")


def test_cholesky_decompose():
    m = np.array([[1, 2, 3, 4, 5],
                  [2, 3, 4, 5, 6],
                  [3, 4, 5, 6, 7],
                  [4, 5, 6, 7, 8],
                  [5, 6, 7, 8, 9]])
    m = m + m.T
    m = m + 5 * np.eye(5, dtype=m.dtype)
    c = Cholesky.decompose(m)
    target_matrix = np.array([[1, 0, 0, 0, 0],
                              [0, 2, 0, 0, 0],
                              [0, 0, 7, 0, 0],
                              [1, 2, 2, 4, 0],
                              [0, 0, 0, 0, 0]])
    target_vector = np.array([1, 2, 7, 4, 0, 0, 0, 0, 1, 2, 2, 0, 0, 0, 0,
                              0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    np.testing.assert_allclose(c.matrix, target_matrix)
    np.testing.assert_allclose(c.vector, target_vector)


def test_cholesky_reconstruct():
    v = np.arange(16)
    c = Cholesky.from_vector(v)
    target_matrix = np.array([
        [0.38709677+0.j, 0.32580645-0.01774194j, 0.21612903-0.02741935j, 0.01693548-0.03145161j],
        [0.32580645+0.01774194j, 0.35564516+0.j, 0.23709677-0.02419355j, 0.01935484-0.03387097j],
        [0.21612903+0.02741935j, 0.23709677+0.02419355j, 0.25+0.j, 0.02177419-0.03629032j],
        [0.01693548+0.03145161j, 0.01935484+0.03387097j, 0.02177419+0.03629032j, 0.00725806+0.j]])
    np.testing.assert_allclose(c.reconstruct(), target_matrix, atol=1e-7)


def test_tomography_init():
    amplitudes = np.random.random(16)
    state = np.random.random(4)
    gates = np.random.random((16, 4, 4))
    tom = Tomography(amplitudes, state, gates)
    np.testing.assert_allclose(tom.amplitudes, amplitudes)
    np.testing.assert_allclose(tom.state, state)
    np.testing.assert_allclose(tom.gates, gates)


def test_tomography_find_beta():
    amplitudes = np.random.random(16)
    state = np.array([1, 2, 3, 4])
    tom = Tomography(amplitudes, state)
    target_beta = [2.5, -1, -0.5, 0]
    np.testing.assert_allclose(tom.find_beta(state), target_beta)


def test_tomography_default_gates():
    amplitudes = np.random.random(16)
    state = np.array([1, 2, 3, 4])
    tom = Tomography(amplitudes, state)
    target_path = os.path.join(os.getcwd(), "data")
    if not os.path.exists(target_path):
        os.mkdir("results")
    target_path = os.path.join(os.getcwd(), "data", "default_gates.npy")
    if os.path.exists(target_path):
        target_gates = np.load(target_path)
        np.testing.assert_allclose(tom.gates, target_gates)
    else:
        np.save(target_path, tom.gates)


def test_tomography_linear():
    amplitudes = np.arange(16)
    amplitudes = amplitudes / amplitudes.sum()
    state = np.array([0.48721439, 0.61111949, 0.44811308, 0.05143444])
    tom = Tomography(amplitudes, state)
    target_path = os.path.join(os.getcwd(), "data", "linear_estimation.npy")
    if os.path.exists(target_path):
        target_linear = np.load(target_path)
        np.testing.assert_allclose(tom.linear, target_linear)
    else:
        np.save(target_path, tom.linear)


def test_tomography_fit():
    amplitudes = np.arange(16)
    amplitudes = amplitudes / amplitudes.sum()
    state = np.array([0.48721439, 0.61111949, 0.44811308, 0.05143444])
    tom = Tomography(amplitudes, state)
    with pytest.raises(ValueError):
        tom.fit

    tom.minimize()
    assert tom.success

    target_path = os.path.join(os.getcwd(), "data", "mlefit_estimation.npy")
    if os.path.exists(target_path):
        target_fit = np.load(target_path)
        np.testing.assert_allclose(tom.fit, target_fit)
    else:
        np.save(target_path, tom.fit)


def extract_json(filepath):
    with open(filepath, "r") as file:
        raw = json.loads(file.read())
    data = np.stack(list(raw.values()))
    return np.sqrt((data ** 2).sum(axis=1))


@pytest.mark.parametrize("state_value,target_fidelity",
                         [(0, 93.01278047175582), (1, 82.30795926024483),
                          (2, 65.06114271984393), (3, 22.230579223385284)])
def test_tomography_example(state_value, target_fidelity):
    target_file = "tomo_181120-{0:02b}.json".format(state_value)
    print(target_file)
    state_path = os.path.join(os.getcwd(), "data", "states_181120.json")
    amplitude_path = os.path.join(os.getcwd(), "data", target_file)
    if not os.path.exists(state_path):
        pytest.skip("Skipping tomography test because data are not available.")
    state = extract_json(state_path)
    amp = extract_json(amplitude_path)
    tom = Tomography(amp, state)
    tom.minimize()
    assert tom.success
    rho_theory = np.zeros((4, 4), dtype=complex)
    rho_theory[state_value, state_value] = 1
    fidelity = tom.fidelity(rho_theory)
    np.testing.assert_allclose(fidelity, target_fidelity)
