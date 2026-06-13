"""
PrivacyLabel — privacy-preserving federated data labeling with deepfake detection.

Part of the ResponsibleAI toolkit: https://github.com/Guruprasath-Annadurai/ResponsibleAi

Quick start::

    from privacylabel import FederatedClient, DeepfakeDetector, DifferentialPrivacy
    from privacylabel.providers import OpenAILabelProvider

    # Federated labeling round — data never leaves the device
    client = FederatedClient("node-01", provider=OpenAILabelProvider(api_key="sk-..."))
    summary = await client.train_round("local_data.jsonl")

    # Deepfake detection
    detector = DeepfakeDetector()
    result = await detector.detect_image("photo.jpg")
    print(result.is_fake, result.confidence)
"""

from privacylabel.core.label import Label, LabelBatch
from privacylabel.core.privacy_budget import PrivacyBudget
from privacylabel.crypto.differential_privacy import DifferentialPrivacy
from privacylabel.deepfake.detector import DeepfakeDetector, DeepfakeResult
from privacylabel.federated.aggregator import FedAvgAggregator
from privacylabel.federated.client import FederatedClient, RoundSummary

__version__ = "0.1.0"
__all__ = [
    "DeepfakeDetector",
    "DeepfakeResult",
    "DifferentialPrivacy",
    "FedAvgAggregator",
    "FederatedClient",
    "Label",
    "LabelBatch",
    "PrivacyBudget",
    "RoundSummary",
    "__version__",
]
