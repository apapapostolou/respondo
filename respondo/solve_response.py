import numpy as np

from adcc.solver.conjugate_gradient import conjugate_gradient, default_print
from adcc.solver.preconditioner import JacobiPreconditioner
from adcc.solver.explicit_symmetrisation import IndexSymmetrisation
from adcc.adc_pp.state2state_transition_dm import state2state_transition_dm
from adcc.OneParticleOperator import product_trace

from .cpp_algebra import (
    ComplexPolarizationPropagatorPinv,
    ResponseVectorSymmetrisation,
)
from .cpp_algebra import ComplexPolarizationPropagatorMatrix as CppMatrix


def solve_real(
    matrix, rhs, omega, solver=conjugate_gradient, preconditioner=None, **solver_args
):
    matrix.omega = omega
    if preconditioner is None:
        preconditioner = JacobiPreconditioner(matrix)
    explicit_symmetrisation = IndexSymmetrisation(matrix)
    preconditioner.update_shifts(omega)
    # solve system of linear equations
    x0 = preconditioner.apply(rhs)
    res = solver(
        matrix,
        rhs=rhs,
        x0=x0,
        callback=default_print,
        Pinv=preconditioner,
        explicit_symmetrisation=explicit_symmetrisation,
        **solver_args,
    )
    return res.solution


def solve_complex(matrix, rhs, omega, gamma, solver=conjugate_gradient, **solver_args):
    cpp_matrix = CppMatrix(matrix, gamma=gamma, omega=omega)
    Pinv = ComplexPolarizationPropagatorPinv(cpp_matrix, shift=omega, gamma=gamma)
    x0 = Pinv @ rhs
    rsymm = ResponseVectorSymmetrisation(matrix)
    guess_symm = rsymm.symmetrise(x0)
    # solve system of linear equations
    res = solver(
        cpp_matrix,
        rhs=rhs,
        x0=guess_symm,
        callback=default_print,
        Pinv=Pinv,
        explicit_symmetrisation=rsymm,
        **solver_args,
    )
    return res.solution


# from_vecs * B(ops) * to_vecs
def transition_polarizability(method, ground_state, from_vecs, ops, to_vecs):
    if not isinstance(from_vecs, list):
        from_vecs = [from_vecs]
    if not isinstance(to_vecs, list):
        to_vecs = [to_vecs]
    if not isinstance(ops, list):
        ops = [ops]

    ret = np.zeros((len(from_vecs), len(ops), len(to_vecs)))
    for i, from_vec in enumerate(from_vecs):
        for j, to_vec in enumerate(to_vecs):
            tdm = state2state_transition_dm(method, ground_state, from_vec, to_vec)
            for k, op in enumerate(ops):
                ret[i, k, j] = product_trace(tdm, op)
    return np.squeeze(ret)


def transition_polarizability_complex(method, ground_state, from_vecs, ops, to_vecs):
    if not isinstance(from_vecs, list):
        from_vecs = [from_vecs]
    if not isinstance(to_vecs, list):
        to_vecs = [to_vecs]
    if not isinstance(ops, list):
        ops = [ops]

    # TODO: maybe use non-complex transition_polarizability function?
    # TODO: "recognize" ResponseVector/AmplitudeVector
    ret = np.zeros((len(from_vecs), len(ops), len(to_vecs)), dtype=np.complex)
    for i, from_vec in enumerate(from_vecs):
        for j, to_vec in enumerate(to_vecs):
            # TODO: optimize performance...
            # compute dot product?
            tdm_real_real = state2state_transition_dm(
                method, ground_state, from_vec.real, to_vec.real
            )
            tdm_imag_real = state2state_transition_dm(
                method, ground_state, from_vec.imag, to_vec.real
            )
            tdm_real_imag = state2state_transition_dm(
                method, ground_state, from_vec.real, to_vec.imag
            )
            tdm_imag_imag = state2state_transition_dm(
                method, ground_state, from_vec.imag, to_vec.imag
            )
            real = tdm_real_real - tdm_imag_imag
            imag = tdm_imag_real + tdm_real_imag
            for k, op in enumerate(ops):
                ret[i, k, j] = np.complex(
                    product_trace(real, op), product_trace(imag, op)
                )
    return np.squeeze(ret)