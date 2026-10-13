from sklearn.ensemble import HistGradientBoostingRegressor

from models.base import BurstModel


class GradientBoostingModel(BurstModel):
    family = "gradient_boosting"
    estimator_class = HistGradientBoostingRegressor
    settings = {"max_iter": 50, "max_depth": 4}
    grid = {"max_iter": [20, 50, 100, 200], "max_depth": [2, 3, 4, 6]}
