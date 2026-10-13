from sklearn.linear_model import Ridge

from models.base import BurstModel


class RidgeModel(BurstModel):
    family = "ridge"
    estimator_class = Ridge
    scaled = True
    settings = {"alpha": 1.0}
    grid = {"alpha": [0.1, 1.0, 10.0, 100.0]}
