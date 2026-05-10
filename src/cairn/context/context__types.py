from dataclasses import dataclass


@dataclass(frozen=True)
class AssemblyWeights:
    relevance: float = 0.5
    confidence: float = 0.25
    recency: float = 0.15
    bias: float = 0.1
