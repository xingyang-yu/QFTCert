"""Depth-K mutation chain-runner tests (Phase 2d, offline).

Composition logic (node selection, backtracking, repeated-state,
determinism, attrition reasons) is unit-tested with a STUB single-step
mutator + stub verifier so the tests are fast and physics-free. A few
real-physics smoke tests cover depth-1 and depth-2-on-dp0 quickly; the
slow real depth-2 success path on F_0 is marked `slow`.
"""

from __future__ import annotations

from random import Random

import pytest

from dualitycert.experiments.chains import (
    MutationChainResult,
    SingleMutationResult,
    apply_single_seiberg_mutation,
    generate_mutation_chain,
    legal_mutation_nodes,
)
from dualitycert.experiments.config import ChainConfig, VerifierConfig
from dualitycert.experiments.seeds import dp0_electric, f0_phase_ii_electric
from dualitycert.experiments.verifier import VerifierOutcome


# ----------------------------------------------------------------------
# Stub mutator / verifier for fast composition tests.
# ----------------------------------------------------------------------


def _mk(state: int) -> dict:
    """A minimal sanitizer-hashable theory whose identity is `state`."""

    return {
        "name": f"S{state}",
        "node_labels": ["G0", "G1", "G2"],
        "ranks": [2, 2, 2],
        "u1_globals": [],
        "arrows": [{"label": "x", "source": 0, "target": 1, "r_charge": str(state)}],
        "superpotential": [],
    }


def _state_of(theory) -> int:
    return int(theory["arrows"][0]["r_charge"])


class _StubMutator:
    """transitions: {(state, node): next_state}; missing -> step fails."""

    def __init__(self, transitions: dict):
        self.transitions = transitions

    def __call__(self, theory, node, rng) -> SingleMutationResult:
        nxt = self.transitions.get((_state_of(theory), node))
        if nxt is None:
            return SingleMutationResult(
                ok=False, node=node, reason="single_step_mutation_failed"
            )
        return SingleMutationResult(
            ok=True, node=node, theory=_mk(nxt), metadata={"node": node, "to": nxt}
        )


def _always_certified(a, b, vcfg) -> VerifierOutcome:
    return VerifierOutcome(status="CERTIFIED")


def _stub_chain(transitions, depth, *, cfg=None, seed=0):
    cfg = cfg or ChainConfig()
    return generate_mutation_chain(
        _mk(0),
        depth,
        Random(seed),
        cfg,
        source_name="stub",
        seed_id=1,
        step_fn=_StubMutator(transitions),
        verify_fn=_always_certified,
        schema_fn=lambda t: True,
    )


def test_stub_depth2_composition_succeeds():
    t = {(0, n): 1 for n in range(3)}
    t.update({(1, n): 2 for n in range(3)})
    res = _stub_chain(t, 2)
    assert res.success is True
    assert res.depth_realized == 2
    assert len(res.node_sequence) == 2
    assert _state_of(res.final_theory) == 2
    # intermediate hashes track T0..T2.
    assert len(res.intermediate_hashes) == 3


def test_stub_immediate_backtracking_rejected():
    # step1: 0->1 ; step2: every node maps 1->0 (== T_0) -> rejected.
    t = {(0, n): 1 for n in range(3)}
    t.update({(1, n): 0 for n in range(3)})
    res = _stub_chain(t, 2)
    assert res.success is False
    assert res.attrition_reason == "immediate_backtracking_rejected"


def test_stub_repeated_state_rejected():
    # step1: 0->1 ; step2: 1->1 (repeats current state, not T_{i-2}).
    t = {(0, n): 1 for n in range(3)}
    t.update({(1, n): 1 for n in range(3)})
    res = _stub_chain(t, 2)
    assert res.success is False
    assert res.attrition_reason == "repeated_state_rejected"


def test_stub_allow_repeated_states_permits_revisit():
    t = {(0, n): 1 for n in range(3)}
    t.update({(1, n): 1 for n in range(3)})
    cfg = ChainConfig(allow_repeated_states=True, forbid_immediate_backtracking=False)
    res = _stub_chain(t, 2, cfg=cfg)
    assert res.success is True
    assert _state_of(res.final_theory) == 1


def test_stub_no_valid_step_attrition():
    res = _stub_chain({}, 2)  # no transitions -> step always fails
    assert res.success is False
    assert res.attrition_reason in {"no_valid_mutation_nodes", "single_step_mutation_failed"}


def test_stub_chain_is_deterministic():
    t = {(0, n): 1 for n in range(3)}
    t.update({(1, n): 2 for n in range(3)})
    a = _stub_chain(t, 2, seed=42)
    b = _stub_chain(t, 2, seed=42)
    assert a.node_sequence == b.node_sequence
    assert a.canonical_hash == b.canonical_hash


def test_depth_must_be_positive():
    from dualitycert.experiments.chains import ChainConstructionError

    with pytest.raises(ChainConstructionError):
        _stub_chain({}, 0)


# ----------------------------------------------------------------------
# Real-physics smoke tests (fast).
# ----------------------------------------------------------------------


def test_single_step_move_and_legal_nodes():
    smr = apply_single_seiberg_mutation(dp0_electric(3), 0)
    assert smr.ok is True
    assert "ranks" in smr.theory
    assert 0 in legal_mutation_nodes(dp0_electric(3))


def test_chain_depth1_real_reproduces_single_move():
    res = generate_mutation_chain(
        dp0_electric(3), 1, Random(0), source_name="dp0", node=0, seed_id=1
    )
    assert res.success is True
    assert res.node_sequence == (0,)
    assert res.depth_realized == 1
    assert res.verifier_status_seed_to_final == "CERTIFIED"
    # depth-1 final equals the bare single-step move (MVP-exact pipeline).
    import json

    direct = apply_single_seiberg_mutation(dp0_electric(3), 0).theory
    assert json.dumps(res.final_theory, sort_keys=True) == json.dumps(
        direct, sort_keys=True
    )


def test_chain_depth2_succeeds_genuine_on_dp0():
    # dp0's magnetic dual CAN now be re-mutated (multi-term F-term
    # integration): a GENUINE depth-2 dual at a different second node,
    # certified end to end -- not a same-node Seiberg involution / round-trip.
    res = generate_mutation_chain(
        dp0_electric(3), 2, Random(1), ChainConfig(), source_name="dp0", node=0,
        seed_id=1,
    )
    assert isinstance(res, MutationChainResult)
    assert res.success is True
    assert res.depth_realized == 2
    # genuine: the two moves are at different nodes (no consecutive involution)
    assert res.node_sequence[0] != res.node_sequence[1]
    assert res.verifier_status_seed_to_final == "CERTIFIED"
    assert all(s == "CERTIFIED" for s in res.verifier_status_adjacent_steps)


@pytest.mark.slow
def test_chain_depth2_real_success_on_f0_seed_to_final():
    # With adjacent verification OFF (seed-to-final gating only), F_0
    # admits genuine depth-2 duals (intermediates are scaffolding).
    cfg = ChainConfig(verify_adjacent_steps=False, verify_seed_to_final=True)
    successes = 0
    for attempt in range(16):
        res = generate_mutation_chain(
            f0_phase_ii_electric(3), 2, Random(1000 + attempt), cfg,
            source_name="f0", seed_id=2,
        )
        if res.success:
            successes += 1
            assert res.depth_realized == 2
            assert res.verifier_status_seed_to_final == "CERTIFIED"
    assert successes >= 1
