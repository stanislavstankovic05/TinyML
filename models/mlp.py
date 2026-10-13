from sklearn.neural_network import MLPRegressor

from models.base import BurstModel


class MlpModel(BurstModel):
    family = "mlp"
    estimator_class = MLPRegressor
    scaled = True
    settings = {
        "hidden_layer_sizes": (16, 8),
        "alpha": 0.1,
        "max_iter": 5000,
        "early_stopping": True,
        "n_iter_no_change": 30,
    }
    grid = {"hidden_layer_sizes": [(4,), (8,), (16,), (8, 4), (16, 8)], "alpha": [0.01, 0.1, 1.0]}
