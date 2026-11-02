from __future__ import annotations

import numpy as np
import pytest

from privacylabel.federated.aggregator import FedAvgAggregator, NodeUpdate


def _update(node_id: str, values: list[float], n_samples: int = 100) -> NodeUpdate:
    return NodeUpdate(
        node_id=node_id,
        gradients=np.array(values),
        num_samples=n_samples,
        round_number=0,
    )


class TestFedAvgAggregator:
    def test_pending_count_zero_initially(self) -> None:
        agg = FedAvgAggregator()
        assert agg.pending_count == 0

    def test_submit_increments_pending(self) -> None:
        agg = FedAvgAggregator()
        agg.submit(_update("a", [1.0, 2.0]))
        assert agg.pending_count == 1

    def test_can_aggregate_false_when_below_min(self) -> None:
        agg = FedAvgAggregator(min_nodes=3)
        agg.submit(_update("a", [1.0]))
        agg.submit(_update("b", [2.0]))
        assert not agg.can_aggregate()

    def test_can_aggregate_true_at_min(self) -> None:
        agg = FedAvgAggregator(min_nodes=2)
        agg.submit(_update("a", [1.0]))
        agg.submit(_update("b", [2.0]))
        assert agg.can_aggregate()

    def test_aggregate_raises_below_min(self) -> None:
        agg = FedAvgAggregator(min_nodes=3)
        agg.submit(_update("a", [1.0]))
        with pytest.raises(ValueError):
            agg.aggregate()

    def test_fedavg_uniform_weights(self) -> None:
        agg = FedAvgAggregator()
        agg.submit(_update("a", [1.0, 3.0], n_samples=100))
        agg.submit(_update("b", [3.0, 1.0], n_samples=100))
        result = agg.aggregate()
        # Equal weights → simple mean: [2.0, 2.0]
        assert np.allclose(result.global_gradients, [2.0, 2.0])

    def test_fedavg_weighted_by_samples(self) -> None:
        agg = FedAvgAggregator()
        agg.submit(_update("a", [0.0], n_samples=300))
        agg.submit(_update("b", [1.0], n_samples=100))
        result = agg.aggregate()
        # Expected: (300*0 + 100*1) / 400 = 0.25
        assert np.allclose(result.global_gradients, [0.25])

    def test_aggregate_clears_pending(self) -> None:
        agg = FedAvgAggregator()
        agg.submit(_update("a", [1.0]))
        agg.aggregate()
        assert agg.pending_count == 0

    def test_round_counter_increments(self) -> None:
        agg = FedAvgAggregator()
        assert agg.current_round == 0
        agg.submit(_update("a", [1.0]))
        agg.aggregate()
        assert agg.current_round == 1
        agg.submit(_update("b", [2.0]))
        agg.aggregate()
        assert agg.current_round == 2

    def test_result_contains_node_ids(self) -> None:
        agg = FedAvgAggregator()
        agg.submit(_update("node-1", [1.0]))
        agg.submit(_update("node-2", [2.0]))
        result = agg.aggregate()
        assert "node-1" in result.participating_nodes
        assert "node-2" in result.participating_nodes

    def test_result_method_is_fedavg(self) -> None:
        agg = FedAvgAggregator(byzantine_robust=False)
        agg.submit(_update("a", [1.0]))
        result = agg.aggregate()
        assert result.aggregation_method == "fedavg"

    def test_result_to_dict(self) -> None:
        agg = FedAvgAggregator()
        agg.submit(_update("a", [1.0, 2.0]))
        result = agg.aggregate()
        d = result.to_dict()
        assert "round_number" in d
        assert "participating_nodes" in d
        assert "gradient_norm" in d

    def test_three_equal_nodes(self) -> None:
        agg = FedAvgAggregator()
        for name in ["a", "b", "c"]:
            agg.submit(_update(name, [6.0], n_samples=100))
        result = agg.aggregate()
        assert np.allclose(result.global_gradients, [6.0])

    def test_zero_samples_fallback_uniform(self) -> None:
        agg = FedAvgAggregator()
        agg.submit(_update("a", [0.0], n_samples=0))
        agg.submit(_update("b", [2.0], n_samples=0))
        result = agg.aggregate()
        assert np.allclose(result.global_gradients, [1.0])  # uniform average


class TestByzantineRobustAggregation:
    def test_geometric_median_mode(self) -> None:
        agg = FedAvgAggregator(byzantine_robust=True)
        agg.submit(_update("a", [1.0, 1.0]))
        agg.submit(_update("b", [1.0, 1.0]))
        agg.submit(_update("c", [1.0, 1.0]))
        result = agg.aggregate()
        assert result.aggregation_method == "geometric_median"
        assert np.allclose(result.global_gradients, [1.0, 1.0], atol=1e-3)

    def test_geometric_median_robust_to_outlier(self) -> None:
        agg = FedAvgAggregator(byzantine_robust=True, weiszfeld_iterations=100)
        # 4 honest nodes at [0, 0]; 1 Byzantine outlier at [100, 100]
        for i in range(4):
            agg.submit(_update(f"honest-{i}", [0.0, 0.0]))
        agg.submit(_update("byzantine", [100.0, 100.0]))
        result = agg.aggregate()
        # Geometric median should stay near [0, 0], not pulled to [20, 20]
        assert np.linalg.norm(result.global_gradients) < 5.0

    def test_single_node_geometric_median(self) -> None:
        agg = FedAvgAggregator(byzantine_robust=True)
        agg.submit(_update("a", [3.0, 4.0]))
        result = agg.aggregate()
        assert np.allclose(result.global_gradients, [3.0, 4.0], atol=1e-3)
